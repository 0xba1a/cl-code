# Number of Islands in Python: BFS Flood Fill That Sinks Every Island

Number of Islands is a classic coding interview question, and the trick is to treat the 2D grid as a graph where each cell links to its four neighbors. You'll scan every cell, count a new island whenever you hit a 1, then BFS-flood-fill it with a deque, sinking land to 0 so the grid itself works as your visited set. We run it on a grid with three patches of land, get three, and break down why it's O(rows × cols). You'll also see why BFS beats recursive DFS when a huge island would hit Python's recursion limit.

#python #leetcode #bfs #codinginterview #algorithms #graphs

Code typed live in the YouTube short, so you can read it, run it and change it.

## Files

- [`islands.py`](islands.py)

## Run it

Needs Docker. `./run.sh` starts `python:3.12-slim`, mounts this folder and runs what the video ran:

```sh
./run.sh
```

Clone it somewhere Docker can mount (e.g. under your home directory).

Commands:

```sh
python3 islands.py
```

<!-- studio-job: number-of-islands-with-bfs-on-a-grid-treating-a-2d-matrix-as -->
