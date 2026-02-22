# Smart Attendance System (FastAPI)

A backend-driven attendance management system built using FastAPI, SQLAlchemy, and SQLite with a simple frontend interface.

## 🚀 Features
- User login authentication (Admin / Student / Teacher)
- Attendance management system
- Database integration using SQLAlchemy
- REST API built with FastAPI
- Basic frontend using HTML
- Demo credentials supported via seed script

## 🧰 Tech Stack
- FastAPI
- Python
- SQLAlchemy
- SQLite
- Uvicorn
- HTML / JS

## 📁 Project Structure
- main.py → API routes and application entry
- models.py → Database models
- database.py → Database connection setup
- seed.py → Insert demo users
- static/ → Frontend files
- requirements.txt → Dependencies

## ⚙️ Setup & Run

### 1️⃣ Install dependencies
pip install -r requirements.txt

### 2️⃣ Seed demo data
python seed.py

### 3️⃣ Run server
uvicorn main:app --reload

### 4️⃣ Open in browser
http://127.0.0.1:8000

## 🔐 Demo Login
Check DEMO_CREDENTIALS.txt for sample users.

## 🎯 Purpose
This project was built to learn:
- FastAPI backend development
- Database integration
- Authentication flow
- API-based architecture

## 👨‍💻 Author
Piyush Srivastava
BTech CSE (AI/ML)
