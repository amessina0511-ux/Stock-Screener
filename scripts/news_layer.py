"""
Adds a short news/context note to each of today's top picks, using the
Claude API with web search enabled. This is the one piece kept from the
proposed multi-agent redesign (see project conversation history) - applied
only to a handful of picks per day, not the whole universe, to keep cost
and runtime bounded (roughly 5-10 calls/day, not hundreds).
"""
import os
import json

MODEL = "claude-sonnet-4-6"


def get_client():
    import anthropic  # lazy import - see scoring.get_alpaca_client() for why
    return anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])


PROMPT_TEMPLATE = """You are a markets research assistant. A rules-based technical/fundamental \
screener flagged {symbol} ({industry}) as a {direction} candidate today, mainly because: {reasons}.

Current price: ${price}.

Search for recent news (last 1-2 weeks) on {symbol} and write a 2-3 sentence context note that:
1. States whether the recent news/fundamental picture agrees or disagrees with the technical \
signal above (e.g. a stock flagged "bearish" on RSI/Bollinger might actually have good underlying \
news - flag that tension explicitly if it exists).
2. Mentions the single most relevant concrete fact you found (an earnings result, analyst move, \
product/regulatory news, etc.), not generic commentary.
3. Stays neutral and factual - no buy/sell advice, just context.

Respond with ONLY the note text, no preamble, no markdown formatting."""


def get_context_note(pick, client=None):
    client = client or get_client()
    direction = pick.get("classification") or ("Long" if pick.get("option_type") == "call" or "target1_price" in pick else "Short")
    reasons = "; ".join(pick.get("top_reasons", []))
    prompt = PROMPT_TEMPLATE.format(
        symbol=pick["symbol"], industry=pick.get("industry", "unknown industry"),
        direction=direction, reasons=reasons or "no specific reasons logged",
        price=pick.get("price") or pick.get("entry_price"),
    )
    try:
        response = client.messages.create(
            model=MODEL,
            max_tokens=300,
            tools=[{"type": "web_search_20250305", "name": "web_search"}],
            messages=[{"role": "user", "content": prompt}],
        )
        text_blocks = [b.text for b in response.content if b.type == "text"]
        return " ".join(text_blocks).strip() or None
    except Exception as e:
        return f"[context note unavailable: {e}]"


def annotate_context_notes(picks):
    """Mutates picks in place, filling in context_note for each. Call this
    on the combined top-5-options + top-5-stock lists (~10 calls total)."""
    client = get_client()
    for pick in picks:
        pick["context_note"] = get_context_note(pick, client=client)
    return picks
