# Why `counter += 1` Breaks With Threads: A Python Race Condition, Explained and Fixed

Four threads each add 1 to a shared counter 1,000 times. You'd expect 4,000. In this demo you get **1,000**, so three quarters of the work is lost. Nothing raises an error and nothing crashes. The updates are simply gone.

This bug is called a **race condition**, and specifically a **lost update**. It matters because it's silent. It shows up in hit counters, account balances, inventory counts, rate limiters, and database rows, and it often passes every test until production load arrives.

After reading this you will be able to:

- explain why `counter += 1` is not atomic, and prove it with `dis`;
- predict how interleaved threads lose updates;
- fix the bug with `threading.Lock` and keep the locked section small;
- answer the usual interview follow-ups, including the database version of the same bug.

## The concept

### Read-modify-write is three steps, not one

`counter += 1` looks like a single operation, but the interpreter performs three:

1. **Read** the current value of `counter`.
2. **Modify** it by computing value + 1.
3. **Write** the result back to `counter`.

Python's bytecode disassembler shows this directly. `LOAD_NAME` reads, `BINARY_OP (+=)` adds, and `STORE_NAME` writes. They are separate instructions, and a thread switch can happen between any two of them.

### How an update vanishes

Suppose two threads, A and B, share `counter = 5`:

```text
time   Thread A              Thread B              counter
----   -------------------   -------------------   -------
 t1    read  -> 5                                     5
 t2                          read  -> 5               5
 t3    add   -> 6                                     5
 t4                          add   -> 6               5
 t5    write 6                                        6
 t6                          write 6                  6   <- should be 7
```

Both threads did their work, but B's write overwrote A's with the same value. One increment is lost. The two writes don't conflict in any detectable way, so nothing warns you.

### "But Python has the GIL..."

CPython's Global Interpreter Lock (GIL) means only one thread runs Python bytecode at a time. That does **not** make multi-step operations atomic. The interpreter can switch threads between bytecodes, and any blocking call such as `time.sleep` releases the GIL voluntarily. The GIL protects the interpreter's own internals. It does not protect your invariants.

### The fix: mutual exclusion

A **lock** (mutex) is held by at most one thread at a time. If you wrap the whole read-modify-write in the lock, it becomes a **critical section**: no other thread can read `counter` until the current thread has written its new value back. The bad interleaving in the table above can no longer happen.

```text
Thread A: [acquire][read 5][add][write 6][release]
Thread B:                                          [acquire][read 6][add][write 7][release]
```

### Cost and trade-offs

- **Time:** each increment is still O(1). A lock adds an acquire/release on every iteration, and threads that find it held must wait. That waiting is called *contention*. The work inside a critical section is effectively serial, so the 4 × 1,000 increments run one at a time.
- **Space:** a single `Lock` object, O(1).
- **Trade-off:** you get correctness, but you lose parallelism inside the locked region. Keep critical sections as small as possible: lock only the shared-state access, not unrelated slow work.
- **Alternatives:** give each thread its own local count and combine the counts at the end (no sharing, so no lock is needed), use a thread-safe `queue.Queue`, or in databases push the increment into one atomic statement.

## Walking through the code

### [`race.py`](race.py): the broken version

```python
import threading, time

counter = 0
```

- `threading` provides OS-level threads. `time` provides `sleep`.
- `counter = 0` is a module-level global, so every thread sees the same object. This is the shared state.

```python
def work():
    global counter
    for _ in range(1000):
        tmp = counter
        time.sleep(0)
        counter = tmp + 1
```

- `global counter` tells Python that assignments inside `work` refer to the module-level `counter`. Without it, `counter = ...` would create a local variable and `tmp = counter` would raise `UnboundLocalError`.
- `for _ in range(1000):` runs 1,000 increments per thread. `_` signals that the loop variable is unused.
- `tmp = counter` is the **read** step, made explicit in a local variable.
- `time.sleep(0)` asks to sleep for zero seconds. It still releases the GIL and gives other threads a chance to run, which deliberately widens the gap between read and write. Without it, the race still exists but shows up much less often, which is exactly why these bugs survive testing.
- `counter = tmp + 1` is the **modify** and **write** steps. If another thread wrote to `counter` since our read, that write is overwritten with a stale value.

This is `counter += 1` spelled out by hand so you can see where the gap is.

```python
ts = [threading.Thread(target=work) for _ in range(4)]
for t in ts: t.start()
for t in ts: t.join()
print("counter =", counter)
```

- The list comprehension creates four `Thread` objects that will each run `work`. Creating a thread does not start it.
- `t.start()` launches each thread. From here on, they run concurrently.
- `t.join()` blocks the main thread until each worker finishes. Without the joins, `print` could run before the work is done and show a partial count, which would be a different bug.
- `print("counter =", counter)` reports the final total. `print` separates its arguments with a space, so the output is `counter = N`.

### [`safe.py`](safe.py): the fixed version

```python
import threading, time

counter = 0
lock = threading.Lock()
```

- The setup is the same as before, plus one shared `Lock`. It must be a **single** lock shared by all threads. If each thread created its own lock, they would never block each other.

```python
def work():
    global counter
    for _ in range(1000):
        with lock:
            tmp = counter
            time.sleep(0)
            counter = tmp + 1
```

- `with lock:` acquires the lock on entry and releases it on exit, even if an exception is raised inside the block. That guarantee is why `with` is preferred over manual `lock.acquire()` / `lock.release()`.
- The read, the yield, and the write are all inside the block. `time.sleep(0)` still yields the GIL, but any other thread that runs just blocks at `with lock:` until the holder releases it. The yield is now harmless.
- The `for` loop is outside the lock. Each increment holds the lock briefly, so the critical section stays small.

```python
ts = [threading.Thread(target=work) for _ in range(4)]
for t in ts: t.start()
for t in ts: t.join()
print("counter =", counter)
```

This is identical to `race.py`: start four threads, wait for all of them, print the total. The only change between the two files is the lock.

## Run it yourself

**Prerequisites:** Python 3.12 or newer. Nothing else is needed; both files use only the standard library.

From this folder, run:

```sh
python -c "import dis; dis.dis('counter += 1')"
python race.py
python race.py
python safe.py
python safe.py
```

Real output:

```text
0           0 RESUME                   0

  1           2 LOAD_NAME                0 (counter)
              4 LOAD_CONST               0 (1)
              6 BINARY_OP               13 (+=)
             10 STORE_NAME               0 (counter)
             12 RETURN_CONST             1 (None)
```

```text
counter = 1000
```

```text
counter = 1000
```

```text
counter = 4000
```

```text
counter = 4000
```

### Why exactly these numbers

**The disassembly.** `dis.dis` compiles the string `'counter += 1'` as module-level code, which is why you see `LOAD_NAME` and `STORE_NAME` instead of `LOAD_GLOBAL` and `STORE_GLOBAL`.

- `RESUME` is a bookkeeping instruction.
- `LOAD_NAME` pushes the current value. This is the **read**.
- `LOAD_CONST` pushes `1`.
- `BINARY_OP 13 (+=)` computes the sum. This is the **modify**.
- `STORE_NAME` saves it. This is the **write**.
- `RETURN_CONST None` ends the module code.

The offset jumps from 6 to 10 because `BINARY_OP` is followed by an inline cache entry. Three separate instructions do the actual work, so there are two places where a thread switch can split them.

**`race.py` prints 1000.** `time.sleep(0)` makes every thread give up the GIL right after reading. The threads therefore tend to take turns in a round-robin pattern:

```text
A reads 0, sleeps -> B reads 0, sleeps -> C reads 0, sleeps -> D reads 0, sleeps
A writes 1, loops, reads 1, sleeps
B writes 0+1 = 1, reads 1, sleeps
C writes 1, reads 1, sleeps
D writes 1, reads 1, sleeps
A writes 2, ...
```

In each round, all four threads read the same value and all four write that value + 1, so four increments collapse into one. After 1,000 rounds the counter is 1,000: exactly one thread's worth of work survives. In these runs the scheduling was regular enough that both runs printed exactly 1000. On another machine, OS, or Python build, the switches may land differently, and you may see other values somewhere between 1,000 and 4,000 that vary from run to run. Any result other than 4,000 is the bug.

**`safe.py` prints 4000.** With the lock, each read-sleep-write runs to completion before any other thread can read. There are 4 threads × 1,000 increments, none of them lost, so the total is 4,000 every time.

## Try it

1. **Remove the yield.** Delete `time.sleep(0)` from `race.py` and run it several times. *Predict:* the result is often 4000, or close to it. *Learn:* the race is still there, but the window is tiny and thread switches seldom land inside it. "My test passed" doesn't prove the code is thread-safe.
2. **Use `+=` directly.** Replace the three loop-body lines with `counter += 1`, raise the loop count to `1_000_000`, and run it a few times. *Learn:* depending on your Python version, the shorter form may lose fewer updates or none in a given run, but it's still three bytecodes and is not guaranteed atomic.
3. **Lock too much.** In `safe.py`, move `with lock:` above the `for` loop so each thread holds the lock for its whole loop. *Predict:* still 4000. *Learn:* the code is correct but fully serialized, because threads run one after another. Wrap both versions with `time.perf_counter()` to compare timings, and read the result as a lesson about the size of critical sections.
4. **One lock per thread.** Move `lock = threading.Lock()` inside `work()`. *Predict:* the count goes wrong again, close to `race.py`. *Learn:* a lock only protects data if every thread that touches the data uses the *same* lock.
5. **No sharing at all.** Have each thread count into a local variable and append it to a shared list at the end, then `print(sum(results))` after the joins. *Learn:* avoiding shared mutable state is often better than locking it. `list.append` is a single operation in CPython, but a `Lock` around it is the portable choice.

## Common pitfalls

- **Assuming the GIL makes your code thread-safe.** It doesn't. It only makes individual bytecodes run one at a time, and your logic usually spans several.
- **Locking only the write.** `tmp = counter` outside the lock with `counter = tmp + 1` inside it still loses updates. The *whole* read-modify-write must be inside the critical section.
- **Different locks for the same data.** Two locks guarding one variable protect nothing.
- **Forgetting `join()`.** Reading the result before the threads finish gives a partial count, which looks like a race but isn't one.
- **Doing slow work under the lock.** I/O or heavy computation inside `with lock:` makes every other thread wait. Compute outside the lock and update shared state inside it.
- **Re-acquiring a `Lock` in the same thread.** `threading.Lock` is not reentrant, so a second `acquire` from the thread that already holds it deadlocks. Use `threading.RLock` if you need nested acquisition.
- **Trusting a passing run.** Races depend on timing. One correct result proves nothing.

**Interview follow-ups:**

- *Why is `counter += 1` not thread-safe?* It's a non-atomic read-modify-write. Protect it with a lock or an atomic operation.
- *How would you fix it without a lock?* Remove the sharing: give each thread a local counter and merge with `sum` after `join()`. Alternatively, send increments through a `queue.Queue` to a single owner thread. With processes, use `multiprocessing.Value` together with its `get_lock()`.
- *Where else does this show up?* In databases, as the **lost update**: two transactions read `count = 5` and both write 6. Fix it with `SELECT ... FOR UPDATE` to lock the row while you read it, or with a single atomic statement such as `UPDATE t SET count = count + 1 WHERE id = ...`, so the read and write happen together in the database.
- *Lock vs. atomic operation?* An atomic operation (hardware compare-and-swap, a single SQL `UPDATE`) does the read and write as one indivisible step and has no lock to hold. A lock is more general and can protect a multi-step invariant.

## Further reading

- [`threading`: Thread-based parallelism (Lock objects)](https://docs.python.org/3/library/threading.html#lock-objects)
- [`dis`: Disassembler for Python bytecode](https://docs.python.org/3/library/dis.html)
- [Glossary: global interpreter lock](https://docs.python.org/3/glossary.html#term-global-interpreter-lock)
- [PostgreSQL: Explicit Locking (`SELECT ... FOR UPDATE`)](https://www.postgresql.org/docs/current/explicit-locking.html)

<!-- studio-job: race-conditions-explained-why-counter-1-from-multiple-thread -->
