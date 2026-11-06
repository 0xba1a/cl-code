# Number of Islands in Python: Counting Connected Regions with BFS Flood Fill

You get a 2D grid of `1`s (land) and `0`s (water) and need to count the **islands**: groups of land cells connected horizontally or vertically. This is a common interview question, and it shows up in real work too. Counting blobs in an image, finding connected regions on a game map, and grouping adjacent cells in a spreadsheet all use the same idea.

The key point is that **a grid is just a graph**. Once you see it that way, counting islands means counting *connected components*, and you can do that with a plain breadth-first search (BFS).

After reading this, you will be able to:

- model a grid as an implicit graph without building any adjacency lists,
- write an iterative BFS flood fill with `collections.deque`,
- explain why it runs in O(rows × cols) time, and
- explain why BFS (or an explicit stack) is safer than recursive DFS in Python.

## The concept

### A grid is a graph

Treat every cell `(r, c)` as a node. Its edges go to its four orthogonal neighbors:

```text
            (r-1, c)
               |
 (r, c-1) -- (r, c) -- (r, c+1)
               |
            (r+1, c)
```

You never build this graph. You compute neighbors as you need them by adding the offsets `(1,0)`, `(-1,0)`, `(0,1)`, `(0,-1)` and checking bounds. An **island** is a connected component made only of `1` cells. Diagonal cells are **not** connected.

### Counting components: scan + flood fill

The algorithm has two layers:

1. **Scan** every cell in row-major order.
2. When the scan finds a `1`, you have reached land that no earlier flood fill touched, so it is a **new island**. Increment the counter, then **flood fill** from that cell to visit every land cell connected to it.

The flood fill guarantees that each island is counted exactly once. When the scan moves on, every cell of that island has been marked. Later the scan will pass over those cells without counting them again.

### Sinking as the visited set

BFS needs a way to remember which nodes it has already seen. Usually you would use a `set` of visited coordinates. This code uses a cheaper trick: it **sinks** each land cell by overwriting it with `0`. A sunk cell looks like water, so neither the BFS nor the outer scan will treat it as land again. The grid becomes its own visited set, which costs no extra memory but **destroys the input**.

### Why a deque

BFS processes nodes in first-in, first-out order. `collections.deque` supports `append` and `popleft` in O(1). A plain `list` with `pop(0)` would be O(n) per pop, because every remaining element has to shift left.

### Complexity

- **Time: O(R × C).** The scan visits each cell once. Each land cell is enqueued at most once because it is sunk before it enters the queue. When a cell is dequeued, it checks 4 neighbors, which is constant work.
- **Extra space:** the queue holds the current BFS frontier. In the worst case that is O(R × C). In practice it stays much smaller, because the frontier of a BFS on a grid is roughly a diagonal band. No `visited` structure is needed.

### BFS vs. recursive DFS

A recursive DFS flood fill is shorter, but every step deeper adds a Python stack frame. CPython's default recursion limit is usually 1000 (see `sys.getrecursionlimit()`). A snake-shaped island with a few thousand cells will raise `RecursionError`. BFS with a deque is iterative, so the size of the island does not affect stack depth.

## Walking through the code

All the code is in [`islands.py`](islands.py). Here it is in chunks.

```python
from collections import deque

```

- `deque` (a double-ended queue) from the standard library gives O(1) appends and pops at both ends. You need O(1) `popleft()` for an efficient BFS queue.
- The blank line separates the import from the function.

```python
def count_islands(g):
    R, C, count = len(g), len(g[0]), 0
```

- `count_islands` takes the grid `g` as a list of lists of ints.
- `R` is the number of rows and `C` is the number of columns, taken from the first row. This assumes a non-empty, rectangular grid. `count` starts at 0.
- Caching `R` and `C` keeps the bounds checks in the inner loop short and fast.

```python
    for r in range(R):
        for c in range(C):
            if g[r][c] != 1:
                continue
```

- This is the outer scan in row-major order, so it reaches every cell exactly once.
- Water, and land already sunk by an earlier flood fill, both equal `0` here, so they get skipped. The guard clause with `continue` avoids one level of nesting.

```python
            count += 1
            q = deque([(r, c)])
            g[r][c] = 0
```

- A `1` that survives the scan cannot belong to any island seen so far, because that island would already have been sunk. So it starts a new island: `count += 1`.
- A new queue is seeded with the starting coordinate as a tuple `(r, c)`.
- The start cell is sunk **as it is enqueued**. Marking on enqueue, not on dequeue, is what keeps a cell from entering the queue twice.

```python
            while q:
                y, x = q.popleft()
```

- The loop runs until the queue is empty, which happens once the whole island has been explored. An empty deque is falsy.
- `popleft()` takes the oldest cell (FIFO), which makes this a breadth-first search. The names `y, x` mean row and column, and they keep the current cell separate from the scan's `r, c`.

```python
                for dy, dx in ((1,0),(-1,0),(0,1),(0,-1)):
                    ny, nx = y + dy, x + dx
```

- The four direction offsets are down, up, right, and left. A tuple of tuples is a constant literal, and the loop unpacks each pair into `dy, dx`.
- `ny, nx` is the neighbor's coordinate.

```python
                    if 0<=ny<R and 0<=nx<C and g[ny][nx]==1:
                        g[ny][nx] = 0
                        q.append((ny, nx))
    return count

```

- Python's chained comparison `0<=ny<R` is a bounds check. Because `and` short-circuits, `g[ny][nx]` is only read when the coordinate is in range. This matters because `g[-1]` would **not** raise an error. It would quietly wrap around to the last row.
- If the neighbor is unvisited land, the code sinks it right away and then enqueues it, for the same mark-on-enqueue reason as above.
- After the scan finishes, `count` holds the number of islands. Note that `return` sits at the function's top indentation level, outside both loops.

```python
grid = [[1,1,0,0,0],
        [1,1,0,0,1],
        [0,0,0,1,1],
        [0,0,0,0,0],
        [1,0,0,0,0]]
print(count_islands(grid))
```

- This is a 5×5 sample grid with three separate patches of land.
- The function's result is printed. `grid` is all zeros afterwards because the function mutates it in place.

## Run it yourself

**Prerequisites:** Python 3.12 or newer. The script only uses the standard library.

From this folder, which contains `islands.py`:

```sh
cd code
python3 islands.py
```

Output:

```text
3
```

### Why exactly `3`

Here is the grid with coordinates `(row, col)`:

```text
     c0 c1 c2 c3 c4
r0 [ 1, 1, 0, 0, 0 ]
r1 [ 1, 1, 0, 0, 1 ]
r2 [ 0, 0, 0, 1, 1 ]
r3 [ 0, 0, 0, 0, 0 ]
r4 [ 1, 0, 0, 0, 0 ]
```

1. **Scan hits `(0,0)` → count = 1.** Sink it and queue it.
   - Pop `(0,0)`: down `(1,0)` is land, so sink and queue it. Up is out of bounds. Right `(0,1)` is land, so sink and queue it. Left is out of bounds. Queue: `[(1,0), (0,1)]`.
   - Pop `(1,0)`: right `(1,1)` is land, so sink and queue it. All other neighbors are water, sunk, or out of bounds. Queue: `[(0,1), (1,1)]`.
   - Pop `(0,1)` and `(1,1)`: every neighbor is now `0`. The queue empties and the 2×2 block is gone.
2. The scan continues through row 0 (all `0` now) and reaches **`(1,4)` → count = 2.**
   - Pop `(1,4)`: down `(2,4)` is land, so sink and queue it.
   - Pop `(2,4)`: left `(2,3)` is land, so sink and queue it.
   - Pop `(2,3)`: no land neighbors. Done. `(1,4)` and `(2,3)` touch only diagonally, but they still belong to the same island because both connect to `(2,4)`.
3. The scan passes `(2,3)` and `(2,4)`, which are already `0`, so they are not counted again. Row 3 is all water.
4. **Scan hits `(4,0)` → count = 3.** Its neighbors are water or out of bounds, so this one-cell island sinks right away.
5. The scan ends and the function returns `3`, which `print` writes.

## Try it

1. **Connect two islands.** Set `grid[2][2] = 1` and `grid[1][2] = 1`. Predict the count before you run it. You should get `2`, because the cells `(1,1)–(1,2)–(2,2)–(2,3)` join the top-left block to the right-hand island. This shows that one flood fill absorbs everything reachable, however winding the path.
2. **Add diagonals.** Add `(1,1),(1,-1),(-1,1),(-1,-1)` to the direction tuple and rerun. The count stays `3` for this grid. Then set `grid[3][1] = 1`. With 4 directions the count is `4`. With 8 directions it is `3`, because `(3,1)` touches `(4,0)` diagonally. This shows that the neighbor definition *is* the connectivity rule.
3. **Watch the mutation.** Add `print(grid)` after the `print(count_islands(grid))` line. Every row is now zeros. Then pass a copy, `count_islands([row[:] for row in grid])`, and confirm the original survives. This shows the cost of the "sink as visited" trick.
4. **Break recursion, not BFS.** Write a recursive DFS version and run both on `[[1] * 5000]`, a single row with 5000 land cells. With the default recursion limit, the DFS should raise `RecursionError` and the BFS should print `1`. This shows why iterative traversal matters in Python.
5. **Measure island sizes.** Keep a `size` counter that you increment each time a cell is popped, and collect the sizes in a list. For the sample grid you should get `[4, 3, 1]`. This is the "Max Area of Island" variant.

## Common pitfalls

- **Empty grid.** `len(g[0])` raises `IndexError` when `g == []`. Guard with `if not g or not g[0]: return 0`.
- **String grids.** Many judges, including LeetCode, pass `"1"`/`"0"` strings. `g[r][c] != 1` is then always true, so the function returns `0`. Compare against the same type the input uses.
- **Marking on dequeue instead of enqueue.** If you only sink a cell when you pop it, the same cell can be queued several times by different neighbors. The result is still correct, but you waste time and memory.
- **Negative indices.** Leaving out `0<=ny` doesn't crash. `g[-1]` silently reads the last row and can merge islands that aren't connected.
- **Using `list.pop(0)`.** It is correct but O(n) per pop, so large grids can take quadratic time. Use `deque.popleft()`.
- **Mutating the caller's data.** If the caller needs the grid afterwards, use a `visited` set or copy the grid first.

**Interview follow-ups**

- *Can you avoid mutating the input?* Use a `visited = set()` of `(r, c)` tuples, at the cost of O(R × C) extra space.
- *Do it with DFS but without recursion.* Replace the deque with a list used as a stack (`append`/`pop`). Traversal order changes, but the count doesn't.
- *Do it without graph traversal.* Use union-find (disjoint set union): union each land cell with its land neighbors to the right and below, then count distinct roots.
- *What if the grid streams in, or land is added cell by cell?* Union-find handles incremental additions well ("Number of Islands II").

## Further reading

- [`collections.deque` — Python documentation](https://docs.python.org/3/library/collections.html#collections.deque)
- [Using lists as queues — Python tutorial](https://docs.python.org/3/tutorial/datastructures.html#using-lists-as-queues)
- [`sys.getrecursionlimit` / `sys.setrecursionlimit` — Python documentation](https://docs.python.org/3/library/sys.html#sys.setrecursionlimit)

<!-- studio-job: number-of-islands-with-bfs-on-a-grid-treating-a-2d-matrix-as -->
