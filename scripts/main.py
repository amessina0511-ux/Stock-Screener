"""
Daily entry point. Order of operations:
  1. Fetch bars for the full universe from Alpaca
  2. Compute technicals + merge with curated fundamentals -> one shared
     `records` dict (this IS the combined options+stock scan; both
     screeners read from the same classification)
  3. Annotate options ideas (Black-Scholes) and stock ideas (buy-low plan)
  4. Pick each screener's top 5 (stock version prefers an affordable-price
     ceiling first - see stock_pipeline.select_top_stock_ideas)
  5. News/context layer on the combined ~10 picks (Claude API)
  6. Merge into both banks (outcome tracking on all previously open picks)
  7. Render public/index.html
"""
import os
import json
import scoring
import options_pipeline
import stock_pipeline
import news_layer
import merge_bank
import build_html

HERE = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(HERE, "..", "data")

STOCK_AFFORDABLE_CEILING = 100  # see requirements history: pure conviction-ranking
                                  # surfaced $200+ names that returned 0 shares at
                                  # small budget tiers in the first live test run


def main():
    universe = scoring.load_universe()
    fundamentals = scoring.load_fundamentals()
    print(f"Universe: {len(universe)} symbols, fundamentals: {len(fundamentals)} symbols")

    client = scoring.get_alpaca_client()
    all_bars = scoring.fetch_bars(universe, client=client)
    print(f"Fetched bars for {len(all_bars)}/{len(universe)} symbols")

    technicals = scoring.compute_technicals(all_bars)
    records = scoring.build_records(technicals, fundamentals)
    print(f"Scored {len(records)} symbols")

    options_pipeline.annotate_options_ideas(records)
    stock_pipeline.annotate_stock_ideas(records)

    options_top5 = options_pipeline.select_top_options_ideas(records)
    stock_top5 = stock_pipeline.select_top_stock_ideas(records, affordable_ceiling=STOCK_AFFORDABLE_CEILING)

    skip_news = os.environ.get("SKIP_NEWS_LAYER") == "1"
    if skip_news:
        print("SKIP_NEWS_LAYER=1 set, skipping Claude API news layer")
    else:
        try:
            news_layer.annotate_context_notes(options_top5)
            news_layer.annotate_context_notes(stock_top5)
        except Exception as e:
            print(f"WARNING - news layer failed, continuing without context notes: {e}")

    options_bank, stock_bank = merge_bank.run_both_banks(records, options_top5, records, stock_top5)

    with open(os.path.join(DATA_DIR, "screener_results.json"), "w") as f:
        json.dump(records, f, indent=2)

    build_html.build_dashboard(records, options_top5, stock_top5, options_bank, stock_bank)

    longs = [r for r in records.values() if r["classification"] == "Long Candidate"]
    shorts = [r for r in records.values() if r["classification"] == "Short Candidate"]
    print(f"Long: {len(longs)}  Short: {len(shorts)}  Neutral: {len(records) - len(longs) - len(shorts)}")
    print(f"Options top 5: {[p['symbol'] for p in options_top5]}")
    print(f"Stock top 5: {[p['symbol'] for p in stock_top5]}")


if __name__ == "__main__":
    main()
