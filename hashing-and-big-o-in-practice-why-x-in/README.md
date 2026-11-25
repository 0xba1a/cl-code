# `x in list` vs `x in set`: Why Membership Tests Go From O(n) to O(1)

`x in something` looks the same no matter what `something` is, but how long it takes depends on the type. On a list, Python checks the items one by one. On a set, Python hashes the value and jumps straight to where it would be stored. With a million items, that's the gap between milliseconds and nanoseconds. A membership test inside a loop is one of the most common reasons Python code ends up quadratic without anyone noticing.

By the end of this lesson you will be able to:

- explain why `in` is O(n) for a list and O(1) on average for a set,
- measure the difference yourself with `timeit`,
- rewrite the O(n²) nested-loop "Contains Duplicate" as a one-pass O(n) solution,
- name the caveats an interviewer expects: average vs worst case, hashable keys, and memory cost.

## The concept

### A list is a sequence: membership means scanning

A Python list is a contiguous array of references to objects. It has no idea where any particular value is, so `x in my_list` has to compare `x` with each element in order (using `==`) until one matches or the list runs out:

```text
looking for 999_999 in [0, 1, 2, ..., 999_999]

index:   0     1     2    ...   999_998   999_999
value:  [0]   [1]   [2]   ...   [999998]  [999999]
         ≠     ≠     ≠    ...      ≠         =   ← found after 1,000,000 comparisons
```

Searching for the last element (or for a value that isn't there) is the worst case: n comparisons. The time is **O(n)**.

### A set is a hash table: membership means computing an address

A `set` stores its elements in a table of slots, or buckets. To test `x in my_set`, Python:

1. calls `hash(x)` to get an integer,
2. turns that integer into a slot index (roughly `hash % table_size`),
3. looks in that slot. If the slot holds an object with the same hash and `==` is true, the answer is yes. If the slot is empty, the answer is no. If it holds something else (a collision), Python probes a few more slots in a fixed sequence.

```text
hash(999_999) ──► slot index ──► [ ... | 999_999 | ... ]   ← 1 lookup, done
```

How much work that takes doesn't depend on how many elements are in the set. It only depends on the hash and a few probes. Python resizes the table to keep it partly empty, which keeps collisions rare, so a lookup is **O(1) on average**.

### Complexity and trade-offs

| Operation             | list                  | set                                          |
|-----------------------|-----------------------|----------------------------------------------|
| `x in c`              | O(n)                  | O(1) average, O(n) worst case                |
| add an element        | `append`: O(1) amortized | `add`: O(1) average                       |
| keeps order           | yes                   | no                                           |
| allows duplicates     | yes                   | no                                           |
| element requirements  | anything              | must be hashable                             |
| memory                | one reference per item | noticeably more (table kept partly empty)   |

Sets aren't free:

- **Worst case is O(n).** If many keys land in the same slots (a bad or adversarial hash), probing degrades to a scan.
- **Keys must be hashable.** `int`, `str`, `tuple` of hashables, and `frozenset` work. `list`, `dict` and `set` raise `TypeError`.
- **Memory.** A hash table uses more memory than a list of the same items.
- **Building the set is O(n).** It only pays off if you do many lookups.

### Applying it: Contains Duplicate

The brute-force answer compares every pair:

```text
for i in range(n):
    for j in range(i + 1, n):
        if nums[i] == nums[j]: return True
```

That's n·(n−1)/2 comparisons, which is **O(n²)**. The better version remembers what it has already seen in a set and walks the list once. Each step is an O(1) average lookup plus an O(1) average insert, so the whole thing is **O(n) time, O(n) extra space**. You're spending memory to save time.

Two Sum uses the same trick with a `dict` (also a hash table): map each value to its index, and for each `x` check whether `target - x` is already in the dict.

## Walking through the code

### [`bench.py`](bench.py)

```python
import timeit
```

`timeit` is the standard-library module for timing small snippets. It uses a high-resolution clock (`time.perf_counter` by default) and runs the code many times, which smooths out noise much better than one call to `time.time()`.

```python
N = 999_999
nums = list(range(1_000_000))
seen = set(nums)
```

- `N = 999_999` is the value to look for. The underscores are just digit separators (Python 3.6+). It's the **last** element of the list, so the list search hits its worst case and scans all one million items.
- `nums` is a list of the integers 0 through 999,999.
- `seen = set(nums)` builds a set with the same million integers. Building it is O(n), but it happens once and isn't timed.

```python
tl = timeit.timeit(lambda: N in nums, number=100)
ts = timeit.timeit(lambda: N in seen, number=100)
```

- `timeit.timeit(stmt, number=100)` calls `stmt` 100 times and returns the **total** time in seconds as a float.
- The statement is passed as a `lambda` (a callable), so it can use `N`, `nums` and `seen` directly. You don't need `setup` or `globals` strings.
- `tl` is the total time for 100 list lookups and `ts` is the total for 100 set lookups. `number=100` is small because each list lookup is slow. The default of one million runs would take a very long time on the list.

```python
print(f"list: {tl/100*1e3:.3f} ms per lookup")
print(f"set:  {ts/100*1e9:.0f} ns per lookup")
```

- Dividing by 100 turns the total into the time **per lookup**.
- `*1e3` converts seconds to milliseconds, and `:.3f` prints three decimals.
- `*1e9` converts seconds to nanoseconds, and `:.0f` rounds to a whole number.
- Each line uses the unit that suits its result. Keep in mind that the units differ: ms vs ns is a factor of one million.
- The extra space after `set:` lines the two numbers up.

### [`dup.py`](dup.py)

```python
def contains_duplicate(nums):
    seen = set()
```

The function takes any iterable of hashable values. `seen` starts as an empty set. Write `set()`, not `{}`, because `{}` creates an empty **dict**.

```python
    for n in nums:
        if n in seen:
            return True
        seen.add(n)
    return False
```

- The function makes one pass over the input.
- `if n in seen:` is an O(1) average set lookup. If `n` is already there, a duplicate exists, so it returns `True` straight away. This early exit means it may never look at the rest of the input.
- Otherwise `seen.add(n)` records `n` for later iterations. The check comes **before** the add on purpose. If you added first, `n in seen` would always be true.
- If the loop finishes without a repeat, every value was distinct, so it returns `False`.

```python
print(contains_duplicate([3, 1, 4, 1]))
print(contains_duplicate([2, 7, 11, 15]))
```

There are two test cases: one with a repeated `1` and one where every value is distinct.

## Run it yourself

**Prerequisites:** Python 3.12 or newer. Both scripts use only the standard library.

```sh
python bench.py
python dup.py
```

Output from a real run:

```text
list: 5.827 ms per lookup
set:  45 ns per lookup
```

```text
True
False
```

**Why `bench.py` prints that.** The list lookup makes a million `==` comparisons before it reaches `999_999` at the last index. About 5.8 ms per lookup works out to roughly 6 ns per comparison. The set lookup hashes `999_999` (a small `int` hashes to itself), finds the slot, and compares once. Most of the 45 ns is actually the overhead of calling the lambda, not the hash lookup. 5.827 ms / 45 ns ≈ 130,000×. Your numbers will differ by machine, but the gap between the two will be similar.

**Why `dup.py` prints that.** Trace of `[3, 1, 4, 1]`:

```text
n=3  3 in {}        → no  → seen = {3}
n=1  1 in {3}       → no  → seen = {3, 1}
n=4  4 in {3,1}     → no  → seen = {3, 1, 4}
n=1  1 in {3,1,4}   → YES → return True
```

For `[2, 7, 11, 15]`, every check fails, `seen` grows to four elements, the loop ends, and the function returns `False`.

## Try it

1. **Search for the first element.** In `bench.py`, set `N = 0`. *Predict:* the list lookup drops to tens of nanoseconds, because the scan stops at index 0. *Lesson:* O(n) describes the worst case. The cost of a list scan depends on where the item is.
2. **Search for a missing value.** Set `N = -1`. *Predict:* the list time is about the same as for `999_999`, because it has to check every element before saying no. The set stays fast. *Lesson:* for lists, a miss is the most expensive case.
3. **Scale n.** Change `1_000_000` to `100_000`, then `10_000_000` (with `N` set to the last value each time). *Predict:* list time scales about linearly (10× items, roughly 10× time), and set time stays about flat. *Lesson:* you're seeing O(n) vs O(1) directly.
4. **Write the O(n²) version and race it.** Add a nested-loop `contains_duplicate_slow` to `dup.py`, then time both on `list(range(5_000))`, which has no duplicates and so is the worst case for both. *Predict:* the slow version is thousands of times slower. Doubling the size roughly quadruples its time but only doubles the fast one's.
5. **Hit the hashability rule.** Call `contains_duplicate([[1], [1]])`. *Predict:* `TypeError: unhashable type: 'list'`. Then try `[(1,), (1,)]`. *Lesson:* set elements must be hashable, and tuples of hashables are.

## Common pitfalls

- **Building a set for a single lookup.** `x in set(my_list)` is *slower* than `x in my_list`, because building the set is O(n) and you only use it once. Convert once, then look up many times.
- **`x in list` inside a loop.** `for a in A: if a in B_list:` is O(len(A)·len(B)). Change `B_list` to a set before the loop.
- **`{}` is not an empty set.** It's an empty dict. Use `set()`.
- **Unhashable elements.** Lists, dicts and sets can't go into a set. Convert to tuples or `frozenset` first.
- **Mutating a key after inserting it.** If a custom object's `__hash__` depends on fields you later change, the set can no longer find it.
- **Order isn't preserved.** If you need first-seen order without duplicates, use `dict.fromkeys(items)`.
- **Over-trusting O(1).** It's an average-case bound, and the worst case is O(n). Constant factors (hashing, lambda overhead) still count for tiny collections.

**Interview follow-ups:**

- *Can you do it in O(1) extra space?* Sort first (`nums.sort()`, O(n log n)) and check neighbours: `any(a == b for a, b in zip(nums, nums[1:]))`. Note that sorting in place modifies the input, and the `nums[1:]` slice copies the list, so use an index loop if you need truly O(1) space.
- *Is there a one-liner?* `len(set(nums)) != len(nums)`. It's O(n), but it always processes the whole input, with no early exit.
- *Two Sum?* `idx = {}`. For each `i, x`: if `target - x in idx`, return `[idx[target - x], i]`. Otherwise set `idx[x] = i`. That's O(n) time and space.
- *Why is the worst case O(n)?* If all keys collide, every lookup probes through all of them.

## Further reading

- [Python docs: Set types, `set` and `frozenset`](https://docs.python.org/3/library/stdtypes.html#set-types-set-frozenset)
- [Python docs: `timeit`, measuring execution time of small code snippets](https://docs.python.org/3/library/timeit.html)
- [Python docs: `hash()` and the definition of hashable](https://docs.python.org/3/glossary.html#term-hashable)
- [Python wiki: TimeComplexity of built-in operations](https://wiki.python.org/moin/TimeComplexity)

<!-- studio-job: hashing-and-big-o-in-practice-why-x-in-list-is-on-but-x-in-s -->
