import signal, sys, time

stop = False

def handle(sig, frame):
    global stop
    stop = True

signal.signal(signal.SIGTERM, handle)

n = 0
while not stop:
    n += 1
    print(f"task {n} start", flush=True)
    time.sleep(1)
    print(f"task {n} done", flush=True)

# close connections, flush data here
print("goodbye, exiting cleanly", flush=True)
sys.exit(0)
