import urllib.request
import threading
import time

URL = "http://127.0.0.1:5000/"
USERS = 100       # how many users at the same time

times = []
errors = []


def one_user():
    start = time.time()
    try:
        urllib.request.urlopen(URL)
        times.append(time.time() - start)
    except Exception:
        errors.append(1)


all_threads = []
begin = time.time()

for i in range(USERS):
    t = threading.Thread(target=one_user)
    all_threads.append(t)
    t.start()

for t in all_threads:
    t.join()

total = time.time() - begin

print("Users:", USERS)
print("Success:", len(times))
print("Failed:", len(errors))
if len(times) > 0:
    print("Average time:", round(sum(times) / len(times), 3), "seconds")
    print("Slowest time:", round(max(times), 3), "seconds")
print("Total time:", round(total, 2), "seconds")