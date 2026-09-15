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
<title>Nasdaq-100 Screener — Options + Stocks</title>
<style>
  :root{--bg:#0b0f14;--panel:#121820;--border:#232d3a;--text:#e7edf5;--muted:#8ea0b5;--accent:#3ecf8e;--accent2:#ff6b6b;--gold:#e8b95a;}
  *{box-sizing:border-box;}
  body{margin:0;background:var(--bg);color:var(--text);font-family:Georgia,'Iowan Old Style',serif;line-height:1.45;}
  .mono{font-family:'SF Mono','Menlo',monospace;}
  header{padding:28px 24px 18px;border-bottom:1px solid var(--border);background:linear-gradient(180deg,#0e141c,#0b0f14);}
  .wrap{max-width:1200px;margin:0 auto;padding:0 20px;}
  header h1{margin:0 0 6px;font-size:26px;}
  .sub{color:var(--muted);font-size:13px;font-family:'SF Mono',monospace;}
  .tabs{display:flex;gap:8px;margin-top:18px;flex-wrap:wrap;}
  .tab{padding:8px 16px;border-radius:8px;border:1px solid var(--border);background:var(--panel);cursor:pointer;font-size:13px;font-family:'SF Mono',monospace;}
  .tab.active{background:var(--accent);color:#08130d;border-color:var(--accent);}
  .stats{display:flex;gap:14px;margin-top:16px;flex-wrap:wrap;}
  .stat{background:var(--panel);border:1px solid var(--border);border-radius:10px;padding:10px 16px;min-width:100px;}
  .stat .n{font-size:20px;font-weight:bold;font-family:'SF Mono',monospace;}
  .stat .l{color:var(--muted);font-size:11px;text-transform:uppercase;}
  section{max-width:1200px;margin:0 auto;padding:24px 20px;}
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
  .table-wrap{overflow-x:auto;border:1px solid var(--border);border-radius:10px;max-height:70vh;overflow-y:auto;}
  footer{color:var(--muted);font-size:12px;text-align:center;padding:26px 20px 46px;font-family:'SF Mono',monospace;}

  .screener-controls{display:flex;gap:10px;flex-wrap:wrap;align-items:center;margin-bottom:14px;}
  #screener-search{flex:1;min-width:180px;background:var(--panel);border:1px solid var(--border);border-radius:8px;padding:9px 12px;color:var(--text);font-family:'SF Mono',monospace;font-size:13px;}
  #screener-search:focus{outline:1px solid var(--accent);}
  .filter-btns{display:flex;gap:6px;}
  .filter-btn{padding:8px 12px;border-radius:8px;border:1px solid var(--border);background:var(--panel);color:var(--muted);cursor:pointer;font-size:12px;font-family:'SF Mono',monospace;}
  .filter-btn.active{background:var(--accent);color:#08130d;border-color:var(--accent);}
  #screener-table th{cursor:pointer;user-select:none;white-space:nowrap;}
  #screener-table th .arrow{color:var(--accent);margin-left:3px;}
  #screener-table tbody tr.sym-row{cursor:pointer;}
  #screener-table tbody tr.sym-row:hover{background:#141c27;}
  #screener-table tbody tr.sym-row.expanded{background:#141c27;}
  .class-long{color:var(--accent);}
  .class-short{color:var(--accent2);}
  .class-neutral{color:var(--muted);}
  .detail-row td{padding:0;border-bottom:1px solid #182130;}
  .detail-panel{padding:16px 18px;background:#0e141c;border-left:3px solid var(--accent);}
  .detail-panel.short{border-left-color:var(--accent2);}
  .detail-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(220px,1fr));gap:18px;}
  .detail-block h4{margin:0 0 8px;font-size:12px;text-transform:uppercase;letter-spacing:0.03em;color:var(--muted);font-family:'SF Mono',monospace;}
  .kv{display:flex;justify-content:space-between;font-family:'SF Mono',monospace;font-size:12.5px;padding:3px 0;border-bottom:1px dashed #1c2634;}
  .kv .lbl{color:var(--muted);}
  .detail-reasons{font-size:12.5px;padding-left:16px;margin:4px 0;}
  .detail-reasons.bull li{color:var(--accent);}
  .detail-reasons.bear li{color:var(--accent2);}
  .no-idea{color:var(--muted);font-size:12.5px;font-style:italic;}
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
      <div class="tab" data-tab="screener">Full Screener</div>
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

<section id="tab-screener" class="hidden">
  <h2>Full Screener — All Scanned Symbols</h2>
  <div class="hint">Click a row for technicals, fundamentals, bull/bear reasons, and its computed trade idea (if any). Click a column header to sort.</div>
  <div class="screener-controls">
    <input type="text" id="screener-search" placeholder="Search symbol or industry...">
    <div class="filter-btns" id="screener-filters">
      <div class="filter-btn active" data-filter="all">All</div>
      <div class="filter-btn" data-filter="Long Candidate">Long</div>
      <div class="filter-btn" data-filter="Short Candidate">Short</div>
      <div class="filter-btn" data-filter="Neutral">Neutral</div>
    </div>
  </div>
  <div class="table-wrap">
    <table id="screener-table">
      <thead><tr>
        <th data-key="symbol">Symbol</th>
        <th data-key="price">Price</th>
        <th data-key="classification">Class</th>
        <th data-key="net_score">Score</th>
        <th data-key="rsi14">RSI</th>
        <th data-key="pe_ratio">PE</th>
        <th data-key="trend">Trend</th>
        <th data-key="industry">Industry</th>
      </tr></thead>
      <tbody id="screener-tbody"></tbody>
    </table>
  </div>
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

function fmt(n){ return n===null||n===undefined?'—':(typeof n==='number'?n.toLocaleString(undefined,{maximumFractionDigits:2}):n); }
function money(n){ return n===null||n===undefined?'—':'$'+fmt(n); }
function pct(n){ return n===null||n===undefined?'—':fmt(n)+'%'; }

const optResolved = DATA.options_bank.flatMap(e=>e.picks).filter(p=>p.resolved);
const optWins = optResolved.filter(p=>['target_hit','expired_profitable'].includes(p.outcome));
const stkResolved = DATA.stock_bank.flatMap(e=>e.picks).filter(p=>p.resolved);
const stkWins = stkResolved.filter(p=>p.outcome==='target_hit');

document.getElementById('stats').innerHTML = `
  <div class="stat"><div class="n">${DATA.total_symbols}</div><div class="l">Scanned</div></div>
  <div class="stat"><div class="n">${DATA.long_count}</div><div class="l">Long</div></div>
  <div class="stat"><div class="n">${DATA.short_count}</div><div class="l">Short/Caution</div></div>
  <div class="stat"><div class="n">${optResolved.length? Math.round(100*optWins.length/optResolved.length)+'%':'—'}</div><div class="l">Options Win Rate</div></div>
  <div class="stat"><div class="n">${stkResolved.length? Math.round(100*stkWins.length/stkResolved.length)+'%':'—'}</div><div class="l">Stock Win Rate</div></div>
`;

document.getElementById('opt-top5').innerHTML = DATA.options_top5.map(p => `<div class="card ${p.classification==='Short Candidate'?'short':''}">
  <div class="score">${p.net_score>0?'+':''}${fmt(p.net_score)}</div>
  <div class="sym">${p.symbol}</div>
  <div class="ind">${p.industry||''}</div>
  <div class="row"><span class="lbl">${p.option_type.toUpperCase()} strike</span><span>${money(p.strike)}</span></div>
  <div class="row"><span class="lbl">Premium (est.)</span><span>${money(p.premium)}/sh · ${money(p.cost_per_contract)}/contract</span></div>
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

/* ---------- Full Screener tab ---------- */
const allSymbols = Object.values(DATA.all_symbols);
let screenerSort = { key: 'net_score', dir: -1 };
let screenerFilter = 'all';
let screenerSearch = '';
let expandedSymbol = null;

function classClass(c){
  if (c === 'Long Candidate') return 'class-long';
  if (c === 'Short Candidate') return 'class-short';
  return 'class-neutral';
}

function detailPanelHtml(r){
  const idea = r.trade_idea;
  const stockIdea = r.stock_idea;
  let ideaHtml = '<div class="no-idea">No trade idea computed (Neutral classification).</div>';
  if (idea) {
    ideaHtml = `
      <div class="kv"><span class="lbl">${idea.option_type.toUpperCase()} strike</span><span>${money(idea.strike)}</span></div>
      <div class="kv"><span class="lbl">Expiration</span><span>${idea.expiration} (${idea.dte_days}d)</span></div>
      <div class="kv"><span class="lbl">Premium (est.)</span><span>${money(idea.premium)}/sh · ${money(idea.cost_per_contract)}/contract</span></div>
      <div class="kv"><span class="lbl">Breakeven</span><span>${money(idea.breakeven_price)} (${pct(idea.pct_move_to_breakeven)} move)</span></div>
      <div class="kv"><span class="lbl">Target price</span><span>${money(idea.target_price)} (${pct(idea.pct_move_to_target)} move)</span></div>
      <div class="kv"><span class="lbl">Max loss/contract</span><span>${money(idea.max_loss_per_contract)}</span></div>
      <div class="kv"><span class="lbl">Est. reward/contract</span><span>${money(idea.est_reward_per_contract_at_target)}</span></div>
    `;
  } else if (stockIdea) {
    ideaHtml = `
      <div class="kv"><span class="lbl">Entry</span><span>${money(stockIdea.entry_price)}</span></div>
      <div class="kv"><span class="lbl">Stop (-${pct(stockIdea.pct_risk)})</span><span>${money(stockIdea.stop_price)}</span></div>
      <div class="kv"><span class="lbl">Target 1 (+${pct(stockIdea.pct_gain_target1)})</span><span>${money(stockIdea.target1_price)}</span></div>
      <div class="kv"><span class="lbl">Target 2 (+${pct(stockIdea.pct_gain_target2)})</span><span>${money(stockIdea.target2_price)}</span></div>
      <div class="kv"><span class="lbl">$500 budget</span><span>${stockIdea.budget_tiers['$500'].shares} sh</span></div>
      <div class="kv"><span class="lbl">$1000 budget</span><span>${stockIdea.budget_tiers['$1000'].shares} sh</span></div>
    `;
  }

  return `<div class="detail-panel ${r.classification==='Short Candidate'?'short':''}">
    <div class="detail-grid">
      <div class="detail-block">
        <h4>Technicals</h4>
        <div class="kv"><span class="lbl">RSI (14)</span><span>${fmt(r.rsi14)}</span></div>
        <div class="kv"><span class="lbl">Trend</span><span>${r.trend||'—'}</span></div>
        <div class="kv"><span class="lbl">SMA 20 / 50 / 200</span><span>${money(r.sma20)} / ${money(r.sma50)} / ${money(r.sma200)}</span></div>
        <div class="kv"><span class="lbl">Bollinger low/mid/high</span><span>${money(r.bb_lower)} / ${money(r.bb_mid)} / ${money(r.bb_upper)}</span></div>
        <div class="kv"><span class="lbl">%B</span><span>${r.pct_b!=null?fmt(r.pct_b):'—'}</span></div>
        <div class="kv"><span class="lbl">20d chg / 5d chg</span><span>${pct(r.chg_20d_pct)} / ${pct(r.chg_5d_pct)}</span></div>
        <div class="kv"><span class="lbl">Rel. volume</span><span>${r.rel_volume!=null?fmt(r.rel_volume)+'x':'—'}</span></div>
        <div class="kv"><span class="lbl">52wk range</span><span>${money(r.fifty_two_wk_low)} – ${money(r.fifty_two_wk_high)}</span></div>
        <div class="kv"><span class="lbl">Historical vol (ann.)</span><span>${r.hv_annual!=null?pct(r.hv_annual*100):'—'}</span></div>
      </div>
      <div class="detail-block">
        <h4>Fundamentals</h4>
        <div class="kv"><span class="lbl">Industry</span><span>${r.industry||'—'}</span></div>
        <div class="kv"><span class="lbl">Fiscal year</span><span>${r.fy||'—'}</span></div>
        <div class="kv"><span class="lbl">Market cap</span><span>${money(r.market_cap)}</span></div>
        <div class="kv"><span class="lbl">PE ratio</span><span>${r.pe_ratio!=null?fmt(r.pe_ratio):'n/m'}</span></div>
        <div class="kv"><span class="lbl">Debt / equity</span><span>${r.debt_to_equity!=null?fmt(r.debt_to_equity):'—'}</span></div>
        <div class="kv"><span class="lbl">FCF yield</span><span>${pct(r.fcf_yield_pct)}</span></div>
        <div class="kv"><span class="lbl">Net income</span><span>${money(r.net_income)}</span></div>
        <div class="kv"><span class="lbl">Free cash flow</span><span>${money(r.fcf)}</span></div>
        <div class="kv"><span class="lbl">Profitable</span><span>${r.profitable?'Yes':'No'}</span></div>
      </div>
      <div class="detail-block">
        <h4>Bull / Bear reasons</h4>
        ${(r.bull_reasons&&r.bull_reasons.length) ? `<ul class="detail-reasons bull">${r.bull_reasons.map(x=>`<li>${x}</li>`).join('')}</ul>` : ''}
        ${(r.bear_reasons&&r.bear_reasons.length) ? `<ul class="detail-reasons bear">${r.bear_reasons.map(x=>`<li>${x}</li>`).join('')}</ul>` : ''}
        ${(!r.bull_reasons||!r.bull_reasons.length) && (!r.bear_reasons||!r.bear_reasons.length) ? '<div class="no-idea">No notable signals.</div>' : ''}
      </div>
      <div class="detail-block">
        <h4>${idea ? 'Options trade idea' : (stockIdea ? 'Stock trade idea' : 'Trade idea')}</h4>
        ${ideaHtml}
      </div>
    </div>
  </div>`;
}

function renderScreenerTable(){
  let rows = allSymbols.slice();
  if (screenerFilter !== 'all') rows = rows.filter(r => r.classification === screenerFilter);
  if (screenerSearch) {
    const q = screenerSearch.toLowerCase();
    rows = rows.filter(r => r.symbol.toLowerCase().includes(q) || (r.industry||'').toLowerCase().includes(q));
  }
  rows.sort((a,b)=>{
    let av = a[screenerSort.key], bv = b[screenerSort.key];
    if (av === null || av === undefined) av = (typeof bv === 'string') ? '' : -Infinity;
    if (bv === null || bv === undefined) bv = (typeof av === 'string') ? '' : -Infinity;
    if (typeof av === 'string' || typeof bv === 'string') return screenerSort.dir * String(av).localeCompare(String(bv));
    return screenerSort.dir * (av - bv);
  });

  document.querySelectorAll('#screener-table th[data-key]').forEach(th=>{
    th.innerHTML = th.textContent.replace(/\s*[↑↓]$/, '');
    if (th.dataset.key === screenerSort.key) {
      th.innerHTML += `<span class="arrow">${screenerSort.dir === 1 ? '↑' : '↓'}</span>`;
    }
  });

  const tbody = document.getElementById('screener-tbody');
  tbody.innerHTML = rows.map(r => {
    const isExpanded = r.symbol === expandedSymbol;
    let html = `<tr class="sym-row${isExpanded?' expanded':''}" data-symbol="${r.symbol}">
      <td>${r.symbol}</td>
      <td>${money(r.price)}</td>
      <td class="${classClass(r.classification)}">${r.classification}</td>
      <td class="${r.net_score>0?'pos':(r.net_score<0?'neg':'')}">${r.net_score>0?'+':''}${fmt(r.net_score)}</td>
      <td>${fmt(r.rsi14)}</td>
      <td>${r.pe_ratio!=null?fmt(r.pe_ratio):'n/m'}</td>
      <td>${r.trend||'—'}</td>
      <td>${r.industry||'—'}</td>
    </tr>`;
    if (isExpanded) {
      html += `<tr class="detail-row"><td colspan="8">${detailPanelHtml(r)}</td></tr>`;
    }
    return html;
  }).join('');

  tbody.querySelectorAll('tr.sym-row').forEach(tr=>{
    tr.addEventListener('click', ()=>{
      const sym = tr.dataset.symbol;
      expandedSymbol = (expandedSymbol === sym) ? null : sym;
      renderScreenerTable();
    });
  });
}

document.querySelectorAll('#screener-table th[data-key]').forEach(th=>{
  th.addEventListener('click', ()=>{
    const key = th.dataset.key;
    if (screenerSort.key === key) {
      screenerSort.dir *= -1;
    } else {
      screenerSort.key = key;
      screenerSort.dir = (key === 'symbol' || key === 'classification' || key === 'trend' || key === 'industry') ? 1 : -1;
    }
    renderScreenerTable();
  });
});

document.querySelectorAll('.filter-btn').forEach(btn=>{
  btn.addEventListener('click', ()=>{
    document.querySelectorAll('.filter-btn').forEach(b=>b.classList.remove('active'));
    btn.classList.add('active');
    screenerFilter = btn.dataset.filter;
    renderScreenerTable();
  });
});

document.getElementById('screener-search').addEventListener('input', (e)=>{
  screenerSearch = e.target.value;
  renderScreenerTable();
});

renderScreenerTable();
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
        "all_symbols": records,
    }
    html = TEMPLATE.replace("__DATA__", json.dumps(data))
    os.makedirs(PUBLIC_DIR, exist_ok=True)
    out_path = os.path.join(PUBLIC_DIR, "index.html")
    with open(out_path, "w") as f:
        f.write(html)
    print(f"Wrote dashboard to {out_path} ({len(html):,} bytes)")
    return out_path
