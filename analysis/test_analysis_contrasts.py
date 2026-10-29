"""Synthetic-data checks for analysis_contrasts.py.

Run from the folder that contains analysis_contrasts.py:
    python test_analysis_contrasts.py
It should end with "ALL CHECKS PASSED". Run it again after any change to the analysis code.

What it checks: one score per need (mean over wordings; main wording for the sensitivity analysis),
the C3a copy, contrast arithmetic (including P5-P7 with C7f and the extras X11-X16), the t-test,
the exact sign-flip test (against brute force), equivalence and non-inferiority tests (against
scipy's one-sided tests), Holm, zero-variance handling, the missing-primary-contrast guard, the
classification labels, which contrasts are available for the GPT model, LA and EAA on the original
questions only, the separate analyses of the original and new questions, the wording analysis,
the process summary, the minimum detectable effect (against a simulation), and the overlap
sensitivity analysis (contrasts without the overlap needs).
"""

import itertools
import sys

import numpy as np
import pandas as pd
from scipy import stats

sys.path.insert(0, ".")
import analysis_contrasts as A  # noqa: E402

# Synthetic runs (same generator as make_fake_runs.py, which is kept out of git): 20 original
# questions (one need each) and 40 new questions in 26 needs, 9 of them with more than one wording.
CLAUDE = A.CLAUDE
CLAUDE_CFGS = ["C0", "C1", "C2", "C3", "C4", "C4w", "C4p", "C5", "C6", "C7", "C7t", "C7f", "C3n", "C6n", "C7n"]
GPT_CFGS = ["C1", "C3", "C4", "C5", "C6", "C7", "C7t", "C7f", "C3n", "C6n", "C7n"]
# True success log-odds per configuration (made up): C4 much better than C3, C5 == C4.
BASE = dict(C0=-6, C1=2.5, C2=1.5, C3=0.2, C4=1.5, C4w=1.5, C4p=0.2, C5=1.5, C6=1.3, C7=1.4,
            C7t=2.3, C7f=2.6, C3n=-0.5, C6n=0.4, C7n=0.9)
N_ORIG = 20
NEW_WORDINGS = [4, 3, 3, 3, 2, 2, 2, 2, 2] + [1] * 17      # 26 new needs, 40 new questions


def layout(rng):
    """(qid, qset, need, main_wording) for every question."""
    out = [(f"P{i}", "original", f"N{i:02d}", 1) for i in range(1, N_ORIG + 1)]
    q = N_ORIG
    for k, n in enumerate(NEW_WORDINGS, start=N_ORIG + 1):
        main = rng.integers(n)
        for j in range(n):
            q += 1
            out.append((f"P{q}", "new", f"N{k:02d}", int(j == main)))
    return out


def make(rng, model, cfgs, questions, runs, shift=0.0):
    rows = []
    need_effect = {n: rng.normal(0, 1.2) for n in {q[2] for q in questions}}
    wording_effect = {q[0]: rng.normal(0, 0.5) for q in questions}
    for c in cfgs:
        for qid, qset, need, main in questions:
            p = 1 / (1 + np.exp(-(BASE[c] + need_effect[need] + wording_effect[qid] + shift)))
            for r in range(1, runs + 1):
                y = rng.random() < p
                orig = qset == "original"
                rows.append(dict(benchmark="qp", qset=qset, model=model, config=c, qid=qid, need=need,
                                 main_wording=main, run_idx=r,
                                 la=int(y or rng.random() < .3),
                                 ea_a=int(y) if orig else np.nan, ea_s=int(y),
                                 ea_m=int(y or rng.random() < .1), ct_s=rng.lognormal(1, 0.2),
                                 skill_loaded=int(c in ("C5", "C7f") or (c in ("C6n", "C7n") and rng.random() < .25)),
                                 tokens_in=int(rng.normal(2500, 200)), tokens_out=int(rng.normal(120, 20)), n_calls=1))
    return rows


def fake_runs(seed=1, runs=5, gpt="gpt"):
    rng = np.random.default_rng(seed)
    questions = layout(rng)
    return pd.DataFrame(make(rng, CLAUDE, CLAUDE_CFGS, questions, runs)
                        + make(rng, gpt, GPT_CFGS, questions, runs, shift=-0.3))


rng = np.random.default_rng(1)
GPT = "gpt"
runs = A.add_c3a(fake_runs(seed=1, gpt=GPT))
pn = A.per_need(runs)
N_NEEDS, N_NEW_NEEDS, N_MULTI = 46, 26, 9

out = A.analyse(pn, "ea_s", A.CLAUDE)
print(out[out["class"].notna()][["id", "est", "lo", "hi", "p_holm", "p_eq_holm", "class"]]
      .round(4).to_string(index=False))

# 1. one score per need: the mean over its wordings, each wording averaged over its runs
q = runs[(runs.model == A.CLAUDE) & (runs.config == "C4") & (runs.need == "N21")]
assert q.qid.nunique() == 4
manual = q.groupby("qid")["ea_s"].mean().mean()
assert np.isclose(pn.query("model == @A.CLAUDE and config == 'C4' and need == 'N21'")["ea_s"].iloc[0], manual)
assert pn.query("model == @A.CLAUDE and config == 'C4'").shape[0] == N_NEEDS
# 2. sensitivity: only the main wording
pm = A.per_need(runs, how="main")
main_q = q[q.main_wording == 1]
assert main_q.qid.nunique() == 1
assert np.isclose(pm.query("model == @A.CLAUDE and config == 'C4' and need == 'N21'")["ea_s"].iloc[0],
                  main_q["ea_s"].mean())
try:
    A.per_need(runs.assign(main_wording=1), how="main")
    raise SystemExit("FAIL: two main wordings in one need not detected")
except ValueError as e:
    print("main-wording check OK:", e)
# 3. C3a is a copy of C3; X2 (C3 - C3a) is then zero and dropped
assert set(runs.query("model == @A.CLAUDE").config) >= {"C3", "C3a"}
assert "X2" not in set(out.id)
W = A.wide(pn, "ea_s", A.CLAUDE)
assert np.allclose(W.C3, W.C3a)
# 4. contrast arithmetic
assert np.allclose(A.contrast_values(A.CONTRASTS["P5"], W), W.C7f - W.C5)
assert np.allclose(A.contrast_values(A.CONTRASTS["P6"], W), W.C7f - W.C7t)
assert np.allclose(A.contrast_values(A.CONTRASTS["P7"], W), W.C7f - W.C1)
assert np.allclose(A.contrast_values(A.CONTRASTS["X11"], W), W.C7 - W.C7f)
assert np.allclose(A.contrast_values(A.CONTRASTS["X15"], W), W.C6n - W.C3n)
assert np.allclose(A.contrast_values(A.CONTRASTS["X5"], W), W.C4 - W.C4p)
# 5. t-test matches scipy
d = A.contrast_values(A.CONTRASTS["P3"], W).to_numpy()
assert len(d) == N_NEEDS
assert np.isclose(A.paired_t(d)[0], stats.ttest_1samp(d, 0).pvalue)
# 6. exact sign-flip matches brute force
small = np.array([0.1, 0.3, -0.1, 0.2, 0, 0.4, 0.1, -0.2])
nz = small[small != 0]
bf = np.mean([abs(sum(s * x for s, x in zip(sg, nz))) >= abs(nz.sum()) - 1e-9
              for sg in itertools.product([1, -1], repeat=len(nz))])
assert np.isclose(A.signflip_p(small, rng)[0], bf)
# 7. equivalence and non-inferiority match scipy one-sided tests
tost = max(stats.ttest_1samp(d, -.1, alternative="greater").pvalue,
           stats.ttest_1samp(d, .1, alternative="less").pvalue)
assert np.isclose(A.equivalence_p(d), tost)
assert np.isclose(A.equivalence_p(d, noninferiority=True),
                  stats.ttest_1samp(d, -.1, alternative="greater").pvalue)
# 8. Holm matches a textbook example
assert np.allclose(A.holm(np.array([0.01, 0.04, 0.03, 0.005])), [0.03, 0.06, 0.06, 0.02])
# 9. zero-variance handling
assert A.paired_t(np.zeros(20))[0] == 1.0 and A.paired_t(np.full(20, 0.1))[0] == 0.0
assert A.equivalence_p(np.zeros(20)) == 0.0 and A.equivalence_p(np.full(20, 0.2)) == 1.0
# 10. missing primary configuration raises an error
try:
    A.analyse(pn[pn.config != "C7f"], "ea_s", A.CLAUDE)
    raise SystemExit("FAIL: missing primary contrast not detected")
except ValueError as e:
    print("missing-primary check OK:", e)
# 11. labels are from the allowed sets; seven primary contrasts; the sensitivity analysis is not classified
allowed = {"higher", "lower", "trivial effect", "equivalent", "inconclusive"}
lab = out.set_index("id")["class"].dropna()
assert len(lab) == 7
assert all(lab[f"P{i}"] in allowed for i in range(1, 7))
assert lab["P7"] in {"superior", "non-inferior", "inferior", "inconclusive"}
sens = A.analyse(pm, "ea_s", A.CLAUDE, classify=False, aggregation="main_wording")
assert sens["class"].isna().all() and (sens["aggregation"] == "main_wording").all() and sens.n_needs.iloc[0] == N_NEEDS
# 12. contrasts available for the GPT model
key = lambda s: (s[0], int(s[1:]))
gpt = A.analyse(pn, "ea_s", GPT)
print("GPT contrasts:", sorted(gpt.id, key=key))
assert sorted(gpt.id, key=key) == ["P3", "P4", "P5", "P6", "P7", "X6", "X7", "X8", "X9", "X10",
                                   "X11", "X12", "X13", "X14", "X15", "X16"]
# 13. EAA exists for the original questions only; LA is analysed on each question set separately
assert A.analyse(pn, "ea_a", A.CLAUDE)["n_needs"].iloc[0] == 20
la_parts = A.subset_analysis(runs, A.CLAUDE, metric="la")
assert {(s["benchmark"].iloc[0], int(s["n_needs"].iloc[0])) for s in la_parts} == {("qp_original", 20), ("qp_new", N_NEW_NEEDS)}
assert all((s["metric"] == "la").all() and s["class"].isna().all() for s in la_parts)
# 14. separate analyses of original and new questions (exploratory, not classified)
subs = A.subset_analysis(runs, A.CLAUDE)
labels = sorted({s["benchmark"].iloc[0] for s in subs})
print("subsets:", labels, [int(s["n_needs"].iloc[0]) for s in subs])
assert labels == ["qp_new", "qp_original"]
assert all(s["class"].isna().all() for s in subs)
assert {int(s["n_needs"].iloc[0]) for s in subs} == {20, N_NEW_NEEDS}
print("model difference P3:", {k: round(v, 4) if isinstance(v, float) else v
                                 for k, v in A.model_difference(pn, "P3", GPT).items()})
# 15. wording analysis: needs with more than one wording
detail, summary = A.wording_analysis(runs)
s = summary.query("model == @A.CLAUDE and config == 'C4'").iloc[0]
assert s.n_needs == N_MULTI
per_q = q.groupby("qid")["ea_s"].mean()
row = detail.query("model == @A.CLAUDE and config == 'C4' and need == 'N21'").iloc[0]
assert row.n_wordings == 4 and np.isclose(row.spread, per_q.max() - per_q.min())
assert np.isclose(s.share_spread_flagged,
                  np.mean(detail.query("model == @A.CLAUDE and config == 'C4'").spread >= A.SPREAD_FLAG))
print("wording analysis (Claude):", summary.query("model == @A.CLAUDE")[["config", "n_needs", "mean_spread"]]
      .round(3).head(4).to_dict("records"))
# 16. process summary: skill load rate per configuration
ps = A.process_summary(runs).set_index(["model", "config"])
assert ps.loc[(A.CLAUDE, "C5"), "skill_loaded"] == 1 and ps.loc[(A.CLAUDE, "C3"), "skill_loaded"] == 0
# 17. MDE against simulation (46 needs, 7 primary contrasts)
sd = 0.30
dl = A.mde(sd, n=N_NEEDS)
sims = rng.normal(dl, sd, (20000, N_NEEDS))
power = np.mean(stats.ttest_1samp(sims, 0, axis=1).pvalue < 0.05 / 7)
print(f"MDE(sd=0.30, n={N_NEEDS}) = {dl:.3f}, simulated power = {power:.3f}")
assert abs(power - 0.8) < 0.02
for n in (20, 40, 46, 60, 80):      # the function must not fail across the planning range
    for sdv in (0.2, 0.3, 0.4):
        assert 0 < A.mde(sdv, n=n) < 1
# 18. time has no equivalence test
assert A.analyse(pn, "ct_log", A.CLAUDE)["p_eq"].isna().all()
# 19. overlap sensitivity: the same contrasts without 7 needs, classified with the same rules
assert len(A.OVERLAP_NEEDS) == 7
seven = ["N23", "N24", "N32", "N37", "N43", "N46", "N45"]          # the fake layout has needs N21-N46 only
ro = A.without_needs(runs, seven)
assert set(ro.need).isdisjoint(seven) and ro.need.nunique() == N_NEEDS - 7
so = A.analyse(A.per_need(ro), "ea_s", A.CLAUDE, aggregation="without_overlap")
assert (so.n_needs == N_NEEDS - 7).all() and so["class"].notna().sum() == 7
d_o = A.contrast_values(A.CONTRASTS["P3"], A.wide(A.per_need(ro), "ea_s", A.CLAUDE))
assert np.allclose(d_o, A.contrast_values(A.CONTRASTS["P3"], W).drop(seven))
try:
    A.without_needs(runs)                                              # N48 is not in the fake layout
    raise SystemExit("FAIL: a need missing from the runs not detected")
except ValueError as e:
    print("overlap-need check OK:", e)
QV2 = __import__("pathlib").Path("../data/questions_v2.jsonl")
if QV2.exists():                                                       # the real need IDs, once frozen
    import json
    qs = [json.loads(l) for l in QV2.read_text(encoding="utf-8").splitlines() if l.strip()]
    needs = {q["need"]: q["qset"] for q in qs if not q.get("_header")}
    assert all(needs.get(n) == "new" for n in A.OVERLAP_NEEDS) and len(needs) - 7 == 39
print("ALL CHECKS PASSED")
