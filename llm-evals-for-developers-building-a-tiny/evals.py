CASES = [
    {"q": "Capital of France?", "must": "paris"},
    {"q": "2 + 2?", "must": "4"},
    {"q": "Greet a user", "must": "hello", "tone": 1},
    {"q": "Deny a refund", "must": "sorry", "tone": 1},
]

def model(q):
    # stub: swap in your real LLM client here
    return {"Capital of France?": "Paris.",
            "2 + 2?": "It is 5.",
            "Greet a user": "Hello! Welcome aboard.",
            "Deny a refund": "Sorry, no."}[q]

def check(case, out):
    return case["must"] in out.lower()

def judge(out):
    # stub: ask an LLM "Is this friendly? PASS/FAIL"
    return "PASS" if "!" in out else "FAIL"

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
