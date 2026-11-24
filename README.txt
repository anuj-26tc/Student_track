StudentTrack — Student Skill Development and Academic Progress Tracking Platform

PROJECT PURPOSE
A unified platform for tracking academic progress and practical skill development.
Teachers manage official marks and attendance. Students manage their own skills,
learning goals and practical project portfolio.

RUN THE PROJECT
1. Install Python 3.10 or newer.
2. Open Terminal / Command Prompt inside this project folder.
3. Install dependencies:  pip install -r requirements.txt
4. Start the app:        python app.py
5. Open:                 http://127.0.0.1:5000

TEACHER LOGIN
URL: http://127.0.0.1:5000/teacher
First teacher ID: teacher
First password: teacher123
Change this password after your first login.

FEATURES
Teacher Panel:
- Search/select students by roll or enrollment number.
- Add/update subject-wise Mid-Sem (30), End-Sem (70) and Internal/Lab (20) marks.
- Add/update subject-wise total classes held and classes attended.
- View student skills and project portfolio (read-only).
- Add academic guidance remarks.

Student Dashboard:
- Read-only academic records and subject-wise attendance.
- Automatic marks total out of 120 and percentage calculation.
- Attendance status: Safe at 75% or above; Low below 75%.
- Academic performance bars/analytics.
- Add/update/delete skills, with category, proficiency, progress and learning note.
- Add/update/delete practical projects with technologies, description, link and status.
- Add/delete learning goals and mark goals complete.
- Combined Student Growth Report; use Print / Save as PDF in the browser.

SCOPE DECISIONS
- Removed student self-entry/edit/delete of official marks. Teachers alone manage official marks.
- Students cannot edit official attendance.
- Kept teacher remarks as academic guidance.
- Fee, transport, library and unrelated college administration features are not included.

DATABASE NOTE
The app creates/migrates students.db automatically when it starts. Existing student
accounts and records are preserved. Back up students.db before upgrading. The app keeps
legacy marks data only for migration compatibility; the student interface no longer
allows students to change official marks.
