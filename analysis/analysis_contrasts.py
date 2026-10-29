"""
Implements Section 3.4.3 of the manuscript and Supplementary S6:
per-need run-averaged correctness, t-tests over needs, exact (or Monte Carlo)
sign-flip tests, equivalence (TOST) or non-inferiority tests against delta, Holm
adjustment within the primary family, classification of the primary contrasts,
between-model differences, separate analyses of the original and new questions,
per-configuration summaries, the wording analysis, and the pre-run minimum detectable effect.

The unit of analysis is the information need: questions
that ask for the same information share a need ID, and each need gives one score per
configuration. Primary: the mean over the need's wordings (each wording first averaged over
its runs). Sensitivity: the need's main wording only (chosen at random with seed 2026 when the
questions were frozen). The wording analysis looks at needs with more than one wording.
Overlap sensitivity: the same contrasts without the needs in
OVERLAP_NEEDS, whose new questions are close to a few-shot example or answered by an original
question's answer query.

Requires numpy, scipy, pandas. Input: runs_scored.csv produced by scoring/rescore.py, with at
least the columns benchmark, qset, model, config, qid, need, main_wording, run_idx, la, ea_a,
ea_s, ea_m, ct_s (see the guide, section 7). qset is "original" or "new"; model is the model
key from configurations/models.yaml ("claude", "gpt"). EAA exists for the original questions only
(empty for the new ones). LA uses the published rules for the original questions and the author's rules
for the new ones, so its contrasts are computed separately on each question set, never pooled.

Usage:
    python analysis_contrasts.py runs_scored.csv --gpt gpt --out contrast_results.csv
"""

from __future__ import annotations

import argparse

import numpy as np
import pandas as pd
from scipy import optimize, stats

CLAUDE = "claude"               # model key as logged by the harness (configurations/models.yaml)
PRIMARY_BENCH = "qp"            # benchmark label for the main QP question set (original + new)
DELTA = 0.10                    # smallest difference of interest (10 percentage points)
METRICS = ["ea_s", "la", "ea_a", "ea_m"]
PROCESS = ["skill_loaded", "tokens_in", "tokens_out", "n_calls"]   # descriptive, per configuration
PRIMARY = [f"P{i}" for i in range(1, 8)]
NONINFERIORITY = {"P7"}
EXACT_SIGNFLIP_MAX = 22         # beyond this many non-zero differences, use Monte Carlo
MC_DRAWS = 1_000_000
SD_TOL = 1e-9                   # differences with smaller SD are treated as constant
SPREAD_FLAG = 0.5               # wording analysis: a need whose wordings differ by at least this much
# Overlap sensitivity: one small change from a few-shot example (N23, N24, N43, N48) or fully answered
# by an original question's answer query (N32, N37, N46).
OVERLAP_NEEDS = ["N23", "N24", "N32", "N37", "N43", "N46", "N48"]

# Signs follow tab:contrasts in the main text (new configuration minus reference).
# The original MCP script fixed the schema in the prompt, so C3 and C3a are the same
# configuration: it is run once as C3 and its rows are copied as C3a (add_c3a); X2 is then
# zero and dropped.
CONTRASTS: dict[str, dict[str, float]] = {
    "P1": {"C2": 1, "C1": -1},       # schema version: MCP-tool vs full
    "P2": {"C3a": 1, "C2": -1},      # interface: MCP server vs driver
    "P3": {"C4": 1, "C3": -1},       # generic skill content, as plain instructions
    "P4": {"C5": 1, "C4": -1},       # packaging that content as a loaded skill
    "P5": {"C7f": 1, "C5": -1},      # domain-specific vs generic skill, both loaded by the harness
    "P6": {"C7f": 1, "C7t": -1},     # domain content: as a loaded skill vs as a prompt
    "P7": {"C7f": 1, "C1": -1},      # domain skill vs Graph RAG (non-inferiority)
    "X1": {"C1": 1, "C0": -1},       # schema and examples in context
    "X2": {"C3": 1, "C3a": -1},      # schema delivery (only if C3 and C3a differ)
    "X3": {"C4w": 1, "C4": -1},      # wording
    "X4": {"C4p": 1, "C3": -1},      # irrelevant text of the same length
    "X5": {"C4": 1, "C4p": -1},      # content given length
    "X6": {"C6": 1, "C5": -1},       # model selection (generic skill)
    "X7": {"C7t": 1, "C4": -1},      # domain vs generic instructions
    "X8": {"C3": 1, "C1": -1},       # original comparison, re-run: Neo4j-MCP vs Graph RAG
    "X9": {"C5": 1, "C3": -1},       # original comparison, re-run: Agent Skill vs Neo4j-MCP
    "X10": {"C5": 1, "C1": -1},      # original comparison, re-run: Agent Skill vs Graph RAG
    "X11": {"C7": 1, "C7f": -1},     # model selection (domain skill): offered vs loaded by the harness
    "X12": {"C3": 1, "C3n": -1},     # examples, no skill
    "X13": {"C6": 1, "C6n": -1},     # examples, generic skill offered
    "X14": {"C7": 1, "C7n": -1},     # examples, domain skill offered
    "X15": {"C6n": 1, "C3n": -1},    # generic skill offered, without examples
    "X16": {"C7n": 1, "C3n": -1},    # domain skill offered, without examples
}


# ---------------------------------------------------------------------------
# Data preparation
# ---------------------------------------------------------------------------

def add_c3a(runs: pd.DataFrame) -> pd.DataFrame:
    """Copy C3's rows as C3a for every model that ran C3 but not C3a (C3 = C3a, see above)."""
    extra = []
    for model, sub in runs.groupby("model"):
        cfgs = set(sub["config"])
        if "C3" in cfgs and "C3a" not in cfgs:
            extra.append(sub[sub["config"] == "C3"].assign(config="C3a"))
    return pd.concat([runs] + extra, ignore_index=True) if extra else runs


def without_needs(runs: pd.DataFrame, needs: list[str] = OVERLAP_NEEDS) -> pd.DataFrame:
    """The runs without the given needs. Every need must be in the runs (guards against a mistyped ID)."""
    missing = sorted(set(needs) - set(runs["need"]))
    if missing:
        raise ValueError(f"need(s) not in the runs: {missing}")
    return runs[~runs["need"].isin(needs)]


def per_need(runs: pd.DataFrame, how: str = "average", metrics: list[str] | None = None) -> pd.DataFrame:
    """One value per (benchmark, model, config, need).

    Each wording (question) is first averaged over its runs (correctness: mean; CT: median of
    log CT). Then how="average" takes the mean over the need's wordings (primary), and
    how="main" keeps only the need's main wording (sensitivity analysis)."""
    if how not in ("average", "main"):
        raise ValueError(f"how must be 'average' or 'main', not {how!r}")
    metrics = metrics or METRICS
    runs = runs.assign(ct_log=np.log(runs["ct_s"]))
    if how == "main":
        runs = runs[runs["main_wording"] == 1]
    keys = ["benchmark", "model", "config", "need"]
    agg = {m: "mean" for m in metrics if m in runs.columns}
    agg["ct_log"] = "median"
    per_q = runs.groupby(keys + ["qid"], as_index=False).agg(agg)
    if how == "main" and per_q.groupby(keys)["qid"].nunique().gt(1).any():
        raise ValueError("a need has more than one main wording")
    return per_q.groupby(keys, as_index=False).agg({k: "mean" for k in agg})


def wide(pn: pd.DataFrame, metric: str, model: str, bench: str = PRIMARY_BENCH) -> pd.DataFrame:
    sub = pn[(pn["model"] == model) & (pn["benchmark"] == bench)].dropna(subset=[metric])
    return sub.pivot(index="need", columns="config", values=metric).sort_index()


def contrast_values(weights: dict[str, float], W: pd.DataFrame) -> pd.Series | None:
    """Per-need contrast values d_i, indexed by need. None if a configuration was not run."""
    if not set(weights).issubset(W.columns):
        return None
    X = W[list(weights)]
    if X.isna().any().any():
        raise ValueError(f"NA in {list(weights)}: incomplete runs or unrated EA_M?")
    d = X.to_numpy() @ np.array(list(weights.values()), dtype=float)
    return pd.Series(np.round(d, 10), index=W.index)   # rounding avoids spurious tiny variance


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

def paired_t(d: np.ndarray) -> tuple[float, float, float]:
    """Two-sided p-value and 95% CI for mean(d) = 0."""
    m = float(np.mean(d))
    if np.std(d, ddof=1) < SD_TOL:
        return (1.0 if m == 0 else 0.0), m, m
    res = stats.ttest_1samp(d, 0.0)
    ci = res.confidence_interval(0.95)
    return float(res.pvalue), float(ci.low), float(ci.high)


def signflip_p(d: np.ndarray, rng: np.random.Generator) -> tuple[float, str]:
    """Two-sided sign-flip test. Exact enumeration up to EXACT_SIGNFLIP_MAX non-zero values."""
    nz = d[np.abs(d) > 1e-12]
    if nz.size == 0:
        return 1.0, "exact"
    obs = abs(nz.sum())
    if nz.size <= EXACT_SIGNFLIP_MAX:
        sums = np.zeros(1)
        for x in nz:
            sums = np.concatenate([sums + x, sums - x])
        return float(np.mean(np.abs(sums) >= obs - 1e-9)), "exact"
    signs = rng.choice([-1.0, 1.0], size=(MC_DRAWS, nz.size))
    hits = np.sum(np.abs(signs @ nz) >= obs - 1e-9)
    return float((hits + 1) / (MC_DRAWS + 1)), "monte_carlo"


def equivalence_p(d: np.ndarray, delta: float = DELTA, noninferiority: bool = False) -> float:
    """TOST p-value against +/-delta, or one-sided non-inferiority p-value against -delta."""
    n, m = len(d), float(np.mean(d))
    sd = float(np.std(d, ddof=1))
    se = sd / np.sqrt(n)
    if sd < SD_TOL:
        if noninferiority:
            return 1.0 if m <= -delta else 0.0
        return 1.0 if abs(m) >= delta else 0.0
    p_lower = stats.t.sf((m + delta) / se, n - 1)       # H0: mu <= -delta
    if noninferiority:
        return float(p_lower)
    p_upper = stats.t.cdf((m - delta) / se, n - 1)      # H0: mu >= +delta
    return float(max(p_lower, p_upper))


def holm(p: np.ndarray) -> np.ndarray:
    """Holm step-down adjusted p-values."""
    p = np.asarray(p, dtype=float)
    order = np.argsort(p)
    m = len(p)
    adj = np.empty(m)
    running = 0.0
    for rank, idx in enumerate(order):
        running = max(running, (m - rank) * p[idx])
        adj[idx] = min(1.0, running)
    return adj


# ---------------------------------------------------------------------------
# Analysis
# ---------------------------------------------------------------------------

def analyse(pn: pd.DataFrame, metric: str, model: str, bench: str = PRIMARY_BENCH,
            seed: int = 20261007, classify: bool = True, aggregation: str = "average") -> pd.DataFrame | None:
    """All contrasts for one metric and model. The primary contrasts are Holm-adjusted and
    classified only for EA_S, Claude, the main benchmark and classify=True (the primary analysis)."""
    rng = np.random.default_rng(seed)
    W = wide(pn, metric, model, bench)
    rows = []
    for cid, w in CONTRASTS.items():
        s = contrast_values(w, W)
        if s is None:
            continue
        d = s.to_numpy()
        if cid == "X2" and np.all(d == 0):
            continue                                    # C3a is a copy of C3
        p, lo, hi = paired_t(d)
        p_sf, sf_method = signflip_p(d, rng)
        p_eq = np.nan if metric == "ct_log" else equivalence_p(d, noninferiority=(cid in NONINFERIORITY))
        rows.append(dict(id=cid, metric=metric, model=model, benchmark=bench, aggregation=aggregation,
                         n_needs=len(d), est=float(np.mean(d)), lo=lo, hi=hi, p=p,
                         p_signflip=p_sf, signflip_method=sf_method, p_eq=p_eq))
    if not rows:
        return None
    out = pd.DataFrame(rows)

    is_primary_run = classify and metric == "ea_s" and model == CLAUDE and bench == PRIMARY_BENCH
    if is_primary_run:
        missing = sorted(set(PRIMARY) - set(out["id"]))
        if missing:
            raise ValueError(f"primary contrast(s) missing: {missing}")
    is_p = out["id"].isin(PRIMARY) & is_primary_run
    out["p_holm"] = np.nan
    out["p_eq_holm"] = np.nan
    out["class"] = None
    if is_p.any():
        out.loc[is_p, "p_holm"] = holm(out.loc[is_p, "p"].to_numpy())
        out.loc[is_p, "p_eq_holm"] = holm(out.loc[is_p, "p_eq"].to_numpy())
        for i in out.index[is_p]:
            diff, eq = out.at[i, "p_holm"] < 0.05, out.at[i, "p_eq_holm"] < 0.05
            up = out.at[i, "est"] > 0
            if out.at[i, "id"] in NONINFERIORITY:
                out.at[i, "class"] = ("superior" if diff and up else
                                      "inferior" if diff else
                                      "non-inferior" if eq else "inconclusive")
            else:
                out.at[i, "class"] = ("trivial effect" if diff and eq else
                                      ("higher" if up else "lower") if diff else
                                      "equivalent" if eq else "inconclusive")
    return out


def subset_analysis(runs: pd.DataFrame, model: str, metric: str = "ea_s") -> list[pd.DataFrame]:
    """Exploratory: the same contrasts on the original and on the new questions separately."""
    if "qset" not in runs.columns:
        return []
    parts = []
    main = runs[runs["benchmark"] == PRIMARY_BENCH]
    for qs in sorted(main["qset"].dropna().unique()):
        label = f"{PRIMARY_BENCH}_{qs}"
        pn_sub = per_need(main[main["qset"] == qs].assign(benchmark=label))
        res = analyse(pn_sub, metric, model, bench=label)
        if res is not None:
            parts.append(res)
    return parts


def model_difference(pn: pd.DataFrame, cid: str, gpt: str, metric: str = "ea_s") -> dict | None:
    """t-test on d_i(Claude) - d_i(GPT), joined by need."""
    a = contrast_values(CONTRASTS[cid], wide(pn, metric, CLAUDE))
    b = contrast_values(CONTRASTS[cid], wide(pn, metric, gpt))
    if a is None or b is None:
        return None
    if not a.index.equals(b.index):
        raise ValueError(f"{cid}: need sets differ between models")
    diff = (a - b).to_numpy()
    p, lo, hi = paired_t(diff)
    return dict(id=cid, metric=metric, est=float(diff.mean()), lo=lo, hi=hi, p=p)


def config_summary(pn: pd.DataFrame, metric: str = "ea_s") -> pd.DataFrame:
    """Mean over needs of per-need values, with a t-interval over needs."""
    def ci(x: pd.Series) -> pd.Series:
        x = x.dropna().to_numpy()
        m, sd, n = x.mean(), x.std(ddof=1), len(x)
        h = 0.0 if sd < SD_TOL else stats.t.ppf(0.975, n - 1) * sd / np.sqrt(n)
        return pd.Series(dict(n_needs=n, mean=m, lo=m - h, hi=m + h))
    return pn.groupby(["benchmark", "model", "config"])[metric].apply(ci).unstack().reset_index()


def process_summary(runs: pd.DataFrame) -> pd.DataFrame:
    """Descriptive, per configuration: skill load rate, tokens and calls (mean over needs)."""
    cols = [c for c in PROCESS if c in runs.columns]
    pn = per_need(runs, metrics=cols)
    return pn.groupby(["benchmark", "model", "config"], as_index=False)[cols].mean()


def wording_analysis(runs: pd.DataFrame, metric: str = "ea_s") -> tuple[pd.DataFrame, pd.DataFrame]:
    """Needs with more than one wording: does a configuration answer a need equally well however it is asked?

    Per (model, config, need): each wording's run-averaged score, and the spread (highest minus
    lowest wording). Summary per (model, config): number of such needs, mean spread, and the share
    of needs whose wordings differ by at least SPREAD_FLAG."""
    main = runs[runs["benchmark"] == PRIMARY_BENCH]
    per_q = main.groupby(["model", "config", "need", "qid"], as_index=False)[metric].mean()
    multi = per_q.groupby(["model", "config", "need"])["qid"].transform("nunique") > 1
    per_q = per_q[multi]
    detail = (per_q.groupby(["model", "config", "need"])[metric]
              .agg(n_wordings="count", lowest="min", highest="max", mean="mean").reset_index())
    detail["spread"] = detail["highest"] - detail["lowest"]
    summary = (detail.groupby(["model", "config"])
               .agg(n_needs=("need", "count"), mean_spread=("spread", "mean"),
                    share_spread_flagged=("spread", lambda s: float(np.mean(s >= SPREAD_FLAG))))
               .reset_index())
    return detail, summary


def mde(sd_d: float, n: int = 46, m_family: int = len(PRIMARY), power: float = 0.8) -> float:
    """Smallest mean difference detectable with the given power by a two-sided t-test on
    n per-need values at the most stringent Holm level (0.05 / m_family)."""
    alpha = 0.05 / m_family
    df = n - 1
    t_crit = stats.t.ppf(1 - alpha / 2, df)
    se = sd_d / np.sqrt(n)

    def achieved(delta: float) -> float:
        nc = delta / se
        lower = np.nan_to_num(stats.nct.cdf(-t_crit, df, nc), nan=0.0)   # ~0; scipy can return NaN
        return stats.nct.sf(t_crit, df, nc) + lower - power

    return float(optimize.brentq(achieved, 1e-9 * se, (t_crit + 6) * se))   # power ~1 at upper bound


# ---------------------------------------------------------------------------

def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[1])
    ap.add_argument("runs_csv")
    ap.add_argument("--gpt", default=None, help="model key of the GPT runs, as logged (e.g. gpt)")
    ap.add_argument("--out", default="contrast_results.csv")
    args = ap.parse_args()

    runs = add_c3a(pd.read_csv(args.runs_csv))
    pn = per_need(runs)                         # primary: mean over each need's wordings
    pn_main = per_need(runs, how="main")        # sensitivity: each need's main wording

    parts = [analyse(pn, m, CLAUDE) for m in METRICS + ["ct_log"] if m != "la"]
    parts += subset_analysis(runs, CLAUDE, metric="la")     # LA: original and new needs separately, never pooled
    parts.append(analyse(pn_main, "ea_s", CLAUDE, classify=False, aggregation="main_wording"))
    runs_o = without_needs(runs)                # overlap sensitivity: primary aggregation, without OVERLAP_NEEDS
    parts += [analyse(per_need(runs_o), m, CLAUDE, aggregation="without_overlap") for m in ["ea_s", "ea_m"]]
    parts += [p.assign(aggregation="without_overlap") for p in subset_analysis(runs_o, CLAUDE, metric="la")]
    if args.gpt:
        parts += [analyse(pn, m, args.gpt) for m in ["ea_s", "ea_m"]]
        parts.append(analyse(pn_main, "ea_s", args.gpt, classify=False, aggregation="main_wording"))
    parts += subset_analysis(runs, CLAUDE)
    if args.gpt:
        parts += subset_analysis(runs, args.gpt)
    res = pd.concat([p for p in parts if p is not None], ignore_index=True)
    res.to_csv(args.out, index=False)

    print(res[res["class"].notna()][["id", "aggregation", "est", "lo", "hi", "p_holm", "p_eq_holm", "class"]]
          .to_string(index=False))
    if args.gpt:
        diffs = [model_difference(pn, c, args.gpt) for c in CONTRASTS]
        print(pd.DataFrame([x for x in diffs if x]).to_string(index=False))
    config_summary(pn).to_csv(args.out.replace(".csv", "_configs.csv"), index=False)
    process_summary(runs).to_csv(args.out.replace(".csv", "_process.csv"), index=False)
    detail, summary = wording_analysis(runs)
    detail.to_csv(args.out.replace(".csv", "_wording_needs.csv"), index=False)
    summary.to_csv(args.out.replace(".csv", "_wording.csv"), index=False)


if __name__ == "__main__":
    main()
