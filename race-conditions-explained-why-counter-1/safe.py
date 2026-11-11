import threading, time

counter = 0
lock = threading.Lock()

def work():
    global counter
    for _ in range(1000):
        with lock:
            tmp = counter
            time.sleep(0)
            counter = tmp + 1

ts = [threading.Thread(target=work) for _ in range(4)]
for t in ts: t.start()
for t in ts: t.join()
print("counter =", counter)
