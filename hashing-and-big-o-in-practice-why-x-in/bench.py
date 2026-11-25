import timeit

N = 999_999
nums = list(range(1_000_000))
seen = set(nums)
tl = timeit.timeit(lambda: N in nums, number=100)
ts = timeit.timeit(lambda: N in seen, number=100)
print(f"list: {tl/100*1e3:.3f} ms per lookup")
print(f"set:  {ts/100*1e9:.0f} ns per lookup")
