# `kill` vs `kill -9`: Graceful Shutdown with SIGTERM in Python

Every long-running program is eventually told to stop: during a deploy, when a machine reboots, or when you get impatient in a terminal. How it is stopped decides whether it finishes the job it is doing or leaves half-written files, unacknowledged messages and open transactions behind.

`kill` and `kill -9` look almost the same, but they do very different things. Plain `kill` *asks* the process to stop. `kill -9` makes the kernel remove it on the spot. This lesson explains the difference from the ground up, then walks through a 20-line Python worker that catches the polite request and finishes its current task before it exits.

When you finish, you will be able to:

- explain what SIGTERM, SIGKILL and SIGINT are and which of them a program can catch,
- write a Python process that shuts down cleanly when it receives SIGTERM,
- explain why the exit codes are `0` and `137`, and why the output stops where it does.

## The concept

### Signals in one paragraph

A **signal** is a small, numbered notification that the kernel delivers to a process. Each signal has a *default action*, which is usually "terminate the process". For most signals a process can replace that default by installing a **handler**, a function that runs when the signal arrives. Two signals are special: **SIGKILL (9)** and **SIGSTOP** cannot be caught, blocked or ignored. The kernel acts on them directly and your code never finds out.

| How you send it | Signal | Number | Catchable? | Default action |
|---|---|---|---|---|
| `kill PID` | SIGTERM | 15 | yes | terminate |
| `kill -9 PID` | SIGKILL | 9 | **no** | terminate immediately |
| Ctrl+C in a terminal | SIGINT | 2 | yes | terminate (Python raises `KeyboardInterrupt`) |

So `kill` without a number means `kill -15`, or `kill -TERM`. It is a request. `kill -9` is an order, and the process gets no chance to clean up.

### The graceful-shutdown pattern

When a signal arrives, the handler interrupts the program at whatever line it happens to be running. Doing real cleanup inside the handler is risky, because you might be halfway through a write. The standard pattern keeps the handler tiny:

1. The handler only **sets a flag** (`stop = True`).
2. The main loop **checks the flag between units of work**.
3. When the loop sees the flag it exits, and the code after the loop does the cleanup: closing connections, flushing buffers, and so on.

```
 time ─────────────────────────────────────────────────────────▶
 main loop:  [ task 1 ][ task 2 ][ task 3 ......... ] check flag → exit → cleanup
                                      ▲
                               SIGTERM arrives
                               handler: stop = True   (returns immediately)
```

The current task is never cut in half. Shutdown happens only at a boundary you chose.

### Cost and trade-offs

- **Time/space:** handling a signal costs O(1). It is one flag write, plus one boolean check per loop iteration.
- **Shutdown latency** is at most the length of one unit of work plus the cleanup time. If a single task can take minutes, the process will be slow to stop.
- **Grace periods:** service managers and orchestrators usually send SIGTERM, wait for a fixed grace period, then send SIGKILL. Your shutdown has to fit inside that window, or it ends up as a `kill -9` anyway.
- **Wrappers:** a signal goes to one PID. If your program is started by a shell script that does not forward signals (or `exec` the program), the shell receives the SIGTERM and your handler never runs.

## Walking through the code

The whole program is [`worker.py`](worker.py). Let's go through it in chunks.

```python
import signal, sys, time
```

- `signal` is the standard-library interface to POSIX signals: `signal.signal()` and constants such as `signal.SIGTERM`.
- `sys` gives us `sys.exit()`, so the exit status is set explicitly.
- `time` provides `time.sleep()`, which stands in for real work.

```python
stop = False
```

This is the module-level **stop flag**. It starts as `False` because nobody has asked us to stop yet. A plain boolean is enough: in CPython, signal handlers always run in the main thread, between bytecode instructions, so the handler and the loop never write it at the same moment.

```python
def handle(sig, frame):
    global stop
    stop = True
```

- Python calls a signal handler with two arguments: the signal number (`sig`) and the current stack frame (`frame`). We need neither, but the signature has to accept both.
- `global stop` is required. Without it, `stop = True` would create a new local variable and the module-level flag would stay `False`.
- The handler does **only** this one assignment. It does not print, exit or clean up. The main loop owns all of that, so shutdown always happens at a safe point.

```python
signal.signal(signal.SIGTERM, handle)
```

This installs `handle` as the handler for SIGTERM, replacing the default "terminate" action. From here on, `kill PID` no longer kills the process. It only flips the flag. Notice that nothing is registered for SIGKILL. Python would raise an `OSError` if you tried, because the kernel does not allow it.

```python
n = 0
while not stop:
    n += 1
    print(f"task {n} start", flush=True)
    time.sleep(1)
    print(f"task {n} done", flush=True)
```

- `n` counts tasks so the output shows exactly which task was running when a signal arrived.
- `while not stop:` checks the flag **only at the top of each iteration**. This is the boundary between units of work.
- The body is a fake one-second task. It prints `start`, does its "work" (`sleep(1)`) and prints `done`.
- `flush=True` matters. When stdout is a pipe or file instead of a terminal, Python buffers output, and a SIGKILL would throw away whatever is still in the buffer. Flushing each line means you see exactly how far the program got.
- If SIGTERM arrives during `time.sleep(1)`, the handler runs and returns. Since Python 3.5 (PEP 475), `sleep` then continues for the rest of its time instead of raising an error, so the task really does finish.

```python
# close connections, flush data here
print("goodbye, exiting cleanly", flush=True)
sys.exit(0)
```

- Execution reaches this point only after the loop sees `stop == True`. In a real service, this is where you close database connections, commit offsets, flush logs and remove temp files.
- The goodbye line is the proof that cleanup ran.
- `sys.exit(0)` reports success to the parent process. A clean, requested shutdown is not an error.

## Run it yourself

**Prerequisites:** Python 3.12 or newer, on Linux or macOS (or any POSIX shell that has `kill`).

Run these from the folder that contains `worker.py`:

```sh
(python worker.py & sleep 2.5; kill $!; wait $!; echo "exit=$?")
(python worker.py & sleep 2.5; kill -9 $!; wait $!; echo "exit=$?")
```

Each line starts the worker in the background (`&`), waits 2.5 seconds, sends a signal to the background PID (`$!`), waits for the process to end, and prints its exit status (`$?`).

**Output with `kill` (SIGTERM):**

```text
task 1 start
task 1 done
task 2 start
task 2 done
task 3 start
task 3 done
goodbye, exiting cleanly
exit=0
```

Step by step:

1. t≈0s: `task 1 start`, sleep. t≈1s: `task 1 done`. The flag is still `False`, so `task 2 start` follows.
2. t≈2s: `task 2 done`, `task 3 start`, sleep.
3. t≈2.5s: SIGTERM arrives in the middle of the sleep. `handle` sets `stop = True` and returns, and the sleep continues.
4. t≈3s: `task 3 done`. Task 3 finished even though the signal arrived partway through it.
5. The `while not stop` check is now false, so the loop ends. `goodbye, exiting cleanly` is printed, `sys.exit(0)` runs, and `wait` reports `exit=0`.

**Output with `kill -9` (SIGKILL):**

```text
task 1 start
task 1 done
task 2 start
task 2 done
task 3 start
exit=137
```

Steps 1 and 2 are the same. At t≈2.5s the kernel ends the process immediately. No Python code runs: no handler, no `task 3 done`, no goodbye. Task 3 is left half-done. The shell reports a process killed by signal *N* as `128 + N`, so SIGKILL (9) gives `exit=137`.

## Try it

1. **Remove the handler.** Comment out the `signal.signal(...)` line and run the `kill` command again. *Predict:* output stops after `task 3 start`, with no goodbye, and the exit status is `143` (128 + 15). *Lesson:* without a handler, SIGTERM's default action is as abrupt as `kill -9`. The difference only exists if you catch the signal.
2. **Press Ctrl+C.** Run `python worker.py` in the foreground and press Ctrl+C during a task. *Predict:* a `KeyboardInterrupt` traceback from inside `time.sleep`, with no goodbye. Then add `signal.signal(signal.SIGINT, handle)` and try again. *Lesson:* SIGINT is a separate signal, and Python's default turns it into an exception. Registering the same handler makes Ctrl+C graceful too.
3. **Make the work longer.** Change `time.sleep(1)` to `time.sleep(5)` and send `kill` after 2.5 seconds. *Predict:* the goodbye is delayed until about t=5s. *Lesson:* shutdown latency is bounded by the length of one unit of work, which is why tasks should be short or able to check the flag themselves.
4. **Drop `flush=True`.** Remove it from every `print`, then run `python worker.py > out.txt & sleep 2.5; kill -9 $!` and look at `out.txt`. *Predict:* the file is likely empty, because the lines were still in Python's buffer when the process was killed. *Lesson:* buffered output (and buffered data in general) is lost on SIGKILL.
5. **Try to catch SIGKILL.** Add `signal.signal(signal.SIGKILL, handle)`. *Predict:* `OSError: [Errno 22] Invalid argument` at startup. *Lesson:* the kernel, not Python, makes SIGKILL uncatchable.

## Common pitfalls

- **Doing real work inside the handler.** Printing, taking locks or closing sockets in a handler can deadlock or corrupt state, because the handler interrupts arbitrary code. Set a flag and return.
- **Forgetting `global`.** `stop = True` without `global stop` sets a local variable, and the process never stops gracefully.
- **Expecting threads to receive signals.** In Python, handlers run only in the main thread, and `signal.signal()` can only be called from the main thread. Worker threads need their own way to hear about shutdown, such as a `threading.Event` that the main thread sets.
- **Blocking calls that never return.** A loop that blocks forever (for example on a socket read with no timeout) never gets back to checking the flag. Use timeouts so the flag is checked regularly.
- **A wrapper that swallows SIGTERM.** If a shell script starts your program without `exec`, the shell may be the process that receives SIGTERM, and it may not forward it. Start the program with `exec` so it replaces the shell and keeps its PID.
- **Exceeding the grace period.** Whatever stops your process will usually follow SIGTERM with SIGKILL after a timeout. Keep cleanup fast.

**Interview-style follow-ups:**

- *Why can't SIGKILL be caught?* So the system always has a guaranteed way to remove a misbehaving process. A process that could ignore every signal could never be stopped.
- *What does exit code 137 or 143 mean?* The process was killed by signal 9 or 15: 128 plus the signal number.
- *How would you do this without a global flag?* Use `threading.Event`: the handler calls `event.set()`, and the loop uses `while not event.is_set()`. As a bonus, `event.wait(1)` can replace `sleep(1)` and wake up as soon as shutdown is requested.
- *Could you exit directly in the handler?* `sys.exit()` in a handler raises `SystemExit` at whatever line was running. That skips the rest of the current task, which is exactly what this pattern avoids.

## Further reading

- [Python `signal` module documentation](https://docs.python.org/3/library/signal.html)
- [PEP 475: Retry system calls failing with EINTR](https://peps.python.org/pep-0475/)
- [signal(7) Linux manual page](https://man7.org/linux/man-pages/man7/signal.7.html)
- [kill(1) Linux manual page](https://man7.org/linux/man-pages/man1/kill.1.html)

<!-- studio-job: sigterm-vs-sigkill-and-graceful-shutdown-what-kill-ctrlc-doc -->
