"""
Plain-share buy-low/sell-high trade ideas for Long Candidates. Short
Candidates are a caution/avoid list only - no shorting logic (needs margin).
Same rules as the stock_daily_pipeline.py tested earlier: stop = tighter of
lower Bollinger Band / 20-day low (clamped 8-15% below entry); target 1 =
20-day SMA (mean reversion); target 2 = upper Bollinger Band or 52wk high.
"""

BUDGET_TIERS = [50, 100, 500, 1000]
STOP_FLOOR_PCT = 0.08
STOP_CEIL_PCT = 0.15


def build_stock_idea(rec):
    if rec["classification"] != "Long Candidate":
        return None
    p = rec["price"]
    bb_mid, bb_lower, bb_upper = rec["bb_mid"], rec["bb_lower"], rec["bb_upper"]
    recent_low = rec.get("recent_low_20d")
    wk_high = rec.get("fifty_two_wk_high")
    if not p or not bb_mid:
        return None

    candidate_stops = [x for x in (bb_lower, recent_low) if x is not None and x < p]
    raw_stop = max(candidate_stops) if candidate_stops else p * (1 - STOP_FLOOR_PCT)
    stop = min(raw_stop, p * (1 - STOP_FLOOR_PCT))
    stop = max(stop, p * (1 - STOP_CEIL_PCT))
    risk_per_share = round(p - stop, 2)
    if risk_per_share <= 0:
        return None

    target1 = bb_mid if bb_mid > p else p * 1.05
    stretch_candidates = [x for x in (bb_upper, wk_high) if x is not None and x > p]
    target2 = min(stretch_candidates) if stretch_candidates else target1 * 1.05

    reward1 = round(target1 - p, 2)
    reward2 = round(target2 - p, 2)
    rr1 = round(reward1 / risk_per_share, 2) if risk_per_share else None
    rr2 = round(reward2 / risk_per_share, 2) if risk_per_share else None

    tiers = {}
    for budget in BUDGET_TIERS:
        shares = int(budget // p)
        tiers[f"${budget}"] = {
            "shares": shares,
            "dollars_deployed": round(shares * p, 2),
            "risk_if_stopped_out": round(shares * risk_per_share, 2),
            "gain_at_target1": round(shares * reward1, 2),
            "gain_at_target2": round(shares * reward2, 2),
        }

    return {
        "entry_price": round(p, 2), "stop_price": round(stop, 2), "risk_per_share": risk_per_share,
        "pct_risk": round(100 * risk_per_share / p, 2), "target1_price": round(target1, 2),
        "pct_gain_target1": round(100 * reward1 / p, 2), "risk_reward_target1": rr1,
        "target2_price": round(target2, 2), "pct_gain_target2": round(100 * reward2 / p, 2),
        "risk_reward_target2": rr2, "budget_tiers": tiers,
    }


def annotate_stock_ideas(records):
    for rec in records.values():
        rec["stock_idea"] = build_stock_idea(rec)
    return records


TOP_IDEAS_N = 5


def select_top_stock_ideas(records, n=TOP_IDEAS_N, affordable_ceiling=None):
    """If affordable_ceiling is set (e.g. 100), ranks Long Candidates priced
    at or below that ceiling FIRST by net_score, then fills any remaining
    slots with higher-priced candidates. This fixes the gap found in the
    first live test run, where pure conviction-ranking surfaced $200+ stocks
    that returned 0 shares at small budget tiers."""
    candidates = [r for r in records.values() if r.get("stock_idea")]
    if affordable_ceiling:
        affordable = [r for r in candidates if r["price"] <= affordable_ceiling]
        pricier = [r for r in candidates if r["price"] > affordable_ceiling]
        affordable.sort(key=lambda r: -r["net_score"])
        pricier.sort(key=lambda r: -r["net_score"])
        chosen = (affordable + pricier)[:n]
    else:
        candidates.sort(key=lambda r: -r["net_score"])
        chosen = candidates[:n]

    picks = []
    for r in chosen:
        idea = r["stock_idea"]
        picks.append({
            "symbol": r["symbol"], "industry": r["industry"], "net_score": r["net_score"],
            "top_reasons": r["bull_reasons"][:2], **idea, "context_note": None,
        })
    return picks
