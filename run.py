"""
Smart Attendance System
Run: python run.py
"""
import os, subprocess, sys

os.chdir(os.path.dirname(os.path.abspath(__file__)))

print("=" * 52)
print("  Smart Attendance System")
print("=" * 52)

if not os.path.exists("attendance.db"):
    print("\n📦 First run — setting up demo database...")
    subprocess.run([sys.executable, "seed.py"], check=False)

print("\n🚀 Starting server → http://localhost:8000")
print("   Press Ctrl+C to stop.\n")
subprocess.run([sys.executable, "-m", "uvicorn", "main:app",
                "--reload", "--host", "0.0.0.0", "--port", "8000"])
