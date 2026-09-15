"""
Outcome-tracking bank for both screeners. Same tracking model as the
original claude_merge_bank.py (best price touched since pick date vs.
target/breakeven/stop), adapted to:
  1. run standalone inside the GitHub Actions checkout (reads/writes
     data/options_bank.json and data/stock_bank.json directly - no
     calling agent needed to shuttle files to/from a Claude Project), and
  2. handle stock picks too, which have a stop-loss instead of an
     expiration date (no time-based resolution - only target-hit or
     stopped-out resolves a stock pick).
"""
import json
import os
import datetime

HERE = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(HERE, "..", "data")
BANK_MAX_DAYS = 120


def _favorable_price(is_long, price_info):
    if not price_info:
        return None
    if is_long:
        return price_info.get("high") if price_info.get("high") is not None else price_info.get("price")
    return price_info.get("low") if price_info.get("low") is not None else price_info.get("price")


def _unfavorable_price(is_long, price_info):
    """The worst price touched that day - used to check stop-loss hits for stock picks."""
    if not price_info:
        return None
    if is_long:
        return price_info.get("low") if price_info.get("low") is not None else price_info.get("price")
    return price_info.get("high") if price_info.get("high") is not None else price_info.get("price")


def update_options_outcome(pick, price_info, today_iso):
    if pick.get("resolved"):
        return pick
    is_long = pick["classification"] == "Long Candidate"
    target, breakeven, expiration, entry_price = pick["target_price"], pick["breakeven_price"], pick["expiration"], pick["price"]

    best = pick.get("best_price", entry_price)
    candidate = _favorable_price(is_long, price_info)
    if candidate is not None:
        if is_long and candidate > best:
            best = candidate
        elif (not is_long) and candidate < best:
            best = candidate
    pick["best_price"] = round(best, 2)
    pick["best_move_pct"] = round(100 * (best - entry_price) / entry_price, 2) if entry_price else None
    if price_info and price_info.get("price") is not None:
        pick["current_price"] = price_info["price"]
    pick["last_checked"] = today_iso

    cleared_breakeven = (best >= breakeven) if is_long else (best <= breakeven)
    hit_target = (best >= target) if is_long else (best <= target)

    if hit_target:
        pick["resolved"], pick["outcome"], pick["resolved_date"] = True, "target_hit", today_iso
    elif today_iso > expiration:
        pick["resolved"] = True
        pick["outcome"] = "expired_profitable" if cleared_breakeven else "expired_loss"
        pick["resolved_date"] = today_iso
    else:
        pick["resolved"] = False
        pick["outcome"] = "open_profitable" if cleared_breakeven else "open"
    return pick


def update_stock_outcome(pick, price_info, today_iso):
    """Long-only (no expiration): resolves on stop-loss hit (loss) or
    target1_price hit (win). Otherwise stays open indefinitely, tracking the
    best price touched since entry."""
    if pick.get("resolved"):
        return pick
    entry_price, stop, target1 = pick["entry_price"], pick["stop_price"], pick["target1_price"]

    best = pick.get("best_price", entry_price)
    fav = _favorable_price(True, price_info)
    if fav is not None and fav > best:
        best = fav
    pick["best_price"] = round(best, 2)
    pick["best_move_pct"] = round(100 * (best - entry_price) / entry_price, 2) if entry_price else None
    if price_info and price_info.get("price") is not None:
        pick["current_price"] = price_info["price"]
    pick["last_checked"] = today_iso

    worst = _unfavorable_price(True, price_info)
    stopped_out = worst is not None and worst <= stop
    hit_target = best >= target1

    if stopped_out:
        pick["resolved"], pick["outcome"], pick["resolved_date"] = True, "stopped_out", today_iso
    elif hit_target:
        pick["resolved"], pick["outcome"], pick["resolved_date"] = True, "target_hit", today_iso
    else:
        pick["resolved"] = False
        pick["outcome"] = "open_profitable" if best > entry_price else "open"
    return pick


def seed_options_pick(pick, today_iso):
    pick.update(resolved=False, outcome="open", best_price=pick["price"], best_move_pct=0.0,
                current_price=pick["price"], last_checked=today_iso)
    return pick


def seed_stock_pick(pick, today_iso):
    pick.update(resolved=False, outcome="open", best_price=pick["entry_price"], best_move_pct=0.0,
                current_price=pick["entry_price"], last_checked=today_iso)
    return pick


def _price_lookup_from_records(records):
    return {sym: {"price": r.get("price"), "high": r.get("day_high"), "low": r.get("day_low")}
            for sym, r in records.items()}


def merge_bank(bank_path, today_ideas, records, update_fn, seed_fn, today_iso):
    if os.path.exists(bank_path):
        with open(bank_path) as f:
            bank = json.load(f)
    else:
        bank = []

    price_lookup = _price_lookup_from_records(records)
    prior_entries = [e for e in bank if e.get("date") != today_iso]
    n_updated = 0
    for entry in prior_entries:
        for pick in entry.get("picks", []):
            if pick.get("resolved"):
                continue
            update_fn(pick, price_lookup.get(pick["symbol"]), today_iso)
            n_updated += 1

    for p in today_ideas:
        seed_fn(p, today_iso)

    bank = prior_entries + [{"date": today_iso, "picks": today_ideas}]
    bank.sort(key=lambda e: e["date"], reverse=True)
    bank = bank[:BANK_MAX_DAYS]

    with open(bank_path, "w") as f:
        json.dump(bank, f, indent=2)
    return bank, n_updated


def run_both_banks(options_records, options_top_ideas, stock_records, stock_top_ideas):
    today_iso = datetime.date.today().isoformat()
    options_bank, n1 = merge_bank(
        os.path.join(DATA_DIR, "options_bank.json"), options_top_ideas, options_records,
        update_options_outcome, seed_options_pick, today_iso)
    stock_bank, n2 = merge_bank(
        os.path.join(DATA_DIR, "stock_bank.json"), stock_top_ideas, stock_records,
        update_stock_outcome, seed_stock_pick, today_iso)

    print(f"Options bank: {len(options_bank)} day(s); updated {n1} open pick(s) today")
    print(f"Stock bank: {len(stock_bank)} day(s); updated {n2} open pick(s) today")
    return options_bank, stock_bank
