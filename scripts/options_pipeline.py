"""
Options trade ideas for Long/Short Candidates - modeled pricing only (no live
options chain; see README.md for the same disclosure as the original
screener). Identical math to claude_daily_pipeline.py's build_trade_idea().
"""
import math
import datetime

IV_PREMIUM_MULTIPLIER = 1.2
RISK_FREE_RATE = 0.04  # update periodically; not fetched live
MIN_DTE_DAYS = 21


def next_standard_expiration(today=None):
    today = today or datetime.date.today()

    def third_friday(year, month):
        d = datetime.date(year, month, 1)
        fridays = 0
        while True:
            if d.weekday() == 4:
                fridays += 1
                if fridays == 3:
                    return d
            d += datetime.timedelta(days=1)

    year, month = today.year, today.month
    for _ in range(3):
        exp = third_friday(year, month)
        if (exp - today).days >= MIN_DTE_DAYS:
            return exp, (exp - today).days
        month += 1
        if month > 12:
            month = 1
            year += 1
    return exp, (exp - today).days


def _norm_cdf(x):
    return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))


def black_scholes(spot, strike, dte_days, r, q, sigma, option_type):
    if not spot or not strike or not sigma or sigma <= 0 or dte_days <= 0:
        return None
    T = dte_days / 365.0
    sqrtT = math.sqrt(T)
    d1 = (math.log(spot / strike) + (r - q + 0.5 * sigma * sigma) * T) / (sigma * sqrtT)
    d2 = d1 - sigma * sqrtT
    if option_type == "call":
        price = spot * math.exp(-q * T) * _norm_cdf(d1) - strike * math.exp(-r * T) * _norm_cdf(d2)
    else:
        price = strike * math.exp(-r * T) * _norm_cdf(-d2) - spot * math.exp(-q * T) * _norm_cdf(-d1)
    return max(price, 0.0)


def strike_step(price):
    if price < 25:
        return 0.5
    elif price < 50:
        return 1.0
    elif price < 100:
        return 2.5
    elif price < 500:
        return 5.0
    return 10.0


def round_to_strike(price):
    if price is None:
        return None
    step = strike_step(price)
    return round(price / step) * step


OPTION_EXPIRATION, OPTION_DTE_DAYS = next_standard_expiration()


def build_trade_idea(rec):
    if rec["classification"] not in ("Long Candidate", "Short Candidate"):
        return None
    p = rec["price"]
    hv = rec.get("hv_annual")
    if not p or not hv:
        return None

    iv_est = hv * IV_PREMIUM_MULTIPLIER
    atm_strike = round_to_strike(p)
    div_yield = 0.0  # dividend yield not fetched daily in this version; see README
    is_long = rec["classification"] == "Long Candidate"
    option_type = "call" if is_long else "put"

    premium = black_scholes(p, atm_strike, OPTION_DTE_DAYS, RISK_FREE_RATE, div_yield, iv_est, option_type)
    if premium is None:
        return None

    expected_move_pct = iv_est * math.sqrt(OPTION_DTE_DAYS / 365.0) * 100
    move_frac = expected_move_pct / 100.0
    target_price = p * (1 + move_frac) if is_long else p * (1 - move_frac)
    breakeven_price = atm_strike + premium if is_long else atm_strike - premium

    intrinsic_at_target = max(target_price - atm_strike, 0) if is_long else max(atm_strike - target_price, 0)
    reward_per_contract = round((intrinsic_at_target - premium) * 100, 2)
    pct_to_breakeven = round(100 * (breakeven_price - p) / p, 2) if is_long else round(100 * (p - breakeven_price) / p, 2)

    return {
        "option_type": option_type,
        "strike": atm_strike,
        "dte_days": OPTION_DTE_DAYS,
        "expiration": OPTION_EXPIRATION.isoformat(),
        "premium": round(premium, 2),
        "cost_per_contract": round(premium * 100, 2),
        "breakeven_price": round(breakeven_price, 2),
        "pct_move_to_breakeven": pct_to_breakeven,
        "target_price": round(target_price, 2),
        "pct_move_to_target": round(expected_move_pct if is_long else -expected_move_pct, 2),
        "est_reward_per_contract_at_target": reward_per_contract,
        "max_loss_per_contract": round(premium * 100, 2),
        "expected_move_pct": round(expected_move_pct, 2),
    }


TOP_IDEAS_N = 5
TOP_IDEAS_MAX_COST = 3000


def select_top_options_ideas(records, n=TOP_IDEAS_N, max_cost=TOP_IDEAS_MAX_COST):
    candidates = [r for r in records.values() if r.get("trade_idea")]
    candidates.sort(key=lambda r: abs(r["net_score"]), reverse=True)
    affordable = [r for r in candidates if r["trade_idea"]["cost_per_contract"] <= max_cost]
    pricier = [r for r in candidates if r["trade_idea"]["cost_per_contract"] > max_cost]
    chosen = (affordable + pricier)[:n]

    picks = []
    for r in chosen:
        ti = r["trade_idea"]
        reasons = r["bull_reasons"] if r["classification"] == "Long Candidate" else r["bear_reasons"]
        picks.append({
            "symbol": r["symbol"], "classification": r["classification"], "industry": r["industry"],
            "price": r["price"], "net_score": r["net_score"], "option_type": ti["option_type"],
            "strike": ti["strike"], "expiration": ti["expiration"], "dte_days": ti["dte_days"],
            "premium": ti["premium"], "cost_per_contract": ti["cost_per_contract"],
            "breakeven_price": ti["breakeven_price"], "pct_move_to_breakeven": ti["pct_move_to_breakeven"],
            "target_price": ti["target_price"], "pct_move_to_target": ti["pct_move_to_target"],
            "est_reward_per_contract_at_target": ti["est_reward_per_contract_at_target"],
            "top_reasons": reasons[:2], "context_note": None,
        })
    return picks


def annotate_options_ideas(records):
    """Mutates records in place, adding 'trade_idea' to each."""
    for rec in records.values():
        rec["trade_idea"] = build_trade_idea(rec)
    return records
