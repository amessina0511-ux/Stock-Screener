"""
Builds the single self-contained HTML dashboard (public/index.html) that
Cloudflare Pages serves. Embeds all data as JSON in a <script> tag - no
backend, no API calls from the browser.
"""
import json
import os
import datetime

HERE = os.path.dirname(os.path.abspath(__file__))
PUBLIC_DIR = os.path.join(HERE, "..", "public")

TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>Nasdaq-100 Screener \u2014 Options + Stocks</title>
<style>
  :root{--bg:#0b0f14;--panel:#121820;--border:#232d3a;--text:#e7edf5;--muted:#8ea0b5;--accent:#3ecf8e;--accent2:#ff6b6b;--gold:#e8b95a;}
  *{box-sizing:border-box;}
  body{margin:0;background:var(--bg);color:var(--text);font-family:Georgia,'Iowan Old Style',serif;line-height:1.45;}
  .mono{font-family:'SF Mono','Menlo',monospace;}
  header{padding:28px 24px 18px;border-bottom:1px solid var(--border);background:linear-gradient(180deg,#0e141c,#0b0f14);}
  .wrap{max-width:1100px;margin:0 auto;padding:0 20px;}
  header h1{margin:0 0 6px;font-size:26px;}
  .sub{color:var(--muted);font-size:13px;font-family:'SF Mono',monospace;}
  .tabs{display:flex;gap:8px;margin-top:18px;}
  .tab{padding:8px 16px;border-radius:8px;border:1px solid var(--border);background:var(--panel);cursor:pointer;font-size:13px;font-family:'SF Mono',monospace;}
  .tab.active{background:var(--accent);color:#08130d;border-color:var(--accent);}
  .stats{display:flex;gap:14px;margin-top:16px;flex-wrap:wrap;}
  .stat{background:var(--panel);border:1px solid var(--border);border-radius:10px;padding:10px 16px;min-width:100px;}
  .stat .n{font-size:20px;font-weight:bold;font-family:'SF Mono',monospace;}
  .stat .l{color:var(--muted);font-size:11px;text-transform:uppercase;}
  section{max-width:1100px;margin:0 auto;padding:24px 20px;}
  section.hidden{display:none;}
  h2{font-size:18px;border-bottom:1px solid var(--border);padding-bottom:8px;margin-bottom:14px;}
  .hint{color:var(--muted);font-size:13px;margin:-4px 0 16px;font-family:'SF Mono',monospace;}
  .cards{display:grid;grid-template-columns:repeat(auto-fill,minmax(240px,1fr));gap:14px;}
  .card{background:var(--panel);border:1px solid var(--border);border-radius:12px;padding:16px;position:relative;}
  .card::before{content:"";position:absolute;left:0;top:0;bottom:0;width:4px;background:var(--accent);}
  .card.short::before{background:var(--accent2);}
  .card .sym{font-size:19px;font-weight:bold;font-family:'SF Mono',monospace;}
  .card .ind{color:var(--muted);font-size:11px;margin-top:2px;min-height:26px;}
  .card .score{float:right;font-family:'SF Mono',monospace;font-size:13px;color:var(--accent);}
  .card .row{margin-top:10px;font-family:'SF Mono',monospace;font-size:12.5px;display:flex;justify-content:space-between;}
  .card .row .lbl{color:var(--muted);}
  .card .note{margin-top:10px;font-size:12px;color:#c3d0de;border-top:1px solid var(--border);padding-top:8px;}
  .card .reasons{margin-top:8px;font-size:12px;color:#c3d0de;padding-left:16px;}
  table{width:100%;border-collapse:collapse;font-size:13px;}
  th{text-align:left;padding:8px 10px;color:var(--muted);border-bottom:1px solid var(--border);font-family:'SF Mono',monospace;font-size:11px;text-transform:uppercase;position:sticky;top:0;background:var(--bg);}
  td{padding:8px 10px;border-bottom:1px solid #182130;font-family:'SF Mono',monospace;}
  .pos{color:var(--accent);} .neg{color:var(--accent2);}
  .table-wrap{overflow-x:auto;border:1px solid var(--border);border-radius:10px;}
  footer{color:var(--muted);font-size:12px;text-align:center;padding:26px 20px 46px;font-family:'SF Mono',monospace;}
</style>
</head>
<body>
<header>
  <div class="wrap">
    <h1>Nasdaq-100 Screener</h1>
    <div class="sub" id="stamp"></div>
    <div class="stats" id="stats"></div>
    <div class="tabs">
      <div class="tab active" data-tab="options">Options Ideas</div>
      <div class="tab" data-tab="stocks">Stock Ideas (buy-low/sell-high)</div>
      <div class="tab" data-tab="bank">Track Record</div>
    </div>
  </div>
</header>

<section id="tab-options">
  <h2>Today's Top 5 Options Ideas</h2>
  <div class="hint">Modeled pricing (Black-Scholes off historical volatility) - not live quotes. See README.</div>
  <div class="cards" id="opt-top5"></div>
</section>

<section id="tab-stocks" class="hidden">
  <h2>Today's Top 5 Stock Ideas</h2>
  <div class="hint">Ranked within an affordable-price ceiling first, so small budgets get actionable picks.</div>
  <div class="cards" id="stk-top5"></div>
</section>

<section id="tab-bank" class="hidden">
  <h2>Options Track Record</h2>
  <div class="table-wrap"><table id="opt-bank-table"><thead><tr>
    <th>Date</th><th>Symbol</th><th>Dir</th><th>Entry</th><th>Target</th><th>Outcome</th>
  </tr></thead><tbody></tbody></table></div>
  <h2 style="margin-top:26px">Stock Track Record</h2>
  <div class="table-wrap"><table id="stk-bank-table"><thead><tr>
    <th>Date</th><th>Symbol</th><th>Entry</th><th>Stop</th><th>Target 1</th><th>Outcome</th>
  </tr></thead><tbody></tbody></table></div>
</section>

<footer>Rules-based technical/fundamental screen. Not investment advice. Data: Alpaca Market Data API.</footer>

<script>
const DATA = __DATA__;
document.getElementById('stamp').textContent = 'Generated ' + new Date().toString();

function fmt(n){ return n===null||n===undefined?'\u2014':(typeof n==='number'?n.toLocaleString(undefined,{maximumFractionDigits:2}):n); }
function money(n){ return n===null||n===undefined?'\u2014':'$'+fmt(n); }

const optResolved = DATA.options_bank.flatMap(e=>e.picks).filter(p=>p.resolved);
const optWins = optResolved.filter(p=>['target_hit','expired_profitable'].includes(p.outcome));
const stkResolved = DATA.stock_bank.flatMap(e=>e.picks).filter(p=>p.resolved);
const stkWins = stkResolved.filter(p=>p.outcome==='target_hit');

document.getElementById('stats').innerHTML = `
  <div class="stat"><div class="n">${DATA.total_symbols}</div><div class="l">Scanned</div></div>
  <div class="stat"><div class="n">${DATA.long_count}</div><div class="l">Long</div></div>
  <div class="stat"><div class="n">${DATA.short_count}</div><div class="l">Short/Caution</div></div>
  <div class="stat"><div class="n">${optResolved.length? Math.round(100*optWins.length/optResolved.length)+'%':'\u2014'}</div><div class="l">Options Win Rate</div></div>
  <div class="stat"><div class="n">${stkResolved.length? Math.round(100*stkWins.length/stkResolved.length)+'%':'\u2014'}</div><div class="l">Stock Win Rate</div></div>
`;

document.getElementById('opt-top5').innerHTML = DATA.options_top5.map(p => `<div class="card ${p.classification==='Short Candidate'?'short':''}">
  <div class="score">${p.net_score>0?'+':''}${fmt(p.net_score)}</div>
  <div class="sym">${p.symbol}</div>
  <div class="ind">${p.industry||''}</div>
  <div class="row"><span class="lbl">${p.option_type.toUpperCase()} strike</span><span>${money(p.strike)}</span></div>
  <div class="row"><span class="lbl">Premium (est.)</span><span>${money(p.premium)}/sh \u00b7 ${money(p.cost_per_contract)}/contract</span></div>
  <div class="row"><span class="lbl">Breakeven</span><span>${money(p.breakeven_price)}</span></div>
  <div class="row"><span class="lbl">Target (${p.dte_days}d)</span><span class="pos">${money(p.target_price)}</span></div>
  <ul class="reasons">${(p.top_reasons||[]).map(r=>`<li>${r}</li>`).join('')}</ul>
  ${p.context_note ? `<div class="note">${p.context_note}</div>` : ''}
</div>`).join('');

document.getElementById('stk-top5').innerHTML = DATA.stock_top5.map(p => `<div class="card">
  <div class="score">+${fmt(p.net_score)}</div>
  <div class="sym">${p.symbol}</div>
  <div class="ind">${p.industry||''}</div>
  <div class="row"><span class="lbl">Entry</span><span>${money(p.entry_price)}</span></div>
  <div class="row"><span class="lbl">Stop (-${fmt(p.pct_risk)}%)</span><span class="neg">${money(p.stop_price)}</span></div>
  <div class="row"><span class="lbl">Target 1 (+${fmt(p.pct_gain_target1)}%)</span><span class="pos">${money(p.target1_price)}</span></div>
  <div class="row"><span class="lbl">$500 budget</span><span>${p.budget_tiers['$500'].shares} sh</span></div>
  <div class="row"><span class="lbl">$1000 budget</span><span>${p.budget_tiers['$1000'].shares} sh</span></div>
  <ul class="reasons">${(p.top_reasons||[]).map(r=>`<li>${r}</li>`).join('')}</ul>
  ${p.context_note ? `<div class="note">${p.context_note}</div>` : ''}
</div>`).join('');

const optBody = document.querySelector('#opt-bank-table tbody');
optBody.innerHTML = DATA.options_bank.flatMap(e=>e.picks.map(p=>({...p,date:e.date})))
  .sort((a,b)=>b.date.localeCompare(a.date)).slice(0,100)
  .map(p=>`<tr><td>${p.date}</td><td>${p.symbol}</td><td>${p.classification==='Long Candidate'?'Call':'Put'}</td>
    <td>${money(p.price)}</td><td>${money(p.target_price)}</td>
    <td class="${['target_hit','expired_profitable'].includes(p.outcome)?'pos':(p.resolved?'neg':'')}">${p.outcome}</td></tr>`).join('');

const stkBody = document.querySelector('#stk-bank-table tbody');
stkBody.innerHTML = DATA.stock_bank.flatMap(e=>e.picks.map(p=>({...p,date:e.date})))
  .sort((a,b)=>b.date.localeCompare(a.date)).slice(0,100)
  .map(p=>`<tr><td>${p.date}</td><td>${p.symbol}</td><td>${money(p.entry_price)}</td>
    <td>${money(p.stop_price)}</td><td>${money(p.target1_price)}</td>
    <td class="${p.outcome==='target_hit'?'pos':(p.resolved?'neg':'')}">${p.outcome}</td></tr>`).join('');

document.querySelectorAll('.tab').forEach(tab=>{
  tab.addEventListener('click', ()=>{
    document.querySelectorAll('.tab').forEach(t=>t.classList.remove('active'));
    tab.classList.add('active');
    document.querySelectorAll('section[id^="tab-"]').forEach(s=>s.classList.add('hidden'));
    document.getElementById('tab-'+tab.dataset.tab).classList.remove('hidden');
  });
});
</script>
</body>
</html>
"""


def build_dashboard(records, options_top5, stock_top5, options_bank, stock_bank):
    longs = [r for r in records.values() if r["classification"] == "Long Candidate"]
    shorts = [r for r in records.values() if r["classification"] == "Short Candidate"]
    data = {
        "total_symbols": len(records),
        "long_count": len(longs),
        "short_count": len(shorts),
        "options_top5": options_top5,
        "stock_top5": stock_top5,
        "options_bank": options_bank,
        "stock_bank": stock_bank,
    }
    html = TEMPLATE.replace("__DATA__", json.dumps(data))
    os.makedirs(PUBLIC_DIR, exist_ok=True)
    out_path = os.path.join(PUBLIC_DIR, "index.html")
    with open(out_path, "w") as f:
        f.write(html)
    print(f"Wrote dashboard to {out_path} ({len(html):,} bytes)")
    return out_path
