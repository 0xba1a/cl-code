# LLM Evals in Python: Unit Tests for Nondeterministic Code

You change one word in a prompt, try two or three inputs in a playground, and the answers "look better". Then you ship it. A week later someone notices that refund replies have turned rude, or that arithmetic answers are wrong. Nobody saw it because nobody was measuring. That is a **vibe check**, not a test.

An **eval** is the fix: a fixed set of inputs, an automatic way to score each output, and one number at the end (the pass rate) that you can compare before and after every prompt or model change. This lesson builds a complete eval harness in about 30 lines of plain Python, with no libraries and no API key.

When you finish, you will be able to:

- build a small labeled test set for an LLM feature,
- score outputs with cheap deterministic checks first and an LLM-as-judge only for fuzzy criteria,
- read the pass rate and the list of failures, and turn failures into new test cases,
- explain the trade-offs of judge-based scoring in an interview.

## The concept

### Evals are unit tests for nondeterministic code

A normal unit test says "for input X, the output must equal Y". LLM output rarely matches a string exactly. The same correct answer can come back as `"Paris."`, `"The capital is Paris"` or `"paris"`. So evals relax the assertion. Instead of *equals*, you check a **property** of the output:

| Criterion type | Example | How to score it |
|---|---|---|
| Objective, checkable in code | "answer mentions Paris" | substring, regex, JSON parse, number compare |
| Fuzzy, subjective | "reply is friendly" | ask another LLM (a **judge**) for PASS/FAIL |

The core rule of this harness is **assertions first, judge second**:

```
            input q
               |
               v
         +-----------+
         |  model(q) |  -> out
         +-----------+
               |
               v
   +-------------------------+   fail
   | deterministic check     |----------> FAIL (judge is never called)
   | "must" in out.lower()   |
   +-------------------------+
               | pass
               v
       case has "tone"? --- no ---> PASS
               | yes
               v
   +-------------------------+
   | judge(out) == "PASS" ?  |---- no --> FAIL
   +-------------------------+
               | yes
               v
              PASS
```

Why this order? Code checks are free, instant and give the same answer every time. Judge calls cost money, add latency (a whole extra model round trip), and can be wrong, because the judge is an LLM too. If the cheap check already fails, calling the judge only spends money to confirm a result you already know.

### Data structures and cost

- The test set is a **list of dicts**. Every case has a question `q` and a required substring `must`. Some cases also have an optional `tone` key that says "this case also needs the judge".
- The harness is one loop over the list, with a running integer counter.

Complexity: for *N* cases you make *N* model calls and at most *N* judge calls. The string work is a substring search on each output, which is linear in the output length. In practice the cost is almost all API calls. That is why the order of the checks matters more than anything else here.

Trade-offs:

- **Substring checks** are fast and stable, but they can be fooled: `"4"` also matches `"14"` or `"not 4"`.
- **LLM judges** handle nuance, but they are slow, cost money and are nondeterministic. You should check them against human labels from time to time.
- **Small test sets** are cheap to run on every change, but they only cover what you thought of. That is why the workflow matters: every real failure you find becomes a new case.

## Walking through the code

All the code is in [`evals.py`](evals.py). We go through it top to bottom.

### 1. The labeled test set

```python
CASES = [
    {"q": "Capital of France?", "must": "paris"},
    {"q": "2 + 2?", "must": "4"},
    {"q": "Greet a user", "must": "hello", "tone": 1},
    {"q": "Deny a refund", "must": "sorry", "tone": 1},
]
```

- `CASES` is a module-level constant (upper case by convention). It is the "golden" dataset: inputs paired with what a good answer must contain.
- `"q"` is the input sent to the model.
- `"must"` is the substring a good answer has to include. It is written in **lowercase** on purpose, because the check lowercases the output before comparing. An uppercase `must` would never match.
- `"tone": 1` is a flag. Only the key's presence matters (the code tests `"tone" in c`). The value `1` is never read. It marks cases with an extra fuzzy requirement: the reply must also be friendly.
- The four cases cover two kinds of behavior: factual answers (France, arithmetic) and style-sensitive replies (greeting, refusal).

### 2. The model call (stubbed)

```python
def model(q):
    # stub: swap in your real LLM client here
    return {"Capital of France?": "Paris.",
            "2 + 2?": "It is 5.",
            "Greet a user": "Hello! Welcome aboard.",
            "Deny a refund": "Sorry, no."}[q]
```

- `model(q)` is the only point where the harness talks to an LLM. Here it is a dictionary lookup, so the script runs offline and gives the same output every time.
- The canned answers are chosen to exercise each path: one correct answer, one wrong fact (`"It is 5."`), one friendly reply, and one reply that is correct but curt (`"Sorry, no."`).
- Indexing with `[q]` raises `KeyError` for an unknown question. That is fine for a stub. A real client would accept any string.
- Because the rest of the harness only depends on the signature `str -> str`, you can replace this body with a call to your provider's SDK without touching anything else.

### 3. The deterministic check

```python
def check(case, out):
    return case["must"] in out.lower()
```

- `out.lower()` normalizes case, so `"Paris."` becomes `"paris."`.
- `in` on strings is a substring test, and it returns a `bool`.
- This is the "cheap assertion": no network, no cost, and the same result every time.

### 4. The LLM-as-judge (stubbed)

```python
def judge(out):
    # stub: ask an LLM "Is this friendly? PASS/FAIL"
    return "PASS" if "!" in out else "FAIL"
```

- In production you would send `out` to a second model with a rubric such as "Is this friendly? Answer PASS or FAIL" and parse the reply.
- The stub fakes "friendly" as "contains an exclamation mark". That rule is crude, and the point is not the rule. The point is the **interface**: the judge returns the string `"PASS"` or `"FAIL"`. A constrained, binary verdict is much easier to parse and aggregate than free-form commentary or a 1–10 score.

### 5. The loop, the report and the pass rate

```python
passed = 0
for c in CASES:
    out = model(c["q"])
    ok = check(c, out)
    if ok and "tone" in c:
        ok = judge(out) == "PASS"
    passed += ok
    if not ok:
        print("FAIL:", c["q"], "->", out)
print(f"pass rate: {passed}/{len(CASES)}")
```

- `passed = 0` starts the counter.
- `out = model(c["q"])` gets the output for this case.
- `ok = check(c, out)` runs the cheap assertion first.
- `if ok and "tone" in c:` uses short-circuit evaluation. If `ok` is `False`, Python never evaluates the rest, so the judge is **never called** for an answer that already failed. This one line puts the cost rule into practice.
- `ok = judge(out) == "PASS"` overwrites `ok` with the judge's verdict. At this point a case passes only if both checks pass.
- `passed += ok` works because `bool` is a subclass of `int` in Python (`True == 1`, `False == 0`).
- `print("FAIL:", c["q"], "->", out)` prints every failure with its input and the actual output. `print` puts a single space between its arguments. Seeing the actual output is what makes the eval useful. A bare number does not tell you *what* broke.
- The final f-string prints the pass rate as `passed/total`. This is the number you compare across prompt or model versions.

## Run it yourself

Prerequisites: Python 3.12 or newer. The script uses only the standard language, so you do not need to install any packages.

```sh
python evals.py
```

Output:

```text
FAIL: 2 + 2? -> It is 5.
FAIL: Deny a refund -> Sorry, no.
pass rate: 2/4
```

Here is why the script prints exactly this:

1. **Capital of France?** → `"Paris."` → lowercased `"paris."` contains `"paris"` → `ok = True`. There is no `tone` key, so the case passes. `passed = 1`. Nothing is printed.
2. **2 + 2?** → `"It is 5."` → `"it is 5."` does not contain `"4"` → `ok = False`. The short-circuit skips the judge. `passed` stays 1. The script prints `FAIL: 2 + 2? -> It is 5.`
3. **Greet a user** → `"Hello! Welcome aboard."` → contains `"hello"` → `ok = True`. It has `tone`, so the judge runs: the output contains `!`, so the verdict is `"PASS"`. `passed = 2`.
4. **Deny a refund** → `"Sorry, no."` → contains `"sorry"` → `ok = True`. It has `tone`, so the judge runs: there is no `!`, so the verdict is `"FAIL"` and `ok = False`. The script prints `FAIL: Deny a refund -> Sorry, no.` The content is correct, but the tone is not.
5. After the loop: `passed = 2` and `len(CASES) = 4`, so the script prints `pass rate: 2/4`.

The two failures show the two ways a case can fail: a **factual** failure caught by code, and a **style** failure that only the judge catches.

## Try it

1. **Fix the math.** Change the stub answer for `"2 + 2?"` to `"It is 4."`. Prediction: one `FAIL` line disappears and the pass rate becomes `3/4`. Lesson: the pass rate is the regression signal you watch.
2. **Find a false positive.** Change that answer to `"It is 14."`. Prediction: it **passes**, because `"4"` is a substring of `"14"`. Lesson: substring checks are fragile. Try a stricter check such as a regex with word boundaries (`re.search(r"\b4\b", out)`) and confirm that it now fails.
3. **Prove the judge is skipped.** Add `print("judge called")` inside `judge`. Prediction: it prints twice (for the greeting and the refund), not four times. Lesson: short-circuiting is what keeps judge costs down.
4. **Add a case from a failure.** Add `{"q": "Cancel my order", "must": "cancel", "tone": 1}` to `CASES` and a matching stub answer. Choose an answer that fails, then one that passes. Lesson: this is the core workflow. Read failures, turn them into cases, and rerun on every change.
5. **Gate on a threshold.** Add `import sys` at the top of the file. At the end, call `sys.exit(1)` if `passed < len(CASES)`, and run `python evals.py; echo $?`. Lesson: a non-zero exit code is all a CI pipeline needs to block a bad prompt change.

## Common pitfalls

- **Case mismatch in `must`.** `check` lowercases only the output. A value like `"must": "Paris"` can never match. Either keep the expected values in lowercase or lowercase both sides.
- **Overly loose assertions.** A substring check accepts `"not 4"` and `"14"`. Use word-boundary regex, exact parsing (for example `int(...)`), or structured JSON output when the answer has a fixed format.
- **Trusting the judge blindly.** A judge is an LLM, so it can be biased, inconsistent or simply wrong. Spot-check its verdicts against human labels, keep its rubric narrow, and ask for a binary PASS/FAIL instead of an open-ended opinion.
- **Calling the judge first.** This wastes money and adds latency. Put the deterministic checks first and only call the judge for what code cannot decide.
- **Nondeterminism in the model under test.** A real model may pass on one run and fail on the next. Use temperature 0 where possible, or run each case several times and report a rate.
- **A tiny, stale dataset.** Four cases only prove that the harness works. Grow the set from real production failures, and keep it versioned next to the prompt.
- **Empty dataset.** With `CASES = []` the script prints `pass rate: 0/0`. If you change it to compute a percentage, guard against division by zero.

Interview follow-ups:

- *"How would you explain your eval strategy in one line?"* Assertions first, a judge for the fuzzy rest, run in CI, so no change ships on a vibe check.
- *"How do you know your judge is any good?"* Measure how often it agrees with human labels on a sample, and treat the judge prompt as code that has its own tests.
- *"Why not ask the judge for a 1–10 score?"* Binary verdicts are more consistent across runs and easier to aggregate and threshold.
- *"How would you plug this into CI?"* Exit with a non-zero code when the pass rate drops below a baseline, and run the eval on every prompt or model change.

## Further reading

- [Python docs: String methods (`str.lower`, `in`)](https://docs.python.org/3/library/stdtypes.html#string-methods)
- [Python docs: Boolean type (`bool` as a subclass of `int`)](https://docs.python.org/3/library/stdtypes.html#boolean-type-bool)
- [Python docs: Boolean operations and short-circuit evaluation](https://docs.python.org/3/reference/expressions.html#boolean-operations)
- [Python docs: `re` (regular expressions)](https://docs.python.org/3/library/re.html)

<!-- studio-job: llm-evals-for-developers-building-a-tiny-eval-harness-in-pyt -->
