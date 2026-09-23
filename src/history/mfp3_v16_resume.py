#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
MFP-3 v1.6 RESUME
Reanuda la v1.6 después del error de pandas 'Invalid frequency: ME'.

No repite el torneo.
Lee la carpeta existente mfp3_output_v16 y completa:
- Monte Carlo
- métricas finales
- señales paper actuales
- decisión Champion
"""

from pathlib import Path
import json
import numpy as np
import pandas as pd

OUTPUT = Path("mfp3_output_v16")
INITIAL_CAPITAL_CLP = 10_000_000
BASE_ONE_WAY_COST = 0.0015
TARGETS = ["QQQ", "ECH", "CPER"]

def perf(ret: pd.Series) -> dict:
    r = pd.Series(ret).fillna(0.0)
    curve = (1.0 + r).cumprod()
    total = float(curve.iloc[-1] - 1.0) if len(curve) else 0.0
    years = max(len(r) / 252.0, 1 / 252.0)
    cagr = float(curve.iloc[-1] ** (1.0 / years) - 1.0) if len(curve) else 0.0
    ann_vol = float(r.std() * np.sqrt(252)) if len(r) else 0.0
    sharpe = float(r.mean() * 252 / ann_vol) if ann_vol > 1e-12 else 0.0
    dd = curve / curve.cummax() - 1.0 if len(curve) else pd.Series(dtype=float)
    mdd = float(dd.min()) if len(dd) else 0.0
    fitness = sharpe + 0.35 * total - 0.65 * abs(mdd)
    return {
        "total_return": total,
        "cagr": cagr,
        "sharpe": sharpe,
        "max_drawdown": mdd,
        "ann_vol": ann_vol,
        "fitness": float(fitness),
    }

def monte_carlo_monthly(ret: pd.Series, n_sims: int = 2000) -> pd.DataFrame:
    r = ret.copy()
    r.index = pd.to_datetime(r.index)

    # pandas 2.1.x compatible
    monthly = (1 + r).resample("M").prod() - 1
    monthly = monthly.dropna().values

    if len(monthly) < 12:
        return pd.DataFrame()

    rng = np.random.default_rng(42)
    finals = []
    mdds = []

    for _ in range(n_sims):
        sample = rng.choice(monthly, size=len(monthly), replace=True)
        curve = INITIAL_CAPITAL_CLP * np.cumprod(1 + sample)
        peak = np.maximum.accumulate(curve)
        dd = curve / peak - 1.0
        finals.append(curve[-1])
        mdds.append(dd.min())

    return pd.DataFrame({
        "final_capital_clp": finals,
        "max_drawdown": mdds,
    })

def current_signals(selections: pd.DataFrame, daily: pd.DataFrame) -> pd.DataFrame:
    if selections.empty or daily.empty:
        return pd.DataFrame()

    latest_year = int(selections["test_year"].max())
    rows = []

    for asset in TARGETS:
        s = selections[
            (selections["asset"] == asset)
            & (selections["test_year"] == latest_year)
        ]

        d = daily[
            (daily["asset"] == asset)
            & (daily["year"] == latest_year)
        ].sort_index()

        if s.empty or d.empty:
            continue

        sel = s.iloc[-1]
        last = d.iloc[-1]
        prev = d.iloc[-2] if len(d) > 1 else last

        sig = float(last["signal"])
        prev_sig = float(prev["signal"])

        if sig > 0 and prev_sig <= 0:
            action = "COMPRAR (paper)"
        elif sig > 0:
            action = "MANTENER (paper)"
        elif prev_sig > 0:
            action = "VENDER / CASH (paper)"
        else:
            action = "CASH / NO OPERAR"

        rows.append({
            "date": d.index[-1],
            "asset": asset,
            "strategy": sel["strategy"],
            "horizon": int(sel["horizon"]),
            "threshold": sel["threshold"],
            "paper_action": action,
            "p_up": last["p_up"],
            "price_usd": last["price_usd"],
            "usdclp": last["usdclp"],
            "price_clp": last["price_clp"],
        })

    return pd.DataFrame(rows)

def champion_decision(portfolio, benchmark, costs, unresolved):
    p = perf(portfolio["portfolio_net_ret"])
    b = perf(benchmark)

    annual = (
        portfolio["portfolio_net_ret"]
        .groupby(portfolio.index.year)
        .apply(lambda s: (1 + s).prod() - 1)
    )
    positive_year_rate = float((annual > 0).mean())

    high_cost = costs[np.isclose(costs["one_way_cost"], 0.0030)]
    high_cost_return = float(high_cost.iloc[0]["total_return"]) if len(high_cost) else -999

    tests = {
        "data_quality_clean": unresolved == 0,
        "positive_total_return": p["total_return"] > 0,
        "sharpe_at_least_0_60": p["sharpe"] >= 0.60,
        "max_drawdown_better_than_-25pct": p["max_drawdown"] >= -0.25,
        "positive_year_rate_at_least_60pct": positive_year_rate >= 0.60,
        "still_positive_at_double_cost": high_cost_return > 0,
        "competitive_vs_benchmark": (
            p["sharpe"] >= b["sharpe"]
            or (
                abs(p["max_drawdown"]) <= 0.75 * abs(b["max_drawdown"])
                and p["cagr"] >= 0.70 * b["cagr"]
            )
        ),
    }

    return {
        "status": "CHAMPION" if all(tests.values()) else "CANDIDATE_NOT_CHAMPION",
        "tests": tests,
        "mfp": p,
        "benchmark": b,
        "positive_year_rate": positive_year_rate,
        "high_cost_total_return": high_cost_return,
    }

def main():
    required = [
        "portfolio_daily.csv",
        "fold_selections.csv",
        "time_machine_daily.csv",
        "cost_sensitivity.csv",
        "data_quality_report.csv",
    ]

    missing = [x for x in required if not (OUTPUT / x).exists()]
    if missing:
        raise SystemExit(
            "Faltan archivos de la ejecución v1.6: " + ", ".join(missing)
        )

    portfolio = pd.read_csv(
        OUTPUT / "portfolio_daily.csv",
        index_col=0,
        parse_dates=True,
    ).sort_index()

    selections = pd.read_csv(OUTPUT / "fold_selections.csv")
    daily = pd.read_csv(
        OUTPUT / "time_machine_daily.csv",
        index_col=0,
        parse_dates=True,
    ).sort_index()

    costs = pd.read_csv(OUTPUT / "cost_sensitivity.csv")
    quality = pd.read_csv(OUTPUT / "data_quality_report.csv")

    benchmark = portfolio["benchmark_ret"]

    mc = monte_carlo_monthly(portfolio["portfolio_net_ret"])
    mc.to_csv(OUTPUT / "monte_carlo.csv", index=False)

    if len(mc):
        mc_summary = pd.DataFrame([{
            "p05_final_capital": np.quantile(mc["final_capital_clp"], 0.05),
            "median_final_capital": np.quantile(mc["final_capital_clp"], 0.50),
            "p95_final_capital": np.quantile(mc["final_capital_clp"], 0.95),
            "p05_max_drawdown": np.quantile(mc["max_drawdown"], 0.05),
            "median_max_drawdown": np.quantile(mc["max_drawdown"], 0.50),
        }])
    else:
        mc_summary = pd.DataFrame()

    mc_summary.to_csv(OUTPUT / "monte_carlo_summary.csv", index=False)

    metrics = pd.DataFrame([
        {"name": "MFP3_v16_ROBUST", **perf(portfolio["portfolio_net_ret"])},
        {"name": "BENCHMARK_30_30_30_CLP", **perf(benchmark)},
    ])
    metrics.to_csv(OUTPUT / "metrics.csv", index=False)

    sig = current_signals(selections, daily)
    sig.to_csv(OUTPUT / "current_signals.csv", index=False)

    unresolved = int(
        quality.get("series", pd.Series(dtype=str))
        .astype(str)
        .str.contains("MONTHLY_CROSSCHECK", na=False)
        .sum()
    )

    decision = champion_decision(
        portfolio,
        benchmark,
        costs,
        unresolved,
    )

    (OUTPUT / "champion_decision.json").write_text(
        json.dumps(decision, indent=2, ensure_ascii=False, default=float),
        encoding="utf-8",
    )

    print("\n" + "=" * 90)
    print("MFP-3 v1.6 — REANUDACIÓN COMPLETADA")
    print("=" * 90)

    with pd.option_context("display.max_columns", None, "display.width", 180):
        print(metrics)

    print("\nCapital inicial:", f"${INITIAL_CAPITAL_CLP:,.0f} CLP")
    print("Capital final MFP-3:", f"${portfolio['capital_clp'].iloc[-1]:,.0f} CLP")
    print("Capital final benchmark:", f"${portfolio['benchmark_capital_clp'].iloc[-1]:,.0f} CLP")

    print("\nDECISIÓN:")
    print(decision["status"])
    for k, v in decision["tests"].items():
        print(f"  {'OK' if v else 'FALLA':5s}  {k}")

    print("\nSEÑALES PAPER ACTUALES")
    with pd.option_context("display.max_columns", None, "display.width", 180):
        print(sig)

    if len(mc_summary):
        print("\nMONTE CARLO")
        with pd.option_context("display.max_columns", None, "display.width", 180):
            print(mc_summary)

    print("\nArchivos completados en:", OUTPUT.resolve())

if __name__ == "__main__":
    main()
