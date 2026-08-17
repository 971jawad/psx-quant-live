"""Render a public dashboard for the (private) psx-quant project from its DATA
files only — the live scoreboard + the edge report. It reads, never writes,
psx-quant, so that repo stays untouched. Daily, CI clones psx-quant read-only
and re-runs this.

Usage: python build_dashboard.py <path-to-psx-quant>   (default: ../psx-quant)
Output: docs/index.html
"""
import re
import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
SRC = Path(sys.argv[1]) if len(sys.argv) > 1 else HERE.parent / "psx-quant"


def scoreboard_summary(sb: pd.DataFrame):
    done = sb[sb.resolved.astype(str).str.lower().isin(["true", "1"])].copy()
    done["net_ret"] = pd.to_numeric(done["net_ret"], errors="coerce")
    done = done.dropna(subset=["net_ret"])
    rows = []
    for (h, v), g in done.groupby(["horizon", "variant"]):
        rows.append({"horizon": h, "variant": v, "n": len(g),
                     "avg_net": g.net_ret.mean(), "win_rate": (g.net_ret > 0).mean(),
                     "cum": (1 + g.net_ret).prod() - 1})
    return pd.DataFrame(rows), len(sb) - len(done)


def open_picks(sb: pd.DataFrame):
    op = sb[~sb.resolved.astype(str).str.lower().isin(["true", "1"])].copy()
    return op.sort_values(["pred_date", "horizon"], ascending=[False, True])


def resolved_picks(sb: pd.DataFrame):
    dn = sb[sb.resolved.astype(str).str.lower().isin(["true", "1"])].copy()
    dn["net_ret"] = pd.to_numeric(dn["net_ret"], errors="coerce")
    return dn.dropna(subset=["net_ret"]).sort_values(["pred_date", "horizon"], ascending=[False, True])


def edge_highlights(md: str):
    # pull the first ~2 paragraphs + the honest bottom line
    m = re.search(r"## Honest bottom line\s*(.+)$", md, re.S)
    bottom = (m.group(1).strip()[:700] if m else "")
    return bottom


def build():
    sb = pd.read_csv(SRC / "predictions" / "scoreboard.csv")
    summ, n_open = scoreboard_summary(sb)
    op = open_picks(sb)
    res = resolved_picks(sb)
    edge_md = (SRC / "reports" / "REPORT_EDGE.md").read_text(encoding="utf-8") \
        if (SRC / "reports" / "REPORT_EDGE.md").exists() else ""
    bottom = edge_highlights(edge_md)
    as_of = sb.pred_date.max()

    def srow(r):
        c = "up" if r.avg_net > 0 else "down"
        return (f"<tr><td>{r.horizon}</td><td>{r.variant}</td><td class=num>{r.n}</td>"
                f"<td class='num {c}'>{r.avg_net*100:+.2f}%</td>"
                f"<td class=num>{r.win_rate*100:.0f}%</td>"
                f"<td class='num {'up' if r.cum>0 else 'down'}'>{r.cum*100:+.1f}%</td></tr>")
    srows = "".join(srow(r) for _, r in summ.iterrows()) or "<tr><td colspan=6 class=muted>no resolved picks yet</td></tr>"
    orows = "".join(f"<tr><td class=mono>{r.pred_date}</td><td>{r.horizon}</td><td>{r.variant}</td>"
                    f"<td><b>{r.symbol}</b></td><td class=num>{r.entry_close}</td></tr>"
                    for _, r in op.iterrows()) or "<tr><td colspan=5 class=muted>none open</td></tr>"

    def rrow(r):
        c = "up" if r.net_ret > 0 else "down"
        return (f"<tr><td class=mono>{r.pred_date}</td><td>{r.horizon}</td><td>{r.variant}</td>"
                f"<td><b>{r.symbol}</b></td><td class=num>{r.entry_close}</td>"
                f"<td class=mono>{'' if pd.isna(r.exit_date) else str(r.exit_date)}</td>"
                f"<td class='num {c}'>{r.net_ret*100:+.2f}%</td></tr>")
    rrows = "".join(rrow(r) for _, r in res.iterrows()) or "<tr><td colspan=7 class=muted>no resolved picks yet</td></tr>"

    html = (TEMPLATE.replace("__ASOF__", str(as_of)).replace("__SROWS__", srows)
            .replace("__OROWS__", orows).replace("__RROWS__", rrows)
            .replace("__NOPEN__", str(n_open)).replace("__NRES__", str(len(res)))
            .replace("__BOTTOM__", bottom.replace("\n", " ")))
    out = HERE / "docs" / "index.html"
    out.parent.mkdir(exist_ok=True)
    out.write_text(html, encoding="utf-8")
    print(f"wrote {out} (as of {as_of}, {n_open} open, {len(res)} resolved picks shown)")


TEMPLATE = """<meta charset="utf-8">
<title>PSX Quant Live</title>
<meta name="viewport" content="width=device-width, initial-scale=1">
<style>
:root{--bg:#f6f7f9;--panel:#fff;--bd:#dde3ea;--ink:#0f1720;--mut:#5b6876;--acc:#c8791a;--up:#1a7f37;--down:#c9302c;
--mono:"Cascadia Code","SF Mono",Consolas,ui-monospace,monospace;--sans:"Segoe UI",system-ui,sans-serif;}
@media(prefers-color-scheme:dark){:root{--bg:#0a0e14;--panel:#111823;--bd:#1f2a37;--ink:#e6edf3;--mut:#8b97a6;--acc:#f5a623;--up:#3fb950;--down:#f85149;}}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--ink);font-family:var(--sans);font-size:15px;line-height:1.55}
.wrap{max-width:860px;margin:0 auto;padding:28px 18px 70px}
h1{font-family:var(--mono);letter-spacing:.02em;margin:0 0 4px}h1 b{color:var(--acc)}
.sub{color:var(--mut);margin-bottom:22px}
.card{background:var(--panel);border:1px solid var(--bd);border-radius:12px;padding:18px 20px;margin-bottom:16px}
h2{font-size:14px;font-family:var(--mono);text-transform:uppercase;letter-spacing:.05em;color:var(--mut);margin:0 0 12px}
table{width:100%;border-collapse:collapse;font-size:14px}th,td{text-align:right;padding:6px 9px;border-bottom:1px solid var(--bd);white-space:nowrap}
th{font-family:var(--mono);font-size:11px;text-transform:uppercase;color:var(--mut)}th:first-child,td:first-child{text-align:left}
.num{font-family:var(--mono);font-variant-numeric:tabular-nums}.mono{font-family:var(--mono)}.up{color:var(--up)}.down{color:var(--down)}.muted{color:var(--mut)}
.note{font-size:13px;color:var(--mut);border-left:2px solid var(--acc);padding-left:11px;margin-top:14px}
.scroll{max-height:440px;overflow:auto;border:1px solid var(--bd);border-radius:8px}
.scroll th{position:sticky;top:0;background:var(--panel)}
.chip{display:inline-block;font-family:var(--mono);font-size:12px;border:1px solid var(--bd);border-radius:999px;padding:3px 10px;color:var(--mut)}
a{color:var(--acc)}
</style>
<div class="wrap">
<h1>PSX<b>·</b>QUANT LIVE</h1>
<div class="sub">Honest live scoreboard for the PSX quant research project · data through <span class="mono">__ASOF__</span> · <span class="chip">__NOPEN__ open picks</span></div>
<div class="card">
<h2>Live scoreboard — v1 (primary) vs v2 (meta-filtered), resolved picks</h2>
<table><thead><tr><th>Horizon</th><th>Variant</th><th>n</th><th>Avg net/trade</th><th>Win rate</th><th>Cumulative</th></tr></thead>
<tbody>__SROWS__</tbody></table>
<div class="note">Every pick is logged before the outcome is known and scored on genuinely out-of-sample data. Net of round-trip cost. This is the honest live record — nothing here is validated alpha; the scoreboard exists to measure it before any money is risked.</div>
</div>
<div class="card">
<h2>Live / open picks (__NOPEN__) — tickers &amp; entry, awaiting outcome</h2>
<div class="scroll"><table><thead><tr><th>Pred date</th><th>Horizon</th><th>Var</th><th>Ticker</th><th>Entry</th></tr></thead>
<tbody>__OROWS__</tbody></table></div>
</div>
<div class="card">
<h2>Resolved picks (__NRES__) — entry, exit &amp; net outcome</h2>
<div class="scroll"><table><thead><tr><th>Pred date</th><th>Horizon</th><th>Var</th><th>Ticker</th><th>Entry</th><th>Exit date</th><th>Net</th></tr></thead>
<tbody>__RROWS__</tbody></table></div>
<div class="note">Every pick logged before its outcome was known, scored net of round-trip cost. Full history of tickers &amp; entry prices — not just aggregates.</div>
</div>
<div class="card">
<h2>The one real edge — market timing (honest bottom line)</h2>
<div style="font-size:14px">__BOTTOM__</div>
<div class="note">Full method &amp; caveats in the project's REPORT_EDGE. Research, not investment advice.</div>
</div>
<div class="sub" style="margin-top:24px;font-size:12px">Auto-generated daily from the private psx-quant project (read-only). Sister project: <a href="https://971jawad.github.io/pak-terminal/">Pak Terminal</a>.</div>
</div>
"""

if __name__ == "__main__":
    build()
