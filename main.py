from fastapi import FastAPI, Depends, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime, timedelta
import hashlib, random

import models, database
from database import engine, get_db

models.Base.metadata.create_all(bind=engine)

app = FastAPI(title="Smart Attendance")
app.mount("/static", StaticFiles(directory="static"), name="static")

def h(pw): return hashlib.sha256(pw.encode()).hexdigest()

DAYS_ORDER = ["Monday","Tuesday","Wednesday","Thursday","Friday","Saturday","Sunday"]

@app.get("/")
def root(): return FileResponse("static/index.html")

# ══════════════════════════════════════════
# AUTH
# ══════════════════════════════════════════
class LoginReq(BaseModel):
    email: str
    password: str

@app.post("/api/login")
def login(req: LoginReq, db: Session = Depends(get_db)):
    u = db.query(models.User).filter(models.User.email == req.email).first()
    if not u or u.password != h(req.password):
        raise HTTPException(401, "Invalid credentials")
    return {"id":u.id,"name":u.name,"email":u.email,"role":u.role,
            "department":u.department,"student_id":u.student_id,"avatar_color":u.avatar_color}

# ══════════════════════════════════════════
# USERS
# ══════════════════════════════════════════
@app.get("/api/users")
def get_users(role: Optional[str] = None, db: Session = Depends(get_db)):
    q = db.query(models.User)
    if role: q = q.filter(models.User.role == role)
    return [{"id":u.id,"name":u.name,"email":u.email,"role":u.role,
             "department":u.department,"student_id":u.student_id,
             "avatar_color":u.avatar_color} for u in q.all()]

# ══════════════════════════════════════════
# SUBJECTS & SLOTS
# ══════════════════════════════════════════
def subject_dict(s: models.Subject):
    fac = s.faculty
    return {"id":s.id,"name":s.name,"code":s.code,"section":s.section,
            "semester":s.semester,"faculty_id":s.faculty_id,
            "faculty_name":fac.name if fac else "","faculty_dept":fac.department if fac else ""}

@app.get("/api/subjects")
def get_subjects(faculty_id: Optional[int]=None, student_id: Optional[int]=None,
                 db: Session = Depends(get_db)):
    if faculty_id:
        subjs = db.query(models.Subject).filter(models.Subject.faculty_id==faculty_id).all()
    elif student_id:
        enrollments = db.query(models.Enrollment).filter(
            models.Enrollment.student_id==student_id).all()
        subjs = [e.subject for e in enrollments]
    else:
        subjs = db.query(models.Subject).all()
    return [subject_dict(s) for s in subjs]

def slot_dict(sl: models.ClassSlot, db: Session):
    s = sl.subject_rel
    fac = s.faculty if s else None
    return {"id":sl.id,"subject_id":sl.subject_id,
            "subject_name":s.name if s else "","subject_code":s.code if s else "",
            "faculty_id":s.faculty_id if s else None,
            "faculty_name":fac.name if fac else "",
            "day":sl.day_of_week,"start_time":sl.start_time,
            "end_time":sl.end_time,"room":sl.room}

@app.get("/api/slots")
def get_slots(faculty_id: Optional[int]=None, student_id: Optional[int]=None,
              day: Optional[str]=None, db: Session = Depends(get_db)):
    q = db.query(models.ClassSlot)
    if faculty_id:
        subj_ids = [s.id for s in db.query(models.Subject).filter(
            models.Subject.faculty_id==faculty_id).all()]
        q = q.filter(models.ClassSlot.subject_id.in_(subj_ids))
    if student_id:
        enr_ids = [e.subject_id for e in db.query(models.Enrollment).filter(
            models.Enrollment.student_id==student_id).all()]
        q = q.filter(models.ClassSlot.subject_id.in_(enr_ids))
    if day:
        q = q.filter(models.ClassSlot.day_of_week==day)
    slots = q.all()
    return sorted([slot_dict(sl, db) for sl in slots],
                  key=lambda x: (DAYS_ORDER.index(x["day"]) if x["day"] in DAYS_ORDER else 9,
                                 x["start_time"]))

# ══════════════════════════════════════════
# ATTENDANCE
# ══════════════════════════════════════════
class AttendanceSubmit(BaseModel):
    slot_id: int
    faculty_id: int
    date: str
    records: list   # [{student_id, status}]

@app.get("/api/attendance/slot-students/{slot_id}")
def slot_students(slot_id: int, date: str, db: Session = Depends(get_db)):
    slot = db.query(models.ClassSlot).filter(models.ClassSlot.id==slot_id).first()
    if not slot: raise HTTPException(404, "Slot not found")

    # Already submitted?
    existing = db.query(models.AttendanceSession).filter(
        models.AttendanceSession.slot_id==slot_id,
        models.AttendanceSession.date==date).first()

    record_map = {}
    if existing:
        for r in existing.records:
            record_map[r.student_id] = r.status

    # All enrolled students
    enrollments = db.query(models.Enrollment).filter(
        models.Enrollment.subject_id==slot.subject_id).all()

    students = []
    for e in enrollments:
        u = e.student
        if u:
            students.append({"student_id":u.id,"name":u.name,
                             "student_no":u.student_id,"avatar_color":u.avatar_color,
                             "status":record_map.get(u.id)})

    return {"students":students,"already_submitted":existing is not None,
            "total_present":existing.total_present if existing else 0,
            "total_absent":existing.total_absent if existing else 0}

@app.post("/api/attendance/submit")
def submit_attendance(req: AttendanceSubmit, db: Session = Depends(get_db)):
    existing = db.query(models.AttendanceSession).filter(
        models.AttendanceSession.slot_id==req.slot_id,
        models.AttendanceSession.date==req.date).first()
    if existing:
        raise HTTPException(400, "Attendance already submitted for this session.")

    slot = db.query(models.ClassSlot).filter(models.ClassSlot.id==req.slot_id).first()
    subj = db.query(models.Subject).filter(models.Subject.id==slot.subject_id).first() if slot else None

    present_count = absent_count = 0
    absent_students = []

    sess = models.AttendanceSession(
        subject_id=slot.subject_id if slot else None,
        slot_id=req.slot_id, faculty_id=req.faculty_id, date=req.date)
    db.add(sess); db.flush()

    for rec in req.records:
        sid, status = rec["student_id"], rec["status"]
        db.add(models.AttendanceRecord(session_id=sess.id, student_id=sid, status=status))
        if status == "present": present_count += 1
        else:
            absent_count += 1
            stu = db.query(models.User).filter(models.User.id==sid).first()
            if stu: absent_students.append(stu)

    sess.total_present = present_count
    sess.total_absent  = absent_count
    db.flush()

    # Notify absent students
    for stu in absent_students:
        db.add(models.Notification(
            user_id=stu.id,
            title=f"Absent: {subj.name if subj else 'Class'}",
            message=f"You were marked absent in {subj.name if subj else 'a class'} on {req.date}. "
                    f"Please maintain at least 75% attendance.",
            type="warning"))
        # Simulated parent alert — visible to admin
        db.add(models.Notification(
            role_target="admin",
            title=f"Parent Alert — {stu.name}",
            message=f"[SIMULATED] SMS/Email sent to parent of {stu.name} ({stu.student_id}): "
                    f"Absent in {subj.name if subj else 'class'} on {req.date}.",
            type="warning"))

    db.commit()
    return {"message":"Submitted","present":present_count,
            "absent":absent_count,"alerts_sent":len(absent_students)}

@app.get("/api/attendance/student/{student_id}")
def student_attendance(student_id: int, db: Session = Depends(get_db)):
    enrollments = db.query(models.Enrollment).filter(
        models.Enrollment.student_id==student_id).all()
    result = []
    for e in enrollments:
        subj = e.subject
        sessions = db.query(models.AttendanceSession).filter(
            models.AttendanceSession.subject_id==subj.id).all()
        total = present = absent = 0
        history = []
        for sess in sessions:
            rec = next((r for r in sess.records if r.student_id==student_id), None)
            if rec:
                total += 1
                if rec.status=="present": present += 1
                else: absent += 1
                history.append({"date":sess.date,"status":rec.status,
                                 "day":sess.slot.day_of_week if sess.slot else ""})
        pct = round((present/total)*100) if total>0 else 0
        color = "green" if pct>=75 else ("amber" if pct>=60 else "red")
        fac = subj.faculty
        result.append({"subject_id":subj.id,"subject":subj.name,"code":subj.code,
                        "faculty":fac.name if fac else "","total":total,
                        "present":present,"absent":absent,"percentage":pct,
                        "color":color,"history":sorted(history,key=lambda x:x["date"])})
    return sorted(result, key=lambda x: x["percentage"])

@app.get("/api/attendance/faculty/{faculty_id}")
def faculty_attendance_history(faculty_id: int, db: Session = Depends(get_db)):
    sessions = db.query(models.AttendanceSession).filter(
        models.AttendanceSession.faculty_id==faculty_id
    ).order_by(models.AttendanceSession.submitted_at.desc()).limit(50).all()
    result = []
    for s in sessions:
        subj = db.query(models.Subject).filter(models.Subject.id==s.subject_id).first()
        slot = db.query(models.ClassSlot).filter(models.ClassSlot.id==s.slot_id).first()
        total = s.total_present + s.total_absent
        result.append({"session_id":s.id,"subject":subj.name if subj else "","code":subj.code if subj else "",
                        "date":s.date,"day":slot.day_of_week if slot else "","room":slot.room if slot else "",
                        "time":slot.start_time if slot else "","total_present":s.total_present,
                        "total_absent":s.total_absent,"total":total,
                        "percentage":round((s.total_present/total)*100) if total>0 else 0,
                        "submitted_at":s.submitted_at.isoformat()})
    return result

@app.get("/api/attendance/admin/overview")
def admin_overview(db: Session = Depends(get_db)):
    sessions = db.query(models.AttendanceSession).all()
    records  = db.query(models.AttendanceRecord).all()
    total_present = sum(1 for r in records if r.status=="present")
    total_absent  = sum(1 for r in records if r.status=="absent")
    total         = len(records)

    # Per student
    student_map = {}
    for r in records:
        sid = r.student_id
        if sid not in student_map:
            u = db.query(models.User).filter(models.User.id==sid).first()
            student_map[sid] = {"name":u.name if u else "","student_no":u.student_id if u else "",
                                 "avatar_color":u.avatar_color if u else "#3b82f6",
                                 "total":0,"present":0,"absent":0}
        student_map[sid]["total"] += 1
        student_map[sid][r.status] += 1

    students_list = []
    for d in student_map.values():
        pct = round((d["present"]/d["total"])*100) if d["total"]>0 else 0
        d["percentage"] = pct
        d["color"] = "green" if pct>=75 else ("amber" if pct>=60 else "red")
        students_list.append(d)
    students_list.sort(key=lambda x: x["percentage"])

    # Per subject
    subject_map = {}
    for r in records:
        sess = db.query(models.AttendanceSession).filter(
            models.AttendanceSession.id==r.session_id).first()
        if not sess: continue
        subj = db.query(models.Subject).filter(models.Subject.id==sess.subject_id).first()
        if not subj: continue
        key = subj.name
        if key not in subject_map:
            subject_map[key] = {"subject":key,"code":subj.code,"total":0,"present":0,"absent":0}
        subject_map[key]["total"] += 1
        subject_map[key][r.status] += 1

    subjects_list = []
    for d in subject_map.values():
        pct = round((d["present"]/d["total"])*100) if d["total"]>0 else 0
        d["percentage"] = pct
        d["color"] = "green" if pct>=75 else ("amber" if pct>=60 else "red")
        subjects_list.append(d)
    subjects_list.sort(key=lambda x: x["percentage"])

    return {"total_sessions":len(sessions),"total_records":total,
            "total_present":total_present,"total_absent":total_absent,
            "overall_percentage":round((total_present/total)*100) if total>0 else 0,
            "students":students_list,"subjects":subjects_list}

# ══════════════════════════════════════════
# AI — ABSENTEE PATTERN DETECTION
# ══════════════════════════════════════════
@app.get("/api/ai/patterns")
def detect_patterns(db: Session = Depends(get_db)):
    """
    Detect students absent 3+ consecutive times in any subject.
    Pure logic — no external AI needed.
    """
    enrollments = db.query(models.Enrollment).all()
    alerts = []

    for e in enrollments:
        student = e.student
        subj    = e.subject
        if not student or not subj: continue

        sessions = db.query(models.AttendanceSession).filter(
            models.AttendanceSession.subject_id==subj.id
        ).order_by(models.AttendanceSession.date).all()

        # Build attendance list for this student in this subject
        attendance = []
        for sess in sessions:
            rec = next((r for r in sess.records if r.student_id==student.id), None)
            if rec: attendance.append({"date":sess.date,"status":rec.status})

        # Count consecutive absences
        max_streak = streak = 0
        streak_start = None
        for entry in attendance:
            if entry["status"] == "absent":
                if streak == 0: streak_start = entry["date"]
                streak += 1
                max_streak = max(max_streak, streak)
            else:
                streak = 0

        if max_streak >= 3:
            total = len(attendance)
            present = sum(1 for a in attendance if a["status"]=="present")
            pct = round((present/total)*100) if total>0 else 0
            alerts.append({
                "student_name": student.name,
                "student_no":   student.student_id,
                "avatar_color": student.avatar_color,
                "subject":      subj.name,
                "code":         subj.code,
                "max_streak":   max_streak,
                "total":        total,
                "present":      present,
                "absent":       total - present,
                "percentage":   pct,
                "color":        "green" if pct>=75 else ("amber" if pct>=60 else "red"),
                "risk_level":   "High" if max_streak>=5 else "Medium",
            })

    alerts.sort(key=lambda x: x["max_streak"], reverse=True)
    return alerts

# ══════════════════════════════════════════
# NOTIFICATIONS
# ══════════════════════════════════════════
@app.get("/api/notifications")
def get_notifs(user_id: int, role: str, db: Session = Depends(get_db)):
    notifs = db.query(models.Notification).filter(
        (models.Notification.user_id==user_id) |
        (models.Notification.role_target==role)
    ).order_by(models.Notification.created_at.desc()).limit(30).all()
    return [{"id":n.id,"title":n.title,"message":n.message,"type":n.type,
             "is_read":n.is_read,"created_at":n.created_at.isoformat()} for n in notifs]

@app.post("/api/notifications/{notif_id}/read")
def read_notif(notif_id: int, db: Session = Depends(get_db)):
    n = db.query(models.Notification).filter(models.Notification.id==notif_id).first()
    if n: n.is_read=True; db.commit()
    return {"ok":True}

@app.post("/api/notifications/read-all")
def read_all(user_id: int, role: str, db: Session = Depends(get_db)):
    db.query(models.Notification).filter(
        (models.Notification.user_id==user_id) |
        (models.Notification.role_target==role)
    ).update({"is_read":True}); db.commit()
    return {"ok":True}

# ══════════════════════════════════════════
# DASHBOARD STATS
# ══════════════════════════════════════════
@app.get("/api/dashboard")
def dashboard(user_id: int, role: str, db: Session = Depends(get_db)):
    unread = db.query(models.Notification).filter(
        ((models.Notification.user_id==user_id) |
         (models.Notification.role_target==role)),
        models.Notification.is_read==False).count()

    if role=="admin":
        return {"total_students":db.query(models.User).filter(models.User.role=="student").count(),
                "total_faculty": db.query(models.User).filter(models.User.role=="faculty").count(),
                "total_subjects":db.query(models.Subject).count(),
                "total_sessions":db.query(models.AttendanceSession).count(),
                "total_records": db.query(models.AttendanceRecord).count(),
                "unread_notifications":unread}
    elif role=="faculty":
        subj_ids = [s.id for s in db.query(models.Subject).filter(
            models.Subject.faculty_id==user_id).all()]
        return {"my_subjects":    len(subj_ids),
                "sessions_taken": db.query(models.AttendanceSession).filter(
                    models.AttendanceSession.faculty_id==user_id).count(),
                "unread_notifications":unread}
    else:
        recs = db.query(models.AttendanceRecord).join(
            models.AttendanceSession,
            models.AttendanceRecord.session_id==models.AttendanceSession.id
        ).filter(models.AttendanceRecord.student_id==user_id).all()
        total   = len(recs)
        present = sum(1 for r in recs if r.status=="present")
        pct     = round((present/total)*100) if total>0 else 0
        return {"total_classes":total,"total_present":present,
                "total_absent":total-present,"overall_percentage":pct,
                "unread_notifications":unread}
