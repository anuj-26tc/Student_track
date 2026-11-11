import sqlite3
import time

db = sqlite3.connect("test.db")
db.execute("DROP TABLE IF EXISTS marks")
db.execute("CREATE TABLE marks (id INTEGER PRIMARY KEY AUTOINCREMENT, enrollment TEXT, subject TEXT, marks INTEGER)")

# add 100000 fake rows
for i in range(100000):
    db.execute("INSERT INTO marks (enrollment, subject, marks) VALUES (?, ?, ?)", ("EN" + str(i), "Maths", 50))
db.commit()


def test():
    start = time.time()
    for i in range(100):
        db.execute("SELECT * FROM marks WHERE enrollment = 'EN99999'").fetchall()
    return round(time.time() - start, 4)


print("Without index:", test(), "seconds")
db.execute("CREATE INDEX idx ON marks(enrollment)")
print("With index:", test(), "seconds")
db.close()