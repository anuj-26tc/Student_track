StudentTrack - Student Skill Development and Academic Progress Tracking Platform

PROJECT PURPOSE
One place for academic progress and practical skill growth.
Teachers manage the official marks and attendance. Students manage their own skills,
projects and learning goals. The website gives each student simple advice (recommendations).

HOW TO RUN
1. Install Python 3.10 or newer (tick "Add Python to PATH").
2. Open Command Prompt inside this folder and type:  pip install -r requirements.txt
3. Start the website:  python app.py   (or double click start.bat)
4. Open http://127.0.0.1:5000 in Chrome. The first page is the student login page.

TEACHER LOGIN
Open http://127.0.0.1:5000/teacher
First teacher id: teacher     First password: teacher123
Change the password after the first login (Change Password in the top bar).

AUTOMATIC TESTS
python -m unittest test_app -v
The tests use a temporary database. Your real students.db is not touched.

OTHER FILES
loadtest.py   sends many requests at the same time (start the website first)
indextest.py  shows how much faster a database index makes a search

FEATURES
Student:
- Dashboard with academic average, attendance, skills and projects
- Recommendations from marks, attendance, skills, projects and goals
- Read-only academic records (marks out of 120) and attendance with Safe / Low status
- Skills with category, level, progress and note (a skill can be added only once)
- Project portfolio, learning goals with target dates
- Growth report page (print or save as PDF from the browser)
- Profile edit (name, father's name, mobile, email) and change password
Teacher:
- Dashboard: total students, class average, need attention, low attendance
- Search a student, open the records, download the class report as a CSV file
- Add, update and delete marks (Mid-Sem 30, End-Sem 70, Internal/Lab 20)
- Add, update and delete attendance
- Change the level of a student's skill
- Write feedback remarks, change the teacher password

SAFETY
- Passwords are saved in hashed form
- The login cookie key is made at random and saved in secret_key.txt (not put on GitHub)
- Students cannot open teacher pages and teachers cannot open student pages
- Every text box has a length limit and every number is checked on the server
- students.db and secret_key.txt are listed in .gitignore, so student data is not put on GitHub

DATABASE
The website makes students.db by itself the first time it starts and upgrades an old one safely.
Tables: users, skills, marks (old, kept only for the one-time upgrade), remarks,
academic_records, attendance, projects, learning_goals, teacher_account.

PUT THE WEBSITE ON THE INTERNET (Render, free)
Build command : pip install -r requirements.txt
Start command : gunicorn app:app
Environment variables to set on Render:
  STUDENTTRACK_SECRET_KEY        any long random text (keeps the login cookie safe)
  STUDENTTRACK_TEACHER_PASSWORD  the teacher password for the public website (do not use teacher123)
  STUDENTTRACK_DEMO              1  (makes 3 demo students: DEMO101, DEMO102, DEMO103, password demo1234)
  STUDENTTRACK_DEMO_PASSWORD     optional, a different password for the demo students
Important: a free Render service forgets its database whenever it restarts, redeploys or sleeps
(it sleeps after 15 minutes without visitors and needs about one minute to wake up).
So the public website is for demonstration only. Do not type real student details on it.
