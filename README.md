# Nasdaq-100 Screener (Options + Stocks, automated)

A daily rules-based screener over the Nasdaq-100 (102 symbols) that produces:
- **Options ideas**: top 5 Long/Short Candidates with modeled Black-Scholes
  pricing (strike, premium, breakeven, target)
- **Stock ideas**: top 5 Long Candidates as plain-share buy-low/sell-high
  plans (entry/stop/target + share counts at $50/$100/$500/$1000 budgets)
- A **news/context note** on each of those ~10 picks (Claude API + web
  search), checking whether recent news agrees or disagrees with the
  technical signal
- A running **bank** of every day's picks with outcome tracking (target
  hit / stopped out / expired), rendered as a live dashboard

Runs automatically on weekdays via GitHub Actions, deployed as a static
site on Cloudflare Pages.

## One-time setup

1. **Add three repository secrets** (Settings -> Secrets and variables ->
   Actions -> New repository secret):
   - `ALPACA_API_KEY`, `ALPACA_SECRET_KEY` - from your Alpaca account
     (Market Data API, free tier is enough)
   - `ANTHROPIC_API_KEY` - from console.anthropic.com. Used only for the
     news-layer step, ~10 calls/day (5 options picks + 5 stock picks), so
     cost should be a few cents/day.

2. **Connect Cloudflare Pages to this repo**: in the Cloudflare dashboard,
   Workers & Pages -> Create -> Pages -> Connect to Git -> pick this repo.
   Build settings: no build command needed, set the output directory to
   `public`. Every push to `main` (including the daily bot commit) will
   redeploy automatically.

3. **(Optional) Trigger a first run manually** from the repo's Actions tab
   -> "Daily Nasdaq-100 Screener" -> "Run workflow", rather than waiting
   for the next scheduled time, to confirm everything works end to end.

## Why the data is split across two sources

Alpaca's Market Data API provides price/volume bars but **not** valuation
fundamentals (PE ratio, market cap, dividend yield) - confirmed directly
against Alpaca's docs and community forum, not assumed. Rather than adding
a second live API just for slow-moving numbers, `data/fundamentals.json`
is a curated file (net income, debt, equity, FCF, shares outstanding,
trailing EPS, industry) that only needs updating when a company's
financials meaningfully change - roughly quarterly, not daily.

Each day's run computes the two Alpaca-can't-provide numbers locally:
```
market_cap = today's_price x shares_outstanding
pe_ratio   = today's_price / eps_ttm
```
52-week high/low is computed from Alpaca's own trailing daily bars, so no
third source is needed for that either.

**When to refresh `fundamentals.json`**: after quarterly earnings, when
net income/debt/equity/FCF move meaningfully, or when shares
outstanding changes materially (buybacks, secondary offerings, splits).

## Design decisions worth knowing (so nobody re-litigates them by accident)

- **Universe stays Nasdaq-100** for now (not the broader Russell-3000-scale
  screen discussed at one point) - mega-caps have tighter spreads and more
  reliable data, and broadening is a clean phase-2 change once this is
  running reliably, not something to bundle into the first automation pass.
- **News/context layer only, not the full multi-agent chain.** An earlier
  design explored fundamentals/price-action/news/social-sentiment analyst
  agents plus bull/bear debate and trader/risk/portfolio sign-off agents.
  Kept: the news/context layer (real, proven value - it catches cases
  where the technical score disagrees with the actual news, e.g. a stock
  flagged "bearish" on RSI that just had good earnings). Cut: social
  sentiment (no reliable free data source) and the debate/trader/risk/
  portfolio chain (redundant when nothing is actually being executed -
  there's no real risk to veto or portfolio to sign off on in a read-only,
  paper/analysis-only screener).
- **Stock picks rank within an affordable-price ceiling first**
  (`STOCK_AFFORDABLE_CEILING` in `main.py`, currently $100), not by pure
  conviction score. A live test run without this surfaced $200+ stocks as
  "top ideas" that returned 0 shares at $50-$100 budget tiers - technically
  highest-conviction, but useless for a small account. Options ideas still
  rank by pure conviction with a cost cap fallback (same as the original
  screener), since a $500-$1000 options budget is a different situation.
- **No real trading, ever.** Every idea here is analysis/paper only. The
  pipeline never calls any order-placement endpoint on any connected
  broker.

## File layout

```
scripts/
  scoring.py           shared technical+fundamental scoring engine (Alpaca data)
  options_pipeline.py  Black-Scholes modeled options ideas
  stock_pipeline.py    buy-low/sell-high plain-share ideas
  news_layer.py        Claude API context notes on top picks
  merge_bank.py         outcome tracking for both banks
  build_html.py         renders public/index.html
  main.py               daily entry point (what the workflow runs)
data/
  fundamentals.json    curated, slow-moving (update quarterly-ish)
  universe.json         the 102 symbols
  options_bank.json     grows daily (created on first run)
  stock_bank.json       grows daily (created on first run)
  screener_results.json full scan from the most recent run
public/
  index.html            the dashboard Cloudflare Pages serves
.github/workflows/
  daily_screener.yml    the cron schedule + run steps
```
