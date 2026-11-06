# Number of Islands in Python: Counting Connected Land with a BFS Flood Fill

You get a 2D grid of `1`s (land) and `0`s (water), and you need to count the **islands**. An island is a group of land cells joined horizontally or vertically. This is one of the most common grid questions in coding interviews. It matters because the same technique shows up in real work: connected regions in images (the paint-bucket tool), clusters on a map, and blobs in a game board.

By the end of this lesson you will be able to:

- treat any 2D grid as a graph and run graph algorithms on it,
- write a breadth-first search (BFS) flood fill with `collections.deque`,
- explain why the algorithm runs in O(rows × cols) time,
- explain when recursive depth-first search (DFS) is risky in Python and why BFS avoids that risk.

## The concept

### A grid is a graph

The key insight is that you don't need a special "grid algorithm". Treat each cell as a **node**. Each node has an **edge** to up to four neighbours: up, down, left and right. Diagonals don't count.

```text
            (r-1, c)
               |
 (r, c-1) -- (r, c) -- (r, c+1)
               |
            (r+1, c)
```

An island is then a **connected component** made only of land nodes. So "count the islands" really means "count the connected components of land".

### Scan + flood fill

The algorithm has two layers:

1. **Scan** every cell in row-major order (left to right, top to bottom).
2. When the scan finds land that you haven't visited yet, you've found a **new island**. Add one to the counter, then **flood fill** from that cell to visit every land cell connected to it.

The flood fill has to mark cells as visited, or the scan would count the same island again later. A common trick is to **sink** each land cell (set it to `0`) as you reach it. The grid itself then works as the visited set, so you don't need an extra `set` or boolean matrix.

### Why BFS with a deque

BFS processes cells in first-in, first-out order using a queue. In Python, `collections.deque` supports O(1) `append` and `popleft`. A plain `list.pop(0)` is O(n) because every remaining element has to shift left.

Here is a small trace of one flood fill on a 2×2 island that starts at `(0,0)`:

```text
queue: [(0,0)]          sink (0,0)
pop (0,0) -> sink+queue (1,0), (0,1)     queue: [(1,0),(0,1)]
pop (1,0) -> sink+queue (1,1)            queue: [(0,1),(1,1)]
pop (0,1) -> nothing new (all sunk)      queue: [(1,1)]
pop (1,1) -> nothing new                 queue: []   -> island done
```

### Complexity and trade-offs

- **Time: O(R × C).** The scan visits each cell once. Each land cell enters the queue at most once because it is sunk the moment it's queued. Each dequeued cell checks only 4 neighbours, which is constant work.
- **Extra space:** the queue holds the current BFS "frontier". In the worst case that is bounded by O(R × C), but in practice it's usually much smaller than the grid. No visited structure is needed because the grid stores that information.
- **Trade-off: mutation.** Sinking the cells destroys the input. If the caller still needs the grid, copy it first or use a separate `visited` set.
- **BFS vs recursive DFS.** Recursive DFS is shorter to write, but each land cell in a long chain adds a stack frame. CPython's default recursion limit is usually 1000 (see `sys.getrecursionlimit()`), so a large island can raise `RecursionError`. BFS keeps its pending work in a heap-allocated deque, so the size of an island doesn't depend on the call stack.

## Walking through the code

All the code lives in [`islands.py`](islands.py). Let's go through it top to bottom.

```python
from collections import deque

```

`deque` ("double-ended queue") is the standard-library queue type. You need fast removal from the **front** for FIFO order, and `deque.popleft()` does that in O(1).

```python
def count_islands(g):
    R, C, count = len(g), len(g[0]), 0
```

The function takes the grid `g` as a list of lists. `R` is the number of rows and `C` is the number of columns (the length of the first row, assuming the grid is rectangular). `count` is the island counter. Saving `R` and `C` once keeps the bounds checks later short and cheap. Note that `g[0]` assumes the grid has at least one row.

```python
    for r in range(R):
        for c in range(C):
            if g[r][c] != 1:
                continue
```

This is the **scan**: two nested loops visit every cell in row-major order. If a cell isn't `1`, it's water or land that an earlier flood fill already sank, so you skip it. This line is what stops an island from being counted twice.

```python
            count += 1
            q = deque([(r, c)])
            g[r][c] = 0
```

Reaching this point means the cell is unvisited land, so it starts a **new island**. You increment the count right away, before exploring. You then create a queue that holds the starting coordinate as a `(row, col)` tuple, and sink the start cell immediately. Sinking at **enqueue time** (not dequeue time) matters: it guarantees that no cell can be added to the queue twice.

```python
            while q:
                y, x = q.popleft()
```

This is the BFS loop. An empty deque is falsy, so `while q` runs until the island has been fully explored. `popleft()` takes the oldest entry, which gives FIFO order: the island is explored in rings around the start cell. The names `y`/`x` mean row/column.

```python
                for dy, dx in ((1,0),(-1,0),(0,1),(0,-1)):
                    ny, nx = y + dy, x + dx
```

The tuple of offsets lists the four neighbours: down, up, right, left. Writing the offsets as data instead of four copy-pasted `if` blocks keeps the code compact. It also makes the neighbour rule easy to change, for example by adding diagonals. `ny, nx` is the neighbour's coordinate.

```python
                    if 0<=ny<R and 0<=nx<C and g[ny][nx]==1:
                        g[ny][nx] = 0
                        q.append((ny, nx))
    return count

```

Python's chained comparisons (`0<=ny<R`) check both bounds in one expression. The order of the `and` clauses matters. `and` short-circuits, so `g[ny][nx]` is only read once the coordinate is known to be in range. Without that order, a negative index like `-1` would silently wrap around to the last row or column (Python's negative indexing) instead of failing. If the neighbour is land, sink it and queue it. After every land cell has been scanned, `return count`.

```python
grid = [[1,1,0,0,0],
        [1,1,0,0,1],
        [0,0,0,1,1],
        [0,0,0,0,0],
        [1,0,0,0,0]]
print(count_islands(grid))
```

This is a 5×5 example grid with three separate patches of land. The last line calls the function and prints the result.

## Run it yourself

**Prerequisites:** Python 3.12 or newer. The script uses only the standard library.

From this folder, run:

```sh
python3 islands.py
```

Output:

```text
3
```

### Why exactly `3`?

Label the land in the grid:

```text
     c0 c1 c2 c3 c4
r0 [ A  A  .  .  . ]
r1 [ A  A  .  .  B ]
r2 [ .  .  .  B  B ]
r3 [ .  .  .  .  . ]
r4 [ C  .  .  .  . ]
```

1. The scan starts at `(0,0)`, which is `1`. Set `count = 1`. BFS sinks `(0,0)`, `(1,0)`, `(0,1)`, `(1,1)`, which is all of island **A** (traced step by step in the concept section).
2. The scan continues. `(0,1)`, `(1,0)` and `(1,1)` are now `0`, so they're skipped. The next `1` is `(1,4)`. Set `count = 2`.
   - pop `(1,4)`: down `(2,4)` is land, so sink and queue it. Up `(0,4)` is water, right `(1,5)` is out of bounds, left `(1,3)` is water.
   - pop `(2,4)`: left `(2,3)` is land, so sink and queue it.
   - pop `(2,3)`: all neighbours are water or already sunk. The queue is empty, so island **B** is done.
3. When the scan reaches `(2,3)` and `(2,4)`, they're already `0`, so they don't increase the count. **This is the visited-set trick at work.** `(2,3)` touches `(1,4)` only diagonally, but it still belongs to B because it is joined through `(2,4)`.
4. The scan reaches `(4,0)`, which is `1`. Set `count = 3`. Its BFS finds no land neighbours, so it's a one-cell island **C**.
5. No `1`s remain, so the function returns `3` and `print` outputs it.

## Try it

1. **Add a diagonal neighbour.** Change `grid[3][2]` to `1`. That cell touches `(2,3)` only diagonally. Predict the result, then run it. You should get `4`, because diagonal contact doesn't connect cells. *Lesson: the neighbour list defines what "connected" means.*
2. **Switch to 8-directional connectivity.** Add `(1,1),(1,-1),(-1,1),(-1,-1)` to the offsets tuple and rerun experiment 1. The new cell now joins island B, so the result goes back to `3`. *Lesson: one line changes the graph's edges.*
3. **Watch the grid get destroyed.** Add `print(grid)` after the `print(count_islands(grid))` line. Every row is now all zeros. Then pass `[row[:] for row in grid]` to the function instead, and the original grid survives. *Lesson: in-place marking has a side effect for the caller.*
4. **Make a giant island.** Build `big = [[1]*1000 for _ in range(1000)]` and count it. You get `1` quickly. Then write a recursive DFS version and run it on the same grid. It raises `RecursionError`, because a single island of a million cells is far deeper than the default limit. *Lesson: why BFS (or an explicit stack) is safer in Python.*
5. **Swap the deque for a list.** Replace `deque([(r, c)])` with `[(r, c)]` and `q.popleft()` with `q.pop(0)`, then time it on the big grid with `time.perf_counter()`. *Lesson: `list.pop(0)` is O(n), so the right container matters.*

## Common pitfalls

- **String grids.** LeetCode's version uses `"1"`/`"0"` strings. With this code, `g[r][c] != 1` is always true for strings, so it silently returns `0`. Compare against the type your input actually uses.
- **Marking visited too late.** If you sink a cell when you *pop* it instead of when you *push* it, the same cell can be queued several times by different neighbours. The answer is still correct, but you waste time and memory.
- **Bounds check after indexing.** If you write `g[ny][nx]==1 and 0<=ny<R` instead, you get `IndexError` past the right or bottom edge, and wrong wrap-around reads at `-1`.
- **Empty input.** `len(g[0])` raises `IndexError` when `g == []`. Guard with `if not g or not g[0]: return 0`.
- **Unexpected mutation.** Callers may not expect their grid to be zeroed out. Document the behaviour or copy the grid first.

**Interview follow-ups:**

- *Do it with DFS without recursion.* Use a plain list as a stack: `append` and `pop()` instead of `popleft()`. The complexity is the same and there's no recursion limit.
- *Do it without mutating the input.* Keep a `visited` set of `(r, c)` tuples. This costs O(R × C) extra space.
- *What if the grid is streamed in or updated cell by cell?* Use Union-Find (disjoint set union) to merge neighbouring land as it appears ("Number of Islands II").
- *Return each island's size, or the largest one?* Count the pops inside each BFS.

## Further reading

- [`collections.deque` (Python docs)](https://docs.python.org/3/library/collections.html#collections.deque)
- [Using lists as queues (Python tutorial)](https://docs.python.org/3/tutorial/datastructures.html#using-lists-as-queues)
- [`sys.getrecursionlimit` / `sys.setrecursionlimit`](https://docs.python.org/3/library/sys.html#sys.getrecursionlimit)
- [Comparisons and chaining (Python language reference)](https://docs.python.org/3/reference/expressions.html#comparisons)

<!-- studio-job: number-of-islands-with-bfs-on-a-grid-treating-a-2d-matrix-as -->
