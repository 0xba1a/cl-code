import numpy as np
toks = ["the", "a", "cat", "zebra"]
logits = np.array([2.0, 1.0, 0.5, -1.0])
def softmax(x, t):
    z = x / t
    e = np.exp(z - z.max())
    return e / e.sum()
for t in (0.5, 2.0):
    print(f"T={t}", softmax(logits, t).round(2))
p = softmax(logits, 1.0)
def top_k(p, k):
    q = np.where(p >= np.sort(p)[-k], p, 0)
    return q / q.sum()
print("top-k=2", top_k(p, 2).round(2))
def top_p(p, top):
    i = np.argsort(p)[::-1]
    keep = np.cumsum(p[i]) - p[i] < top
    q = np.zeros_like(p)
    q[i[keep]] = p[i[keep]]
    return q / q.sum()
print("top-p=0.9", top_p(p, 0.9).round(2))
