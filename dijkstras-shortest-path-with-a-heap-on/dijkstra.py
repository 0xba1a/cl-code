import heapq
from collections import defaultdict

def network_delay(times, n, k):
    g = defaultdict(list)
    for u, v, w in times:
        g[u].append((v, w))
    dist = {i: float("inf") for i in range(1, n + 1)}
    dist[k] = 0
    heap = [(0, k)]
    while heap:
        d, node = heapq.heappop(heap)
        if d > dist[node]:
            continue
        for nei, w in g[node]:
            if d + w < dist[nei]:
                dist[nei] = d + w
                heapq.heappush(heap, (dist[nei], nei))
    best = max(dist.values())
    return best if best < float("inf") else -1

times = [[1, 2, 4], [1, 3, 1], [3, 2, 2], [2, 4, 1]]
print(network_delay(times, 4, 1))
