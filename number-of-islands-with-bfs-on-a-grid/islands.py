from collections import deque

def count_islands(g):
    R, C, count = len(g), len(g[0]), 0
    for r in range(R):
        for c in range(C):
            if g[r][c] != 1:
                continue
            count += 1
            q = deque([(r, c)])
            g[r][c] = 0
            while q:
                y, x = q.popleft()
                for dy, dx in ((1,0),(-1,0),(0,1),(0,-1)):
                    ny, nx = y + dy, x + dx
                    if 0<=ny<R and 0<=nx<C and g[ny][nx]==1:
                        g[ny][nx] = 0
                        q.append((ny, nx))
    return count

grid = [[1,1,0,0,0],
        [1,1,0,0,1],
        [0,0,0,1,1],
        [0,0,0,0,0],
        [1,0,0,0,0]]
print(count_islands(grid))
