"""Seed demo data — run automatically on first launch."""
import hashlib, random
from datetime import datetime, timedelta
from database import SessionLocal, engine
import models

models.Base.metadata.create_all(bind=engine)

COLORS = ["#3b82f6","#6366f1","#10b981","#f59e0b","#ef4444","#8b5cf6","#06b6d4","#ec4899"]

def h(pw): return hashlib.sha256(pw.encode()).hexdigest()

def seed():
    db = SessionLocal()
    if db.query(models.User).count():
        print("Already seeded."); db.close(); return

    # ── Admin
    admin = models.User(name="Admin Office", email="admin@college.edu",
                        password=h("admin123"), role="admin",
                        department="Administration", avatar_color="#6366f1")
    db.add(admin); db.flush()

    # ── Faculty
    faculty_data = [
        ("Dr. Sarah Khan",   "s.khan@college.edu",   "Mathematics",       "#3b82f6"),
        ("Prof. Raj Patel",  "r.patel@college.edu",  "Computer Science",  "#10b981"),
        ("Dr. Amina Noor",   "a.noor@college.edu",   "Physics",           "#f59e0b"),
        ("Mr. Arjun Mehta",  "a.mehta@college.edu",  "English",           "#8b5cf6"),
    ]
    faculty = []
    for name, email, dept, color in faculty_data:
        f = models.User(name=name, email=email, password=h("faculty123"),
                        role="faculty", department=dept, avatar_color=color)
        db.add(f); db.flush(); faculty.append(f)

    # ── Students
    student_data = [
        ("Ali Hassan",       "ali@student.edu",     "2024-CS-001"),
        ("Priya Sharma",     "priya@student.edu",   "2024-CS-002"),
        ("Omar Farooq",      "omar@student.edu",    "2024-CS-003"),
        ("Zara Ahmed",       "zara@student.edu",    "2024-CS-004"),
        ("Rohan Verma",      "rohan@student.edu",   "2024-CS-005"),
        ("Fatima Malik",     "fatima@student.edu",  "2024-CS-006"),
        ("Dev Patel",        "dev@student.edu",     "2024-CS-007"),
        ("Sara Qureshi",     "sara@student.edu",    "2024-CS-008"),
    ]
    students = []
    for i, (name, email, sid) in enumerate(student_data):
        s = models.User(name=name, email=email, password=h("student123"),
                        role="student", student_id=sid,
                        avatar_color=COLORS[i % len(COLORS)])
        db.add(s); db.flush(); students.append(s)

    # ── Subjects
    subjects_data = [
        ("Calculus II",         "MATH201", faculty[0], "A", "2nd"),
        ("Linear Algebra",      "MATH202", faculty[0], "A", "2nd"),
        ("Data Structures",     "CS201",   faculty[1], "A", "2nd"),
        ("Database Systems",    "CS202",   faculty[1], "B", "2nd"),
        ("Mechanics",           "PHY201",  faculty[2], "A", "2nd"),
        ("Technical Writing",   "ENG201",  faculty[3], "A", "2nd"),
    ]
    subjects = []
    for name, code, fac, sec, sem in subjects_data:
        subj = models.Subject(name=name, code=code, faculty_id=fac.id,
                              section=sec, semester=sem)
        db.add(subj); db.flush(); subjects.append(subj)

    # ── Class Slots
    slot_data = [
        (subjects[0], "Monday",    "08:00", "09:00", "Room 101"),
        (subjects[0], "Wednesday", "08:00", "09:00", "Room 101"),
        (subjects[0], "Friday",    "08:00", "09:00", "Room 101"),
        (subjects[1], "Tuesday",   "10:00", "11:00", "Room 102"),
        (subjects[1], "Thursday",  "10:00", "11:00", "Room 102"),
        (subjects[2], "Monday",    "11:00", "12:00", "Lab A"),
        (subjects[2], "Wednesday", "11:00", "12:00", "Lab A"),
        (subjects[2], "Friday",    "11:00", "12:00", "Lab A"),
        (subjects[3], "Tuesday",   "13:00", "14:00", "Lab B"),
        (subjects[3], "Thursday",  "13:00", "14:00", "Lab B"),
        (subjects[4], "Monday",    "14:00", "15:00", "Room 201"),
        (subjects[4], "Wednesday", "14:00", "15:00", "Room 201"),
        (subjects[5], "Tuesday",   "15:00", "16:00", "Room 301"),
        (subjects[5], "Friday",    "15:00", "16:00", "Room 301"),
    ]
    slots = []
    for subj, day, st, et, room in slot_data:
        sl = models.ClassSlot(subject_id=subj.id, day_of_week=day,
                              start_time=st, end_time=et, room=room)
        db.add(sl); db.flush(); slots.append(sl)

    # ── Enrollments (all students in all subjects)
    for student in students:
        for subj in subjects:
            db.add(models.Enrollment(student_id=student.id, subject_id=subj.id))
    db.flush()

    # ── Demo Attendance (past 10 days)
    rng = random.Random(42)
    past_dates = [(datetime.today() - timedelta(days=i)).strftime("%Y-%m-%d")
                  for i in range(1, 11)]

    for slot in slots:
        for date in past_dates:
            # Skip weekends
            d = datetime.strptime(date, "%Y-%m-%d")
            if d.weekday() >= 5: continue
            # Only seed if day matches slot
            day_map = {"Monday":0,"Tuesday":1,"Wednesday":2,"Thursday":3,"Friday":4}
            if d.weekday() != day_map.get(slot.day_of_week, -1): continue

            present_count = absent_count = 0
            sess = models.AttendanceSession(
                subject_id=slot.subject_id, slot_id=slot.id,
                faculty_id=slot.subject_rel.faculty_id, date=date,
            )
            db.add(sess); db.flush()

            for student in students:
                # Make Rohan (index 4) and Fatima (index 5) have low attendance
                if student == students[4]:
                    status = "present" if rng.random() > 0.65 else "absent"
                elif student == students[5]:
                    status = "present" if rng.random() > 0.55 else "absent"
                else:
                    status = "present" if rng.random() > 0.18 else "absent"

                rec = models.AttendanceRecord(
                    session_id=sess.id, student_id=student.id, status=status)
                db.add(rec)
                if status == "present": present_count += 1
                else: absent_count += 1

            sess.total_present = present_count
            sess.total_absent  = absent_count

    db.commit()

    # ── Welcome notifications
    for s in students:
        db.add(models.Notification(
            user_id=s.id, title="Welcome to Smart Attendance!",
            message="Your attendance portal is now active. Check your attendance % under 'My Attendance'.",
            type="success"))
    db.add(models.Notification(
        role_target="faculty", title="Attendance System Live",
        message="You can now take attendance from your schedule. Go to 'My Schedule' and click any class.",
        type="info"))
    db.commit()

    print("✅ Seeded successfully!")
    print("\n  Demo Logins:")
    print("  Admin:   admin@college.edu    / admin123")
    print("  Faculty: s.khan@college.edu   / faculty123")
    print("  Student: ali@student.edu      / student123")
    db.close()

if __name__ == "__main__":
    seed()
