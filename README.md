# 🚀 Django Semi-Hackathon: Civiqo – Elective Opt-In System

## 📋 Project Details
- **Theme**: THEME-03: Elective Choice System  
- **Team Members**: Rakesh B, Pavankalyan V, JM Prajwal, Partha H.C
- **Live URL**: https://sjbit-elective.onrender.com/

---

## 📌 Project Overview

This project is a **Professional Elective Management System** designed for academic institutions like SJBIT. It allows students to select electives based on preferences and ensures fair allocation using a **First-Come-First-Served (FCFS)** algorithm.

The system provides:
- Real-time seat tracking  
- Automated allocation  
- CSV-based data management  
- Admin dashboard for control and monitoring  

---

## ✅ Submission Checklist

- [x] Code runs with `pip install -r requirements.txt`  
- [x] `DEBUG=False` configured  
- [x] Working AJAX endpoint (real-time seat updates)  
- [x] CSV/PDF export functional  
- [x] CO-SDG mapping table completed  
- [x] SDG justification included  

---

## 🎯 CO-SDG Mapping Table

| Course Outcome | How This Project Demonstrates It | SDG Target |
|---------------|--------------------------------|------------|
| CO1: MVT Architecture | Uses Django MVT structure for modular design | SDG 4.5 |
| CO2: Models & Forms | Structured models and validated forms | SDG 9.5 |
| CO3: Frontend Integration | AJAX-based real-time updates | SDG 9.c |
| CO4: Data Handling | CSV import/export for scalability | SDG 4.3 |
| CO5: System Design | FCFS allocation with waitlist system | SDG 8.2 |

---

## 🌍 SDG Justification

This project supports **SDG 4 (Quality Education)** by providing a transparent and fair elective allocation system. The FCFS-based mechanism ensures equal opportunity and eliminates bias in course selection.

It also contributes to **SDG 9 (Industry, Innovation, and Infrastructure)** by implementing a scalable digital platform that automates academic processes. CSV-based data handling reduces manual workload, while real-time updates improve efficiency.

Overall, the system enhances institutional productivity, promotes inclusive learning, and modernizes educational infrastructure.

---

## ✨ Key Features

- 🎯 First-Come-First-Served allocation  
- ⚡ Real-time seat updates (AJAX)  
- 📊 CSV import system  
- 📄 PDF report generation  
- 🛠 Admin dashboard with override  
- 📱 Fully responsive UI  
- 🔄 Automatic waitlist management  

---

## 📦 Setup Instructions

```bash
git clone [your-repo-url]
cd elective_optin
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt
python manage.py migrate
python manage.py runserver
