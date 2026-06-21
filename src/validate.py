# -*- coding: utf-8 -*-
"""
validate.py
4주차 산출물: 전략이 '우연이 아닌지' 검증하는 도구 모음.
  1) grid_search       : 파라미터 조합별 성과 (과최적화/민감도 점검)
  2) in_out_sample     : 학습구간에서 고른 파라미터를 미래(검증구간)에 적용
  3) walk_forward      : 구간을 굴려가며 재최적화·검증 (가장 현실적)

핵심 사고방식:
  - 과거 전체에 가장 잘 맞는 값을 찾는 것은 '과최적화'다.
  - 진짜 질문은 "한 시기에 고른 규칙이, 본 적 없는 다음 시기에도 통하는가?"
"""
import itertools
import pandas as pd
from strategy import BreakoutParams
from backtest import CostModel, backtest_portfolio


# ---------- 데이터 기간 자르기 ----------
def slice_data(price_data: dict, start=None, end=None) -> dict:
    out = {}
    for t, df in price_data.items():
        d = df
        if start is not None:
            d = d[d.index >= pd.Timestamp(start)]
        if end is not None:
            d = d[d.index <= pd.Timestamp(end)]
        if len(d) > 130:   # 지표 워밍업에 충분한 길이만
            out[t] = d
    return out


# ---------- 성과 점수 (최적화 목표) ----------
def score(metrics: dict, min_trades: int = 20) -> float:
    """Sharpe를 기준으로 하되, 매매가 너무 적으면 신뢰 불가 → 제외."""
    if metrics.get("n_trades", 0) < min_trades:
        return -999.0
    s = metrics.get("Sharpe")
    return float(s) if s is not None and pd.notna(s) else -999.0


# ---------- 1) 그리드서치 (민감도/과최적화 점검) ----------
def grid_search(price_data: dict, grid: dict, cost: CostModel = CostModel(),
                **bt_kwargs) -> pd.DataFrame:
    keys = list(grid.keys())
    rows = []
    for combo in itertools.product(*[grid[k] for k in keys]):
        kw = dict(zip(keys, combo))
        p = BreakoutParams(**kw)
        res = backtest_portfolio(price_data, p, cost, **bt_kwargs)
        m = res["metrics"]
        rows.append({**kw, **m, "score": score(m)})
    df = pd.DataFrame(rows).sort_values("score", ascending=False).reset_index(drop=True)
    return df


def best_params_from(grid_df: pd.DataFrame, grid_keys) -> BreakoutParams:
    top = grid_df.iloc[0]
    kw = {k: (int(top[k]) if k != "stop_pct" else float(top[k])) for k in grid_keys}
    return BreakoutParams(**kw)


# ---------- 2) 학습/검증 분리 (In-sample / Out-of-sample) ----------
def in_out_sample(price_data: dict, split_date: str, grid: dict,
                  cost: CostModel = CostModel(), **bt_kwargs) -> dict:
    grid_keys = list(grid.keys())
    train = slice_data(price_data, end=split_date)
    test = slice_data(price_data, start=split_date)

    # 학습구간에서 최적 파라미터 탐색
    gdf = grid_search(train, grid, cost, **bt_kwargs)
    best = best_params_from(gdf, grid_keys)

    # 같은 파라미터를 학습/검증 각각에 적용
    is_metrics = backtest_portfolio(train, best, cost, **bt_kwargs)["metrics"]
    oos_metrics = backtest_portfolio(test, best, cost, **bt_kwargs)["metrics"]
    return {"best": best, "in_sample": is_metrics, "out_sample": oos_metrics, "grid": gdf}


# ---------- 3) Walk-forward ----------
def walk_forward(price_data: dict, grid: dict, folds: list,
                 cost: CostModel = CostModel(), **bt_kwargs) -> pd.DataFrame:
    """
    folds: [(train_start, train_end, test_start, test_end), ...]
    각 fold에서 train으로 최적화 → test로 검증. test(OOS) 성과만 모아 보고.
    """
    grid_keys = list(grid.keys())
    rows = []
    for (tr_s, tr_e, te_s, te_e) in folds:
        train = slice_data(price_data, start=tr_s, end=tr_e)
        test = slice_data(price_data, start=te_s, end=te_e)
        if not train or not test:
            continue
        gdf = grid_search(train, grid, cost, **bt_kwargs)
        best = best_params_from(gdf, grid_keys)
        oos = backtest_portfolio(test, best, cost, **bt_kwargs)["metrics"]
        rows.append({
            "test_period": f"{te_s}~{te_e}",
            "params": f"H{best.entry_high}/L{best.exit_low}/MA{best.trend_ma}/S{best.stop_pct}",
            "OOS_CAGR_%": oos.get("CAGR_%"),
            "OOS_MDD_%": oos.get("MDD_%"),
            "OOS_Sharpe": oos.get("Sharpe"),
            "OOS_trades": oos.get("n_trades"),
            "OOS_PF": oos.get("profit_factor"),
        })
    return pd.DataFrame(rows)
