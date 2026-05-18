"""
Generates the final arbitrage report in HTML and JSON formats.

Each entry includes:
  - Full question text as it appears on the originating platform
  - Hyperlink to the exact market page
  - YES % and NO % from both platforms
  - ROI
  - LLM confidence + reasoning
  - Which LLM model verified it
"""

import json
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any


def _price_pct(price) -> str:
    try:
        return f"{float(price) * 100:.1f}%"
    except (TypeError, ValueError):
        return "N/A"


def _url_link(url: str, text: str) -> str:
    if url and url.startswith("http"):
        return f'<a href="{url}" target="_blank" rel="noopener noreferrer">{text}</a>'
    return text


def _verdict_badge(result: dict) -> str:
    is_arb = result.get("llm_is_arb")
    conf   = result.get("llm_confidence", 0)
    if is_arb is True:
        color = "#22c55e" if conf >= 80 else "#84cc16"
        label = f"CONFIRMED ({conf}%)"
    elif is_arb is False:
        color = "#ef4444"
        label = f"NOT ARB ({conf}%)"
    else:
        color = "#94a3b8"
        label = "UNVERIFIED"
    return (
        f'<span style="background:{color};color:#fff;padding:2px 8px;'
        f'border-radius:4px;font-size:0.78em;font-weight:700">{label}</span>'
    )


def build_html_report(results: List[Dict[str, Any]], out_path: Path):
    confirmed = [r for r in results if r.get("llm_is_arb")]
    unconfirmed = [r for r in results if not r.get("llm_is_arb")]
    all_sorted = confirmed + unconfirmed

    rows = ""
    for rank, r in enumerate(all_sorted, 1):
        ma = r.get("marketA", {})
        mb = r.get("marketB", {})

        title_a = ma.get("title", "Unknown")
        title_b = mb.get("title", "Unknown")
        url_a   = ma.get("marketUrl", "")
        url_b   = mb.get("marketUrl", "")
        plat_a  = ma.get("platform", "?")
        plat_b  = mb.get("platform", "?")
        yes_a   = _price_pct(ma.get("yesPrice", 0))
        no_a    = _price_pct(ma.get("noPrice", 0))
        yes_b   = _price_pct(mb.get("yesPrice", 0))
        no_b    = _price_pct(mb.get("noPrice", 0))
        roi     = f"{r.get('roi', 0):.2f}%"
        score   = f"{r.get('matchScore', 0):.1f}"
        model   = r.get("llm_model", "?")
        reason  = r.get("llm_reasoning", "")
        end_a   = ma.get("endDate", "") or ""
        end_b   = mb.get("endDate", "") or ""
        end_str = f"{end_a[:10] if end_a else '—'} / {end_b[:10] if end_b else '—'}"

        row_bg = "#f0fdf4" if r.get("llm_is_arb") else "#fff"

        rows += f"""
        <tr style="background:{row_bg}">
          <td style="text-align:center;font-weight:700;font-size:1.1em">{rank}</td>
          <td>
            <div style="font-size:0.72em;color:#64748b;font-weight:600;text-transform:uppercase">{plat_a}</div>
            <div style="font-weight:600;line-height:1.35">{_url_link(url_a, title_a)}</div>
            <div style="margin-top:4px">
              <span style="background:#dcfce7;color:#166534;padding:1px 6px;border-radius:3px;font-size:0.8em">YES {yes_a}</span>
              <span style="background:#fee2e2;color:#991b1b;padding:1px 6px;border-radius:3px;font-size:0.8em;margin-left:4px">NO {no_a}</span>
            </div>
          </td>
          <td>
            <div style="font-size:0.72em;color:#64748b;font-weight:600;text-transform:uppercase">{plat_b}</div>
            <div style="font-weight:600;line-height:1.35">{_url_link(url_b, title_b)}</div>
            <div style="margin-top:4px">
              <span style="background:#dcfce7;color:#166534;padding:1px 6px;border-radius:3px;font-size:0.8em">YES {yes_b}</span>
              <span style="background:#fee2e2;color:#991b1b;padding:1px 6px;border-radius:3px;font-size:0.8em;margin-left:4px">NO {no_b}</span>
            </div>
          </td>
          <td style="text-align:center;font-weight:700;color:#16a34a;font-size:1.05em">{roi}</td>
          <td style="text-align:center;color:#64748b">{score}</td>
          <td style="text-align:center">{_verdict_badge(r)}<div style="font-size:0.72em;color:#94a3b8;margin-top:3px">{model.split(':')[0]}</div></td>
          <td style="font-size:0.82em;color:#475569;max-width:260px">{reason}</td>
          <td style="text-align:center;font-size:0.78em;color:#94a3b8">{end_str}</td>
        </tr>"""

    ts = datetime.now().strftime("%B %d, %Y %H:%M")
    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Arbitrage Report — {ts}</title>
<style>
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
         background: #f8fafc; color: #1e293b; padding: 24px; }}
  h1 {{ font-size: 1.6em; font-weight: 800; margin-bottom: 4px; }}
  .meta {{ color: #64748b; font-size: 0.88em; margin-bottom: 20px; }}
  .stats {{ display: flex; gap: 16px; margin-bottom: 24px; flex-wrap: wrap; }}
  .stat {{ background: #fff; border: 1px solid #e2e8f0; border-radius: 8px;
           padding: 12px 20px; min-width: 120px; }}
  .stat-val {{ font-size: 1.8em; font-weight: 800; color: #0f172a; }}
  .stat-lbl {{ font-size: 0.75em; color: #64748b; text-transform: uppercase; font-weight: 600; }}
  table {{ width: 100%; border-collapse: collapse; background: #fff;
           border-radius: 10px; overflow: hidden;
           box-shadow: 0 1px 3px rgba(0,0,0,.1); font-size: 0.88em; }}
  th {{ background: #0f172a; color: #f8fafc; padding: 10px 12px;
        text-align: left; font-weight: 600; font-size: 0.8em; text-transform: uppercase; }}
  td {{ padding: 10px 12px; border-bottom: 1px solid #f1f5f9; vertical-align: top; }}
  tr:last-child td {{ border-bottom: none; }}
  a {{ color: #2563eb; text-decoration: none; }}
  a:hover {{ text-decoration: underline; }}
  .note {{ margin-top: 16px; font-size: 0.78em; color: #94a3b8; }}
</style>
</head>
<body>
<h1>Prediction Market Arbitrage Report</h1>
<div class="meta">Generated {ts} &nbsp;|&nbsp; Markets: Predicit · Polymarket · IBKR</div>

<div class="stats">
  <div class="stat"><div class="stat-val">{len(all_sorted)}</div><div class="stat-lbl">Total Pairs</div></div>
  <div class="stat"><div class="stat-val">{len(confirmed)}</div><div class="stat-lbl">LLM Confirmed</div></div>
  <div class="stat"><div class="stat-val">{max((r.get('roi',0) for r in all_sorted), default=0):.1f}%</div><div class="stat-lbl">Top ROI</div></div>
  <div class="stat"><div class="stat-val">{sum(1 for r in confirmed if r.get('llm_confidence',0)>=80)}</div><div class="stat-lbl">High Confidence</div></div>
</div>

<table>
  <thead>
    <tr>
      <th>#</th>
      <th>Platform A — Full Question</th>
      <th>Platform B — Full Question</th>
      <th>ROI</th>
      <th>Match</th>
      <th>LLM Verdict</th>
      <th>Reasoning</th>
      <th>Closes</th>
    </tr>
  </thead>
  <tbody>
    {rows}
  </tbody>
</table>

<div class="note">
  Click any market title to open it directly on the originating platform.
  YES/NO prices reflect data at time of scan. Verify prices before trading.
  LLM model column shows which model verified each pair.
</div>
</body>
</html>"""

    out_path.write_text(html, encoding="utf-8")


def build_json_report(results: List[Dict[str, Any]], out_path: Path):
    output = []
    for rank, r in enumerate(results, 1):
        ma = r.get("marketA", {})
        mb = r.get("marketB", {})
        output.append({
            "rank":            rank,
            "roi":             round(float(r.get("roi", 0)), 4),
            "matchScore":      r.get("matchScore", 0),
            "llm_is_arb":     r.get("llm_is_arb"),
            "llm_confidence":  r.get("llm_confidence", 0),
            "llm_reasoning":   r.get("llm_reasoning", ""),
            "llm_model":       r.get("llm_model", ""),
            "platformA": {
                "platform":   ma.get("platform"),
                "title":      ma.get("title"),
                "url":        ma.get("marketUrl", ""),
                "yes_pct":    round(float(ma.get("yesPrice", 0)) * 100, 1),
                "no_pct":     round(float(ma.get("noPrice", 0)) * 100, 1),
                "closes":     ma.get("endDate"),
            },
            "platformB": {
                "platform":   mb.get("platform"),
                "title":      mb.get("title"),
                "url":        mb.get("marketUrl", ""),
                "yes_pct":    round(float(mb.get("yesPrice", 0)) * 100, 1),
                "no_pct":     round(float(mb.get("noPrice", 0)) * 100, 1),
                "closes":     mb.get("endDate"),
            },
        })

    out_path.write_text(json.dumps(output, indent=2), encoding="utf-8")
