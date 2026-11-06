# Building an O(1) LRU Cache in Python with `OrderedDict`

A cache only holds so much. Once it's full, adding something new means throwing something old out, so you need a rule for what goes. **LRU (Least Recently Used)** evicts the entry that hasn't been touched for the longest time. It's a good default because recently used data tends to be used again soon. You'll find LRU in CPU caches, database buffer pools, CDNs, and Python's own `functools.lru_cache`. It's also one of the most common coding-interview questions.

After reading this lesson you will be able to:

- explain why an LRU cache needs both fast lookup *and* fast reordering,
- build a working LRU cache with O(1) `get` and `put` in about 20 lines of Python,
- trace exactly which key gets evicted and why,
- describe the hash map + doubly linked list design interviewers expect when `OrderedDict` isn't allowed.

## The concept

An LRU cache supports two operations:

- `get(key)` returns the value if present (a **hit**). Otherwise it reports a **miss**, here by returning `-1`. A hit also counts as a *use*.
- `put(key, value)` inserts or updates the key, which also counts as a use. If the cache is now over capacity, it evicts the least recently used key.

So the cache must answer two questions quickly:

1. *Is this key here, and what is its value?* A **hash map** answers this in O(1).
2. *Which key was used longest ago, and how do I mark a key as just used?* A **recency order** that you can reorder in O(1) answers this.

A plain list can track the order, but moving an element from the middle to the end costs O(n). The classic solution is a **doubly linked list**. Each node knows its previous and next neighbour, so you can unlink it in O(1). The hash map stores *key → node*, so you never have to search the list.

```
 hash map:  { A: ●, B: ●, C: ● }      (each ● points at a list node)
                 │     │     │
 list:   [oldest] B <-> C <-> A [newest]
          ^ evict from here      ^ append / move here on every use
```

Python's `collections.OrderedDict` is exactly this structure: a dict combined with a doubly linked list that records key order. It gives you two O(1) operations:

- `move_to_end(key)` moves an existing key to the "newest" end (it raises `KeyError` if the key is missing).
- `popitem(last=False)` removes and returns the item at the "oldest" end (FIFO order). The default, `last=True`, pops from the newest end (LIFO).

**Complexity:** `get` and `put` are both O(1) on average (hash-based), and space is O(capacity).

**Trade-offs:** `OrderedDict` uses more memory than a plain `dict` because it maintains extra ordering links. LRU also needs bookkeeping on *every read*, so even a lookup mutates the structure. Two consequences follow: you need a lock if several threads share the cache, and a single large scan of one-off keys can flush your useful entries. That scan problem is why variants like LFU or segmented LRU exist.

## Walking through the code

Here is the entire program, [`lru.py`](lru.py), split into small chunks.

```python
from collections import OrderedDict
```

This imports `OrderedDict` from the standard library's `collections` module. You don't need a third-party package.

```python
class LRUCache:
    def __init__(self, capacity):
        self.capacity = capacity
        self.items = OrderedDict()
```

- `class LRUCache:` wraps the state and behaviour in one object, so you can create several independent caches.
- `self.capacity = capacity` stores the maximum number of entries. `put` checks against it later.
- `self.items = OrderedDict()` is the single structure that does both jobs: hash lookup by key and recency order. The **front** of the order holds the least recently used key and the **back** holds the most recently used one.

```python
    def get(self, key):
        if key not in self.items:
            return -1
        self.items.move_to_end(key)
        return self.items[key]
```

- `if key not in self.items:` is an O(1) hash membership test.
- `return -1` signals a miss. This follows the common interview convention (LeetCode's LRU problem uses `-1`). Note that the cache order is not touched on a miss.
- `self.items.move_to_end(key)` marks the key as most recently used. It has to run *before* returning, because a read is a use. Without this line you would have a FIFO cache, not an LRU cache. The membership check above matters here too, because `move_to_end` raises `KeyError` on a missing key.
- `return self.items[key]` returns the value. Moving a key doesn't change its value, so reading it after the move is fine.

```python
    def put(self, key, value):
        self.items[key] = value
        self.items.move_to_end(key)
        if len(self.items) > self.capacity:
            self.items.popitem(last=False)
```

- `self.items[key] = value` inserts or updates. This is subtle: a **new** key is appended at the end, but **updating an existing** key keeps its original position in an `OrderedDict`.
- `self.items.move_to_end(key)` fixes that subtlety by moving updated keys to the end too, because writing counts as using. For a brand-new key it's a harmless no-op.
- `if len(self.items) > self.capacity:` checks for overflow *after* inserting. Because each `put` adds at most one key, a single eviction is always enough to get back to capacity. An update never grows the dict, so it never evicts.
- `self.items.popitem(last=False)` removes the front item, which is the least recently used key. `last=False` is essential here, because the default `last=True` would evict the newest item.

```python
cache = LRUCache(2)
cache.put("A", 1)
cache.put("B", 2)
print(cache.get("A"))
cache.put("C", 3)
print(cache.get("B"))
```

This is the demo. It creates a two-slot cache, fills it with `A` and `B`, reads `A` (a hit, which makes `A` the most recent), then adds `C` to force an eviction, and finally reads `B` to see whether it survived.

## Run it yourself

**Prerequisites:** Python 3.12 or newer. (The code uses only long-standing standard-library features, so older Python 3 versions also work.)

From this folder, run:

```sh
python lru.py
```

The real output:

```text
1
-1
```

Step-by-step trace (order shown oldest → newest):

| Step | Call | Order after | Printed |
|------|------|-------------|---------|
| 1 | `LRUCache(2)` | `[]` | |
| 2 | `put("A", 1)` | `[A]` | |
| 3 | `put("B", 2)` | `[A, B]` | |
| 4 | `get("A")` (hit, A moved to end) | `[B, A]` | `1` |
| 5 | `put("C", 3)` → size 3 > 2 → `popitem(last=False)` removes **B** | `[A, C]` | |
| 6 | `get("B")` (miss) | `[A, C]` | `-1` |

The key moment is step 4. If you hadn't read `A`, it would still be the oldest and step 5 would have evicted `A` instead. `B` lost because it was the least recently *used*, even though `A` was inserted first.

## Try it

1. **Remove the read.** Delete `print(cache.get("A"))` and add `print(cache.get("A"))` at the end. Predict: `-1` for `A`, and `B` now returns `2`. *Lesson:* without the access, insertion order decides who gets evicted.
2. **Break LRU into FIFO.** Comment out `self.items.move_to_end(key)` in `get`. Run the original demo. Predict: `1`, then `2`, because `A` gets evicted instead of `B`. *Lesson:* that one line is the difference between LRU and FIFO.
3. **Update counts as use.** Replace the `get("A")` line with `cache.put("A", 10)`, then print `cache.get("A")` and `cache.get("B")` at the end. Predict: `10` and `-1`. Next, also remove `move_to_end` from `put` and predict again: `-1` and `2`. *Lesson:* assigning to an existing `OrderedDict` key does not move it.
4. **Flip the eviction end.** Change `popitem(last=False)` to `popitem()`. Predict: adding `C` evicts `C` itself, since it's the newest, so `get("B")` returns `2`. *Lesson:* `last=True` is LIFO, which is the wrong end for LRU.
5. **Inspect the order.** Add `print(list(cache.items))` after every call to see the oldest → newest order change in real time, and check it against the trace table above.

## Common pitfalls

- **Forgetting that reads are writes.** Every hit must reorder. If you skip it, you've built FIFO.
- **Forgetting that updates are uses.** `d[key] = value` on an existing key keeps its old position in `OrderedDict`, so you need `move_to_end` afterwards.
- **Wrong `popitem` end.** `popitem()` defaults to `last=True` and evicts the newest entry.
- **Ambiguous `-1`.** If `-1` can be a legitimate stored value, a miss and a hit look the same. In real code, return `None`, use a sentinel object, or raise `KeyError`.
- **Edge capacities.** With `capacity=0`, every `put` inserts and then immediately evicts. That's harmless, but validate the argument if 0 or negative values make no sense for your use case.
- **Thread safety.** `get` mutates the structure, so concurrent access needs a `threading.Lock` around both methods.
- **Using a plain `dict`.** Since Python 3.7, `dict` preserves insertion order, but it has no `move_to_end` or `popitem(last=False)`. You can emulate them with `value = d.pop(key); d[key] = value` and `next(iter(d))`. It works, but `OrderedDict` states the intent more clearly.
- **Memoizing functions?** Don't hand-roll a cache. Use the built-in `functools.lru_cache` decorator.

**Interview follow-ups:**

- *"Implement it without `OrderedDict`."* Use a dict mapping key → node, plus a doubly linked list with dummy `head` and `tail` sentinel nodes, so you never need special cases for an empty list. `get`: look up the node, unlink it, re-insert it next to the newest end. `put`: update or create the node, move it to the newest end, and if you're over capacity, unlink the node at the oldest end and `del` its key from the dict. That's why each node must store its key as well as its value.
- *"Why doubly linked, not singly?"* Unlinking a node in O(1) requires access to its predecessor.
- *"What's the complexity?"* O(1) average for both operations, and O(capacity) space.
- *"How would you make it thread-safe or add a time-to-live (TTL)?"* Add a lock, and store a timestamp with each value that you check on `get`.

## Further reading

- [`collections.OrderedDict`, Python docs](https://docs.python.org/3/library/collections.html#collections.OrderedDict)
- [`functools.lru_cache`, Python docs](https://docs.python.org/3/library/functools.html#functools.lru_cache)
- [Mapping types: `dict`, Python docs](https://docs.python.org/3/library/stdtypes.html#mapping-types-dict)

<!-- studio-job: build-an-lru-cache-in-python-in-20-lines -->
