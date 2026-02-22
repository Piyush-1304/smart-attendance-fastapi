from sqlalchemy import Column, Integer, String, Boolean, ForeignKey, DateTime, Text, Float
from sqlalchemy.orm import relationship
from database import Base
from datetime import datetime

class User(Base):
    __tablename__ = "users"
    id           = Column(Integer, primary_key=True, index=True)
    name         = Column(String, nullable=False)
    email        = Column(String, unique=True, nullable=False)
    password     = Column(String, nullable=False)
    role         = Column(String, nullable=False)   # admin | faculty | student
    department   = Column(String, default="")
    student_id   = Column(String, nullable=True)
    avatar_color = Column(String, default="#3b82f6")
    created_at   = Column(DateTime, default=datetime.utcnow)

class Subject(Base):
    __tablename__ = "subjects"
    id         = Column(Integer, primary_key=True, index=True)
    name       = Column(String, nullable=False)
    code       = Column(String, nullable=False)
    faculty_id = Column(Integer, ForeignKey("users.id"))
    section    = Column(String, default="A")
    semester   = Column(String, default="1st")
    faculty    = relationship("User", foreign_keys=[faculty_id])
    slots      = relationship("ClassSlot", back_populates="subject_rel")
    enrollments= relationship("Enrollment", back_populates="subject")

class ClassSlot(Base):
    __tablename__ = "class_slots"
    id           = Column(Integer, primary_key=True, index=True)
    subject_id   = Column(Integer, ForeignKey("subjects.id"))
    day_of_week  = Column(String, nullable=False)
    start_time   = Column(String, nullable=False)
    end_time     = Column(String, nullable=False)
    room         = Column(String, default="TBD")
    subject_rel  = relationship("Subject", back_populates="slots")

class Enrollment(Base):
    __tablename__ = "enrollments"
    id         = Column(Integer, primary_key=True)
    student_id = Column(Integer, ForeignKey("users.id"))
    subject_id = Column(Integer, ForeignKey("subjects.id"))
    student    = relationship("User", foreign_keys=[student_id])
    subject    = relationship("Subject", back_populates="enrollments")

class AttendanceSession(Base):
    """One session = one class slot on one date, submitted by faculty."""
    __tablename__ = "attendance_sessions"
    id            = Column(Integer, primary_key=True, index=True)
    subject_id    = Column(Integer, ForeignKey("subjects.id"))
    slot_id       = Column(Integer, ForeignKey("class_slots.id"))
    faculty_id    = Column(Integer, ForeignKey("users.id"))
    date          = Column(String, nullable=False)   # YYYY-MM-DD
    total_present = Column(Integer, default=0)
    total_absent  = Column(Integer, default=0)
    submitted_at  = Column(DateTime, default=datetime.utcnow)
    records       = relationship("AttendanceRecord", back_populates="session")

class AttendanceRecord(Base):
    __tablename__ = "attendance_records"
    id         = Column(Integer, primary_key=True, index=True)
    session_id = Column(Integer, ForeignKey("attendance_sessions.id"))
    student_id = Column(Integer, ForeignKey("users.id"))
    status     = Column(String, nullable=False)   # present | absent
    session    = relationship("AttendanceSession", back_populates="records")
    student    = relationship("User", foreign_keys=[student_id])

class Notification(Base):
    __tablename__ = "notifications"
    id          = Column(Integer, primary_key=True)
    user_id     = Column(Integer, ForeignKey("users.id"), nullable=True)
    role_target = Column(String, nullable=True)
    title       = Column(String)
    message     = Column(Text)
    type        = Column(String, default="info")
    is_read     = Column(Boolean, default=False)
    created_at  = Column(DateTime, default=datetime.utcnow)
