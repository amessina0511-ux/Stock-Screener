"""
Shared scoring engine for the Nasdaq-100 screener (GitHub Actions version).

Data source: Alpaca Market Data API (alpaca-py SDK) for daily bars only.
Alpaca does not provide valuation fundamentals (PE, market cap, dividend
yield) - those are computed locally from `data/fundamentals.json`, a curated
file with slow-moving numbers (net income, debt, equity, FCF, shares
outstanding, trailing EPS) combined with each day's live closing price.
See README.md for why this split exists.

This module is deliberately identical in its scoring RULES to the original
Nasdaq-100 options screener (claude_daily_pipeline.py) - only the data
plumbing changed (Webull -> Alpaca, snapshot fields -> computed fields).
Both options_pipeline.py and stock_pipeline.py import build_records() from
here so the two screeners never drift apart on what "bullish"/"bearish"
means.
"""
import os
import json
from datetime import datetime, timedelta, timezone
from statistics import mean, pstdev

HERE = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(HERE, "..", "data")

BARS_LOOKBACK_DAYS = 400  # calendar days back, so we clear 200 trading days for sma200


def get_alpaca_client():
    # Imported lazily so this module (and its scoring functions) can be used
    # / tested without the alpaca-py package installed, e.g. offline tests
    # against pre-fetched bar data that never call fetch_bars() at all.
    from alpaca.data.historical import StockHistoricalDataClient
    api_key = os.environ["ALPACA_API_KEY"]
    secret_key = os.environ["ALPACA_SECRET_KEY"]
    return StockHistoricalDataClient(api_key, secret_key)


def fetch_bars(symbols, client=None):
    """Fetch ~400 calendar days of daily bars for all symbols in one batched
    call. Returns {symbol: [ {time, open, high, low, close, volume}, ... ]}
    sorted oldest->newest, or omits a symbol entirely if Alpaca returned
    nothing for it (delisted/renamed/no data)."""
    from alpaca.data.requests import StockBarsRequest
    from alpaca.data.timeframe import TimeFrame
    from alpaca.data.enums import DataFeed
    client = client or get_alpaca_client()
    end = datetime.now(timezone.utc)
    start = end - timedelta(days=BARS_LOOKBACK_DAYS)

    request = StockBarsRequest(
        symbol_or_symbols=symbols,
        timeframe=TimeFrame.Day,
        start=start,
        end=end,
        feed=DataFeed.IEX,  # free-tier Alpaca accounts can't query SIP data
    )
    barset = client.get_stock_bars(request)
    # barset.data is {symbol: [Bar, ...]}
    out = {}
    for sym in symbols:
        bars = barset.data.get(sym)
        if not bars:
            continue
        clean = [{
            "time": b.timestamp.date().isoformat(),
            "open": float(b.open),
            "high": float(b.high),
            "low": float(b.low),
            "close": float(b.close),
            "volume": float(b.volume),
        } for b in bars]
        clean.sort(key=lambda x: x["time"])
        out[sym] = clean
    return out


def fetch_yahoo_volumes(symbols, lookback_days=40):
    """Fetch real consolidated daily volume from Yahoo Finance (yfinance) for
    all symbols. Alpaca's free tier can only query the IEX feed (see
    fetch_bars above), which reflects trades on a single small exchange -
    roughly 2-3% of true US equity volume - so last_volume/avg_vol20/
    rel_volume computed from it alone are unreliable and noisy. This pulls
    the real consolidated tape's volume instead, used as an override in
    compute_technicals(). Returns {symbol: {"last_volume": float,
    "avg_vol20": float}}; omits a symbol on any per-symbol failure, and
    returns {} (never raises) if the whole fetch fails, so callers can
    always fall back to the Alpaca-derived volume.
    """
    out = {}
    try:
        import yfinance as yf
    except ImportError:
        print("yfinance not installed - skipping Yahoo volume backfill")
        return out

    try:
        data = yf.download(
            tickers=symbols,
            period="2mo",
            interval="1d",
            group_by="ticker",
            auto_adjust=False,
            threads=True,
            progress=False,
        )
    except Exception as e:
        print(f"Yahoo Finance volume fetch failed entirely, keeping Alpaca-only volume: {e}")
        return out

    if data is None or data.empty:
        print("Yahoo Finance returned no data, keeping Alpaca-only volume")
        return out

    for sym in symbols:
        try:
            vols = data[sym]["Volume"].dropna() if len(symbols) > 1 else data["Volume"].dropna()
            if len(vols) < 2:
                continue
            last_vol = float(vols.iloc[-1])
            window = vols.iloc[-21:-1] if len(vols) >= 21 else vols.iloc[:-1]
            if len(window) == 0 or last_vol <= 0:
                continue
            avg_vol20 = float(window.mean())
            if avg_vol20 <= 0:
                continue
            out[sym] = {"last_volume": last_vol, "avg_vol20": avg_vol20}
        except Exception:
            continue  # missing/delisted on Yahoo - fall back to Alpaca for this symbol
    print(f"Yahoo Finance volume backfill: {len(out)}/{len(symbols)} symbols")
    return out


def rsi(closes, period=14):
    if len(closes) < period + 1:
        return None
    gains, losses = [], []
    for i in range(1, len(closes)):
        chg = closes[i] - closes[i - 1]
        gains.append(max(chg, 0))
        losses.append(max(-chg, 0))
    avg_gain = mean(gains[:period])
    avg_loss = mean(losses[:period])
    for i in range(period, len(gains)):
        avg_gain = (avg_gain * (period - 1) + gains[i]) / period
        avg_loss = (avg_loss * (period - 1) + losses[i]) / period
    if avg_loss == 0:
        return 100.0
    rs = avg_gain / avg_loss
    return 100 - (100 / (1 + rs))


def sma(closes, period):
    if len(closes) < period:
        return None
    return mean(closes[-period:])


def bollinger(closes, period=20, num_std=2):
    if len(closes) < period:
        return None, None, None, None
    window = closes[-period:]
    mid = mean(window)
    sd = pstdev(window)
    upper = mid + num_std * sd
    lower = mid - num_std * sd
    last = closes[-1]
    pct_b = (last - lower) / (upper - lower) if upper != lower else 0.5
    return mid, upper, lower, pct_b


OUTLIER_LOG_RETURN_THRESHOLD = 0.223  # ~25% single-day move, log-space


def historical_volatility(closes, window=60):
    import math
    sample = closes[-(window + 1):] if len(closes) > window else closes
    if len(sample) < 11:
        return None
    all_returns = [math.log(sample[i] / sample[i - 1]) for i in range(1, len(sample)) if sample[i - 1] > 0]
    log_returns = [r for r in all_returns if abs(r) <= OUTLIER_LOG_RETURN_THRESHOLD]
    if len(log_returns) < 10:
        log_returns = all_returns
    daily_sd = pstdev(log_returns)
    return daily_sd * math.sqrt(252)


def compute_technicals(all_bars, yahoo_volumes=None):
    """{symbol: [bars]} -> {symbol: technicals dict}

    yahoo_volumes: optional {symbol: {"last_volume", "avg_vol20"}} from
    fetch_yahoo_volumes(), used in place of the Alpaca/IEX-derived volume
    figures when available for that symbol (see fetch_yahoo_volumes
    docstring for why). Falls back to Alpaca's own bars per-symbol whenever
    Yahoo has no data for that symbol, so this never removes coverage.
    """
    yahoo_volumes = yahoo_volumes or {}
    yahoo_hits = 0
    results = {}
    for sym, bars in all_bars.items():
        closes = [b["close"] for b in bars]
        vols = [b["volume"] for b in bars]
        if len(closes) < 30:
            continue
        last_close = closes[-1]
        recent_low_20d = min(b["low"] for b in bars[-20:])
        recent_high_20d = max(b["high"] for b in bars[-20:])
        wk52_high = max(b["high"] for b in bars[-252:]) if len(bars) >= 30 else max(b["high"] for b in bars)
        wk52_low = min(b["low"] for b in bars[-252:]) if len(bars) >= 30 else min(b["low"] for b in bars)
        rsi14 = rsi(closes, 14)
        sma20 = sma(closes, 20)
        sma50 = sma(closes, 50)
        sma200 = sma(closes, 200) if len(closes) >= 200 else None
        bb_mid, bb_upper, bb_lower, pct_b = bollinger(closes, 20, 2)

        yv = yahoo_volumes.get(sym)
        if yv:
            avg_vol20 = yv["avg_vol20"]
            last_vol = yv["last_volume"]
            yahoo_hits += 1
        else:
            avg_vol20 = mean(vols[-20:]) if len(vols) >= 20 else None
            last_vol = vols[-1]
        rel_vol = (last_vol / avg_vol20) if avg_vol20 else None
        chg_5d = (closes[-1] / closes[-6] - 1) * 100 if len(closes) > 6 else None
        chg_20d = (closes[-1] / closes[-21] - 1) * 100 if len(closes) > 21 else None
        hv_annual = historical_volatility(closes, window=60)
        results[sym] = {
            "last_close": round(last_close, 2),
            "last_date": bars[-1]["time"],
            "day_high": round(bars[-1]["high"], 2),
            "day_low": round(bars[-1]["low"], 2),
            "recent_low_20d": round(recent_low_20d, 2),
            "recent_high_20d": round(recent_high_20d, 2),
            "fifty_two_wk_high": round(wk52_high, 2),
            "fifty_two_wk_low": round(wk52_low, 2),
            "rsi14": round(rsi14, 1) if rsi14 is not None else None,
            "sma20": round(sma20, 2) if sma20 else None,
            "sma50": round(sma50, 2) if sma50 else None,
            "sma200": round(sma200, 2) if sma200 else None,
            "bb_mid": round(bb_mid, 2) if bb_mid else None,
            "bb_upper": round(bb_upper, 2) if bb_upper else None,
            "bb_lower": round(bb_lower, 2) if bb_lower else None,
            "pct_b": round(pct_b, 3) if pct_b is not None else None,
            "avg_vol20": round(avg_vol20) if avg_vol20 else None,
            "last_volume": round(last_vol),
            "rel_volume": round(rel_vol, 2) if rel_vol else None,
            "volume_source": "yahoo" if yv else "alpaca_iex",
            "chg_5d_pct": round(chg_5d, 2) if chg_5d is not None else None,
            "chg_20d_pct": round(chg_20d, 2) if chg_20d is not None else None,
            "hv_annual": round(hv_annual, 4) if hv_annual is not None else None,
            "n_bars": len(closes),
        }
    print(f"Volume source: {yahoo_hits}/{len(results)} symbols used Yahoo Finance consolidated volume "
          f"({len(results) - yahoo_hits} fell back to Alpaca/IEX-only volume)")
    return results


def score(rec):
    """Identical bull/bear point rules to the original Nasdaq-100 screener."""
    bull, bear = 0.0, 0.0
    reasons_bull, reasons_bear = [], []

    rsi_v, pct_b, trend = rec["rsi14"], rec["pct_b"], rec["trend"]
    chg5, chg20, rel_vol = rec["chg_5d_pct"], rec["chg_20d_pct"], rec["rel_volume"]
    pe, de, fcf_y = rec["pe_ratio"], rec["debt_to_equity"], rec["fcf_yield_pct"]
    profitable, fcf = rec["profitable"], rec["fcf"]

    if rsi_v is not None:
        if rsi_v <= 30:
            bull += 20; reasons_bull.append(f"RSI oversold ({rsi_v:.1f})")
        elif rsi_v <= 40:
            bull += 10; reasons_bull.append(f"RSI approaching oversold ({rsi_v:.1f})")
        elif rsi_v >= 70:
            bear += 20; reasons_bear.append(f"RSI overbought ({rsi_v:.1f})")
        elif rsi_v >= 60:
            bear += 10; reasons_bear.append(f"RSI approaching overbought ({rsi_v:.1f})")

    if pct_b is not None:
        if pct_b <= 0.05:
            bull += 15; reasons_bull.append("price at/below lower Bollinger Band")
        elif pct_b <= 0.2:
            bull += 8; reasons_bull.append("price near lower Bollinger Band")
        elif pct_b >= 0.95:
            bear += 15; reasons_bear.append("price at/above upper Bollinger Band")
        elif pct_b >= 0.8:
            bear += 8; reasons_bear.append("price near upper Bollinger Band")

    if trend == "strong_uptrend":
        bull += 15; reasons_bull.append("strong uptrend (20>50>200 SMA)")
    elif trend == "uptrend":
        bull += 8; reasons_bull.append("uptrend (price above rising MAs)")
    elif trend == "strong_downtrend":
        bear += 15; reasons_bear.append("strong downtrend (20<50<200 SMA)")
    elif trend == "downtrend":
        bear += 8; reasons_bear.append("downtrend (price below falling MAs)")

    if chg20 is not None:
        if chg20 <= -10:
            bull += 8; reasons_bull.append(f"oversold momentum, 20d chg {chg20:.1f}%")
        elif chg20 >= 15:
            bear += 6; reasons_bear.append(f"extended momentum, 20d chg {chg20:.1f}% (mean reversion risk)")
    if chg5 is not None:
        if chg5 <= -8:
            bull += 5; reasons_bull.append(f"sharp 5d pullback {chg5:.1f}%")
        elif chg5 >= 10:
            bear += 5; reasons_bear.append(f"sharp 5d spike {chg5:.1f}% (mean reversion risk)")

    if rel_vol is not None and rel_vol >= 1.5:
        if bull > bear:
            bull += 5; reasons_bull.append(f"elevated volume ({rel_vol:.1f}x avg) confirming move")
        elif bear > bull:
            bear += 5; reasons_bear.append(f"elevated volume ({rel_vol:.1f}x avg) confirming move")

    if pe is not None and pe > 0:
        if pe < 15:
            bull += 10; reasons_bull.append(f"low PE ({pe:.1f})")
        elif pe > 50:
            bear += 10; reasons_bear.append(f"high PE ({pe:.1f})")
    elif pe is not None and pe <= 0:
        bear += 5; reasons_bear.append("negative earnings (PE n/m)")

    if profitable:
        bull += 5
    else:
        bear += 8; reasons_bear.append("unprofitable (negative net income)")

    if de is not None:
        if de < 0.5:
            bull += 5; reasons_bull.append(f"low leverage (D/E {de:.2f})")
        elif de > 2.0:
            bear += 8; reasons_bear.append(f"high leverage (D/E {de:.2f})")
    elif rec["total_equity"] is not None and rec["total_equity"] < 0:
        bear += 6; reasons_bear.append("negative shareholders' equity")

    if fcf is not None:
        if fcf < 0:
            bear += 8; reasons_bear.append("negative free cash flow")
        elif fcf_y is not None and fcf_y > 5:
            bull += 5; reasons_bull.append(f"strong FCF yield ({fcf_y:.1f}%)")

    return round(bull, 1), round(bear, 1), reasons_bull, reasons_bear


def build_records(technicals, fundamentals):
    """technicals: from compute_technicals(). fundamentals: the curated
    dict {symbol: {net_income, total_debt, total_equity, fcf, industry, fy,
    shares_outstanding, eps_ttm}}. market_cap and pe_ratio are computed here
    from today's price x the static shares/EPS numbers - see module docstring."""
    symbols = sorted(set(technicals) & set(fundamentals))
    records = {}
    for sym in symbols:
        t, fnd = technicals[sym], fundamentals[sym]
        p = t["last_close"]
        rec = {"symbol": sym, "price": p}
        rec["day_high"] = t.get("day_high")
        rec["day_low"] = t.get("day_low")
        rec["recent_low_20d"] = t.get("recent_low_20d")
        rec["recent_high_20d"] = t.get("recent_high_20d")
        rec["fifty_two_wk_high"] = t.get("fifty_two_wk_high")
        rec["fifty_two_wk_low"] = t.get("fifty_two_wk_low")
        rec["rsi14"] = t.get("rsi14")
        rec["sma20"] = t.get("sma20")
        rec["sma50"] = t.get("sma50")
        rec["sma200"] = t.get("sma200")
        rec["bb_mid"] = t.get("bb_mid")
        rec["bb_upper"] = t.get("bb_upper")
        rec["bb_lower"] = t.get("bb_lower")
        rec["pct_b"] = t.get("pct_b")
        rec["avg_vol20"] = t.get("avg_vol20")
        rec["last_volume"] = t.get("last_volume")
        rec["rel_volume"] = t.get("rel_volume")
        rec["volume_source"] = t.get("volume_source")
        rec["chg_5d_pct"] = t.get("chg_5d_pct")
        rec["chg_20d_pct"] = t.get("chg_20d_pct")
        rec["hv_annual"] = t.get("hv_annual")

        rec["net_income"] = fnd.get("net_income")
        rec["total_debt"] = fnd.get("total_debt")
        rec["total_equity"] = fnd.get("total_equity")
        rec["fcf"] = fnd.get("fcf")
        rec["industry"] = fnd.get("industry")
        rec["fy"] = fnd.get("fy")
        shares = fnd.get("shares_outstanding")
        eps = fnd.get("eps_ttm")
        rec["shares_outstanding"] = shares
        rec["eps_ttm"] = eps
        rec["market_cap"] = round(p * shares) if (p and shares) else None
        rec["pe_ratio"] = round(p / eps, 2) if (p and eps and eps != 0) else None

        te, td = rec["total_equity"], rec["total_debt"]
        rec["debt_to_equity"] = round(td / te, 3) if (te and te > 0 and td is not None) else None

        mc, fcf = rec["market_cap"], rec["fcf"]
        rec["fcf_yield_pct"] = round(100 * fcf / mc, 2) if (mc and fcf is not None and mc > 0) else None
        rec["profitable"] = (rec["net_income"] is not None and rec["net_income"] > 0)

        wh, wl = rec["fifty_two_wk_high"], rec["fifty_two_wk_low"]
        rec["pct_off_52wk_high"] = round(100 * (p - wh) / wh, 2) if (p and wh) else None
        rec["pct_above_52wk_low"] = round(100 * (p - wl) / wl, 2) if (p and wl) else None

        sma20, sma50, sma200 = rec["sma20"], rec["sma50"], rec["sma200"]
        if sma20 and sma50 and sma200:
            if sma20 > sma50 > sma200:
                trend = "strong_uptrend"
            elif sma20 < sma50 < sma200:
                trend = "strong_downtrend"
            elif p and p > sma50 > sma200:
                trend = "uptrend"
            elif p and p < sma50 < sma200:
                trend = "downtrend"
            else:
                trend = "mixed"
        elif sma20 and sma50:
            if p and p > sma20 > sma50:
                trend = "uptrend"
            elif p and p < sma20 < sma50:
                trend = "downtrend"
            else:
                trend = "mixed"
        else:
            trend = "unknown"
        rec["trend"] = trend

        records[sym] = rec

    LONG_THRESH = SHORT_THRESH = 25
    MARGIN = 10
    for sym, rec in records.items():
        bull, bear, rb, rs_ = score(rec)
        rec["bull_score"] = bull
        rec["bear_score"] = bear
        net = bull - bear
        rec["net_score"] = round(net, 1)
        if bull >= LONG_THRESH and net >= MARGIN:
            classification = "Long Candidate"
        elif bear >= SHORT_THRESH and -net >= MARGIN:
            classification = "Short Candidate"
        else:
            classification = "Neutral"
        rec["classification"] = classification
        rec["bull_reasons"] = rb
        rec["bear_reasons"] = rs_

    return records


def load_fundamentals():
    with open(os.path.join(DATA_DIR, "fundamentals.json")) as f:
        return json.load(f)


def load_universe():
    with open(os.path.join(DATA_DIR, "universe.json")) as f:
        return json.load(f)
