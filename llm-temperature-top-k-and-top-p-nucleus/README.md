# How an LLM Picks the Next Token: Temperature, Top-k and Top-p in NumPy

Setting temperature to 0 does not make a language model give the same answer every time. To see why, you need to know what happens between the model's raw output and the token it actually writes. At each step the model produces one score per vocabulary token. Those scores become a probability distribution, the distribution gets reshaped, and then one token is picked.

This matters every time you call an LLM API. Temperature, `top_k` and `top_p` are the settings that trade accuracy for variety. If you set them without knowing what they do, you can get extraction output that drifts between runs or creative writing that keeps repeating itself.

After this lesson you will be able to:

- turn logits into probabilities with a numerically stable, temperature-scaled softmax,
- implement top-k and top-p (nucleus) filtering in a few lines of NumPy,
- work out by hand what each setting does to a distribution, and
- explain in an interview why temperature 0 means "most likely" and not "guaranteed identical".

## The concept

### Logits → probabilities

For every token in its vocabulary, the model outputs a real-valued **logit**. Logits can be any real number, so you can't sample from them directly. **Softmax** turns them into probabilities:

```
p_i = exp(z_i / T) / Σ_j exp(z_j / T)
```

Exponentiating makes every value positive and keeps the ranking. Dividing by the sum makes the values add up to 1.

### Temperature T

Before exponentiating, you divide every logit by `T`:

- **T < 1** pushes the logits further apart. After `exp`, the gaps grow, and the top token takes most of the probability. The distribution gets *sharper*.
- **T > 1** pulls the logits closer together. The distribution gets *flatter*, and unlikely tokens get a real chance.
- **T → 0** puts all the probability on the argmax. This is **greedy decoding**. You can't literally divide by 0, so libraries treat `T=0` as "just take the argmax".

### Truncation: top-k and top-p

Even with sensible temperatures, the long tail of a large vocabulary adds up to a real chance of picking a nonsense token. Truncation methods zero out the tail and then **renormalize**:

- **Top-k** keeps the `k` most probable tokens.
- **Top-p (nucleus)** sorts tokens by probability and keeps the *smallest prefix* whose cumulative probability reaches `p`. The number of kept tokens changes with the distribution: few when the model is confident, many when it is unsure.

Here is the pipeline for one decoding step:

```
logits ──÷T──► softmax ──► [top-k / top-p mask] ──► renormalize ──► sample one token
```

### Trace with this file's numbers (T = 1)

```
token   logit   exp(logit)   p       sorted cumsum   cumsum - p   < 0.9 ?
the      2.0      7.389     0.609       0.609           0.000       keep
a        1.0      2.718     0.224       0.834           0.609       keep
cat      0.5      1.649     0.136       0.970           0.834       keep
zebra   -1.0      0.368     0.030       1.000           0.970       drop
         sum =   12.124
```

### Complexity and trade-offs

For a vocabulary of size V:

- Softmax costs O(V) time and O(V) space.
- Top-k as written here sorts, so it costs O(V log V). A partial selection such as `np.partition` brings that down to O(V).
- Top-p needs a sort, so it costs O(V log V).

V is about 10⁵, and the forward pass is far more expensive, so in practice this cost is negligible.

The real trade-off is **accuracy versus diversity**. For code and extraction, use temperature near 0. For creative writing, try a temperature around 0.8 with top-p 0.9.

### Why T = 0 still isn't deterministic

Greedy decoding is deterministic *given identical logits*. On GPUs, floating-point addition is not associative. The order of parallel reductions, the choice of kernel, and how your request is **batched** with other requests can all change the logits slightly. If two tokens are nearly tied, a tiny change can flip the argmax. Every later token is generated from that changed prefix, so one flip can change the rest of the output.

## Walking through the code

All the code is in [`sampling.py`](sampling.py).

```python
import numpy as np
toks = ["the", "a", "cat", "zebra"]
logits = np.array([2.0, 1.0, 0.5, -1.0])
```

- `import numpy as np` imports NumPy under its conventional alias. The rest of the file does vectorized array maths with it.
- `toks` is a toy four-word vocabulary. It is only there so you can tell which position is which. The program never prints it, but index 0 is `"the"`, and so on.
- `logits` holds the model's pretend raw scores, one per token, in the same order as `toks`. It is a float NumPy array, so division and `exp` work element-wise.

```python
def softmax(x, t):
    z = x / t
    e = np.exp(z - z.max())
    return e / e.sum()
```

- `z = x / t` applies the temperature. Every logit is scaled by the same factor.
- `np.exp(z - z.max())` is the **numerically stable softmax** trick. Subtracting a constant from every logit does not change the result, because the constant cancels in the ratio. Subtracting the maximum makes the largest exponent `exp(0) = 1`, so `exp` can never overflow, even with huge logits or a tiny `t`.
- `e / e.sum()` normalizes the values so they add up to 1.

```python
for t in (0.5, 2.0):
    print(f"T={t}", softmax(logits, t).round(2))
```

- This loop applies a low temperature and then a high one to the same logits, so you can compare the two distributions directly.
- `.round(2)` rounds the values for display only. NumPy prints the array in its usual bracketed form.

```python
p = softmax(logits, 1.0)
```

- `T = 1.0` gives the model's "natural" distribution. This `p` is the input to both truncation methods, so you can compare them on the same distribution.

```python
def top_k(p, k):
    q = np.where(p >= np.sort(p)[-k], p, 0)
    return q / q.sum()
print("top-k=2", top_k(p, 2).round(2))
```

- `np.sort(p)` sorts the probabilities in ascending order, so `[-k]` is the k-th largest. That value is the threshold.
- `np.where(cond, p, 0)` keeps each probability at or above the threshold and sets the others to 0.
- `q / q.sum()` renormalizes, so the surviving tokens again add up to 1.
- The `print` applies top-k with `k = 2`.

```python
def top_p(p, top):
    i = np.argsort(p)[::-1]
    keep = np.cumsum(p[i]) - p[i] < top
    q = np.zeros_like(p)
    q[i[keep]] = p[i[keep]]
    return q / q.sum()
print("top-p=0.9", top_p(p, 0.9).round(2))
```

- `np.argsort(p)[::-1]` gives the token indices from most to least probable. You need the indices, not just the sorted values, so you can write results back to the original positions.
- `np.cumsum(p[i]) - p[i]` is the cumulative probability **before** each token, an exclusive prefix sum. A token is kept if the mass before it is still below `top`. This always keeps the top token, because the mass before it is 0. It also keeps the token that crosses the threshold, which is exactly the "smallest set that reaches p" rule. If you compared the inclusive cumsum with `< top` instead, you would drop the token that crosses the threshold and keep too little.
- `q = np.zeros_like(p)` creates an output array of zeros with the same shape and dtype as `p`.
- `q[i[keep]] = p[i[keep]]` uses fancy indexing: `i[keep]` holds the original indices of the kept tokens, and their probabilities are copied back into those positions.
- `return q / q.sum()` renormalizes, and the `print` applies top-p with `top = 0.9`.

Notice that the file stops at the reshaped distribution. A real decoder would then draw one token, for example with `np.random.default_rng().choice(toks, p=q)`.

## Run it yourself

Prerequisites: Python 3.12 or newer.

Run these from this folder:

```sh
pip install --quiet --no-cache-dir numpy >/dev/null 2>&1
python sampling.py
```

Output:

```text
T=0.5 [0.84 0.11 0.04 0.  ]
T=2.0 [0.43 0.26 0.21 0.1 ]
top-k=2 [0.73 0.27 0.   0.  ]
top-p=0.9 [0.63 0.23 0.14 0.  ]
```

Here is why each line comes out exactly this way:

1. **T=0.5**: the scaled logits are `[4, 2, 1, -2]`. After subtracting the max you get `[0, -2, -3, -6]`. Their exponents are `[1, 0.135, 0.050, 0.0025]`, which sum to 1.188. Dividing gives `[0.842, 0.114, 0.042, 0.002]`. "the" dominates, and "zebra" rounds to `0.` (NumPy pads it to keep the columns aligned).
2. **T=2.0**: the scaled logits are `[1, 0.5, 0.25, -0.5]`. After shifting you get `[0, -0.5, -0.75, -1.5]`. Their exponents are `[1, 0.607, 0.472, 0.223]`, which sum to 2.302. Dividing gives `[0.434, 0.263, 0.205, 0.097]`. The distribution is much flatter, and "zebra" now has about a 10% chance.
3. **top-k=2**: at T=1, `p ≈ [0.609, 0.224, 0.136, 0.030]`. The 2nd-largest value is 0.224, so "the" and "a" survive. Their sum is 0.834, and 0.609 / 0.834 = 0.73 and 0.224 / 0.834 = 0.27.
4. **top-p=0.9**: the exclusive cumsums are `[0, 0.609, 0.834, 0.970]`. The first three are below 0.9, so they are kept. "cat" is the token that pushes the total past 0.9. The kept mass is 0.970, which gives `[0.63, 0.23, 0.14, 0]`. Top-p kept three tokens here, while top-k=2 kept two.

## Try it

1. **Push temperature toward greedy.** Change the loop to `(0.1, 0.5, 2.0, 10.0)`. Prediction: at 0.1, "the" gets about 1.0. At 10, all four values approach 0.25. You learn that T interpolates between argmax and uniform.
2. **Test the overflow guard.** Set `logits = np.array([1000.0, 999.0, 0.0, -1.0])` and run the script, then replace `z - z.max()` with plain `z` and run again. Prediction: the stable version prints sensible numbers, while the naive version produces `inf`/`nan` with overflow warnings. You learn why the max-subtraction is not optional.
3. **Make top-k and top-p disagree more.** Try `top_p(p, 0.5)` and `top_p(p, 0.99)`. Prediction: 0.5 keeps only "the" (`[1, 0, 0, 0]`), and 0.99 keeps all four. You learn that the nucleus size adapts to the distribution.
4. **Combine temperature with truncation.** Compute `top_p(softmax(logits, 0.5), 0.9)`. Prediction: at T=0.5, "the" + "a" already reach 0.956, so only two tokens survive. You learn that lower temperature also shrinks the nucleus, so the order of operations matters.
5. **Actually sample.** Add `rng = np.random.default_rng(0)` and print `rng.choice(toks, size=20, p=top_p(p, 0.9))`. Run it again with a different seed. You learn that the randomness lives in this final draw, not in the distribution.

## Common pitfalls

- **Ties in top-k.** `p >= threshold` keeps *every* token equal to the k-th value, so you can end up with more than `k` tokens. If you need exactly k, select by index: `np.argsort(p)[-k:]`.
- **Dividing by T = 0.** `x / 0` gives `inf`/`nan`. Handle `T == 0` as a special case with `np.argmax`.
- **Forgetting to renormalize.** After masking, the probabilities no longer add up to 1. Samplers such as `rng.choice` reject `p` that does not sum to 1.
- **Inclusive versus exclusive cumsum in top-p.** The off-by-one discussed above can silently drop the token that crosses the threshold. With a very peaked distribution and the wrong comparison, it can even drop every token, and you end up dividing by 0.
- **Unstable softmax.** Without `z - z.max()`, large logits or small T overflow.
- **"T=0 is deterministic."** It is deterministic only if the logits are bit-identical. GPU reduction order and batching can break that.

Interview follow-ups:

- *Implement softmax without the max trick, explain why it fails, then fix it.* Covered above.
- *Do top-k without a full sort.* Use `np.argpartition(p, -k)[-k:]`, which runs in O(V).
- *Why apply temperature before softmax rather than after?* Dividing logits by T is equivalent to raising the probabilities to the power 1/T and then renormalizing. That is the well-defined way to sharpen or flatten a distribution, and it keeps the ranking.
- *Top-k or top-p?* Top-p adapts to how confident the model is. Top-k is simpler and has a fixed cost. Many APIs let you set both.

## Further reading

- [NumPy `numpy.exp`](https://numpy.org/doc/stable/reference/generated/numpy.exp.html)
- [NumPy `numpy.argsort`](https://numpy.org/doc/stable/reference/generated/numpy.argsort.html)
- [NumPy `numpy.cumsum`](https://numpy.org/doc/stable/reference/generated/numpy.cumsum.html)
- [NumPy `Generator.choice`](https://numpy.org/doc/stable/reference/random/generated/numpy.random.Generator.choice.html)

<!-- studio-job: llm-temperature-top-k-and-top-p-nucleus-sampling-how-a-model -->
