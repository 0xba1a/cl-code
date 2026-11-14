# Dijkstra's Algorithm with `heapq`: Solving Network Delay Time

You have `n` network nodes and a list of directed, weighted edges `[u, v, w]`, meaning a signal sent from `u` reaches `v` after `w` time units. A signal starts at node `k`. How long until **every** node has received it? If some node can never receive it, the answer is `-1`. This is LeetCode's "Network Delay Time" problem.

The first instinct for "how far is everything from the source?" is breadth-first search. BFS, though, counts **hops**. It is only correct when every edge costs the same. Here every edge has its own cost, so a two-hop path can be cheaper than a one-hop path, and BFS gets it wrong. Dijkstra's algorithm fixes this by measuring **cost**.

After reading this you will be able to:

- explain why Dijkstra's algorithm is correct and when it breaks,
- implement it in Python with a `heapq` min-heap and the "skip stale entries" trick,
- trace it by hand and reason about its `O((V + E) log V)` cost.

## The concept

### Why BFS fails

Take the graph used in the code:

```text
        4
   1 ───────► 2 ───► 4
   │          ▲   1
 1 │          │ 2
   ▼          │
   3 ─────────┘
```

BFS from node 1 reaches node 2 in one hop over the edge of weight 4, and it never looks back. The real shortest path is `1 → 3 → 2` with cost `1 + 2 = 3`. Fewer hops does not mean less time.

### The greedy idea

Dijkstra keeps a tentative distance `dist[v]` for every node. Every distance starts at infinity except the source, which starts at 0. The algorithm then repeats one step:

> Take the unfinished node with the **smallest** tentative distance, mark it finished, and **relax** each of its outgoing edges.

To *relax* an edge `u → v` with weight `w` means: if `dist[u] + w < dist[v]`, set `dist[v] = dist[u] + w`, because you just found a cheaper way to reach `v`.

**Why it works:** suppose `u` is the closest unfinished node. Any other path to `u` must leave the finished set through some unfinished node `x`, and `dist[x] >= dist[u]` because `u` was the smallest. Edge weights are **non-negative**, so the rest of that path cannot make it cheaper. That means `dist[u]` is already final. This argument depends entirely on non-negative weights, which is why negative edges break Dijkstra.

### The data structures

- **Adjacency list:** maps each node to a list of `(neighbor, weight)` pairs. You can iterate over a node's edges in time proportional to its out-degree.
- **Min-heap (priority queue):** gives you "the unfinished node with the smallest distance" in `O(log V)`. Python's `heapq` module implements a binary min-heap on top of a plain list.

`heapq` has no "decrease-key" operation. When a node's distance improves, you push a **new** `(distance, node)` entry and leave the old one in the heap. Later, when the old, larger entry is popped, you see that it is worse than the recorded `dist[node]` and skip it. This is called **lazy deletion**.

### Complexity

- Every successful relaxation pushes once, so there are at most `E` pushes (plus the source), and the same number of pops. Each costs `O(log(heap size))`. Because heap size is at most `E` and `log E <= 2 log V`, the total is **`O((V + E) log V)`**.
- Space: `O(V + E)` for the graph, `dist`, and the heap.

Trade-offs: an array-based `O(V²)` version (no heap) can be faster on very dense graphs. A Fibonacci heap gets `O(E + V log V)` in theory but is rarely worth it in practice. For negative weights you need Bellman-Ford (`O(V·E)`).

## Walking through the code

The whole program lives in [`dijkstra.py`](dijkstra.py). Here it is, one chunk at a time.

```python
import heapq
from collections import defaultdict

```

- `heapq` provides `heappush` and `heappop`, which keep a regular list ordered as a binary min-heap. The smallest item is always at index 0.
- `defaultdict` creates a missing key's value automatically. It lets you append edges without first checking that the key exists. It also means `g[node]` is an empty list for nodes with no outgoing edges.

```python
def network_delay(times, n, k):
    g = defaultdict(list)
    for u, v, w in times:
        g[u].append((v, w))
```

- The function takes the edge list `times`, the node count `n` (nodes are labeled `1..n`), and the source `k`.
- `g` is the adjacency list. Each `[u, v, w]` triple is unpacked and stored as `(v, w)` under `u`. Edges are directed, so you add only `u → v`.

```python
    dist = {i: float("inf") for i in range(1, n + 1)}
    dist[k] = 0
    heap = [(0, k)]
```

- `dist` has an entry for **every** node `1..n`, not just the nodes that appear in `times`. This matters at the end: an isolated node stays at infinity, so you can detect it.
- `float("inf")` compares greater than any finite number, so the first real path always counts as an improvement.
- The source costs 0 to reach. The heap starts with one entry, `(0, k)`. Tuples compare element by element, so the heap orders by distance first.

```python
    while heap:
        d, node = heapq.heappop(heap)
        if d > dist[node]:
            continue
```

- The loop runs until no work is left. Each `heappop` returns the entry with the smallest distance.
- The **stale-entry check**: if the popped `d` is larger than the best distance already recorded, a cheaper entry for this node was pushed later and already processed. This entry is out of date, so you skip it. Without this check you would re-expand nodes with outdated distances. The answer would stay correct, but you would waste work.

```python
        for nei, w in g[node]:
            if d + w < dist[nei]:
                dist[nei] = d + w
                heapq.heappush(heap, (dist[nei], nei))
```

- This is the relaxation step. For every outgoing edge, check whether going through `node` is cheaper than the best known path to `nei`.
- If it is, record the new distance and push a fresh entry. You push only on improvement, which bounds the number of pushes by the number of edges.
- `d` and `dist[node]` are equal here because stale entries were already skipped, so using `d` is safe.

```python
    best = max(dist.values())
    return best if best < float("inf") else -1

```

- The signal reaches every node by the time the **farthest** node gets it, so the answer is the maximum shortest-path distance.
- If any node is still infinity, it is unreachable, so you return `-1` as the problem requires.

```python
times = [[1, 2, 4], [1, 3, 1], [3, 2, 2], [2, 4, 1]]
print(network_delay(times, 4, 1))
```

- This builds the four-node example from the diagram above: 4 nodes, source node 1, and prints the result.

## Run it yourself

Prerequisites: Python 3.12 or newer. Only the standard library is used.

```sh
python dijkstra.py
```

Output:

```text
4
```

Here is why it prints exactly that. Heap contents are shown after each step.

| Step | Pop      | Action                                                                  | `dist` (1,2,3,4) | Heap after               |
|------|----------|-------------------------------------------------------------------------|------------------|--------------------------|
| 0    | n/a      | start                                                                    | 0, ∞, ∞, ∞       | `[(0,1)]`                |
| 1    | `(0,1)`  | relax 1→2: 0+4 < ∞, push `(4,2)`. Relax 1→3: 0+1 < ∞, push `(1,3)`      | 0, 4, 1, ∞       | `[(1,3), (4,2)]`         |
| 2    | `(1,3)`  | relax 3→2: 1+2 = 3 < 4, push `(3,2)`                                    | 0, 3, 1, ∞       | `[(3,2), (4,2)]`         |
| 3    | `(3,2)`  | relax 2→4: 3+1 < ∞, push `(4,4)`                                        | 0, 3, 1, 4       | `[(4,2), (4,4)]`         |
| 4    | `(4,2)`  | **stale**: 4 > `dist[2]` = 3, skip                                      | 0, 3, 1, 4       | `[(4,4)]`                |
| 5    | `(4,4)`  | node 4 has no outgoing edges                                            | 0, 3, 1, 4       | `[]`                     |

The final distances are `{1: 0, 2: 3, 3: 1, 4: 4}`. None is infinite, so the function returns `max = 4`. Node 2 first got distance 4 and then the cheaper 3 through node 3. The old `(4, 2)` entry was skipped exactly as designed. In step 4, `(4,2)` and `(4,4)` tie on distance, so the tuple comparison falls back to the node label, and 2 comes out first.

## Try it

1. **Make the detour expensive.** Change `[3, 2, 2]` to `[3, 2, 5]`. Predict: `1→3→2` now costs 6, so the direct edge (4) wins, node 4 is at 5, and the program prints `5`. You learn that Dijkstra picks whichever path is cheapest, whatever the hop count. No stale entry is created this time.
2. **Make a node unreachable.** Call `network_delay(times, 5, 1)`. Node 5 has no incoming edges, so it stays at infinity and the output is `-1`. You learn why `dist` is initialized for all `n` nodes, not built from the edges.
3. **Change the source.** Call `network_delay(times, 4, 3)`. Node 1 cannot be reached from 3, so the result is `-1`. Remember that edges are directed.
4. **Watch the heap.** Add `print(d, node, dist)` right after `heappop`. You will see the stale `(4, 2)` pop. Then remove the `if d > dist[node]: continue` lines and confirm that the answer is still `4`. The check is about efficiency, not correctness, in this non-negative setting.
5. **Compare with BFS.** Write a BFS that sets `dist[v] = dist[u] + w` the first time it sees `v`. Run it on the original input and watch it report node 2 at 4 and node 4 at 5. That shows the hop-versus-cost failure concretely.

## Common pitfalls

- **Negative edge weights.** Dijkstra assumes a finished node can never get cheaper. A negative edge breaks that. For example, with `1→2 (1)`, `1→3 (2)`, `3→2 (-5)`, textbook Dijkstra with a `visited` set finalizes node 2 at 1 even though the true cost is -3. This lazy-heap version would re-push node 2, but then it can re-expand nodes many times, so the `O((V + E) log V)` bound is gone. With a negative cycle it never terminates. Use Bellman-Ford instead (it also detects negative cycles).
- **Forgetting unreachable nodes.** If you build `dist` only from nodes seen in `times`, a node with no edges is silently ignored and you return a wrong finite answer.
- **Off-by-one node labels.** The nodes here are `1..n`, so the code uses `range(1, n + 1)`. Using `range(n)` would create a phantom node 0 that stays at infinity.
- **Pushing `(node, dist)` instead of `(dist, node)`.** The heap orders by the first tuple element, so swapping them turns the heap into an ordering by node label, and the algorithm stops being correct.
- **Using `>=` in the stale check.** `if d >= dist[node]` would skip the valid entry too, because the valid entry has `d == dist[node]`. Nothing would ever expand.
- **Undirected graphs.** If the problem's edges are bidirectional, add both `g[u].append((v, w))` and `g[v].append((u, w))`.

Interview follow-ups:

- *How would you do this without `heapq`?* Use the `O(V²)` version. Keep a `visited` set, and on each iteration scan all nodes for the unvisited one with the smallest `dist`. On dense graphs where `E ≈ V²`, this is actually optimal.
- *Can you stop early?* For a single target, yes: return as soon as you pop the target. For this problem you can also count finalized nodes and stop when all `n` are done.
- *What if all weights are 0 or 1?* Use 0-1 BFS with a `deque`, which runs in `O(V + E)`.
- *What if all weights are equal?* Plain BFS is correct again.

## Further reading

- [`heapq` — Heap queue algorithm (Python docs)](https://docs.python.org/3/library/heapq.html)
- [`collections.defaultdict` (Python docs)](https://docs.python.org/3/library/collections.html#collections.defaultdict)
- [Python tutorial: Data Structures (tuples and comparisons)](https://docs.python.org/3/tutorial/datastructures.html)

<!-- studio-job: dijkstras-shortest-path-with-a-heap-on-network-delay-time-ad -->
