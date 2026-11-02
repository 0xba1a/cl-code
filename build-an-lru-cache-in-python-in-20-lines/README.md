# Build an LRU Cache in Python in 20 Lines (O(1) Get & Put)

You can build a fully working LRU cache in Python in about 20 lines, with constant-time get and put. We use OrderedDict's move_to_end to mark keys as recently used and popitem(last=False) to evict the least recently used item when the cache goes over capacity. Then we run a quick test that shows exactly which key gets evicted and why. Finally, you'll learn the answer interviewers expect when you can't use OrderedDict: a hash map plus a doubly linked list.

#python #lrucache #codinginterview #datastructures #leetcode

Code typed live in the YouTube short, so you can read it, run it and change it.

## Files

- [`lru.py`](lru.py)

## Run it

Needs Docker. `./run.sh` starts `python:3.12-slim`, mounts this folder and runs what the video ran:

```sh
./run.sh
```

Clone it somewhere Docker can mount (e.g. under your home directory).

Commands:

```sh
python lru.py
```

<!-- studio-job: build-an-lru-cache-in-python-in-20-lines -->
