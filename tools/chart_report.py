"""增强版 HTML 报告生成器 — 支持 Chart.js 图表 + 暖黄纸质风格。

用法:
    python tools/chart_report.py --config reports/data.json --output reports/report.html

config JSON 格式:
{
  "title": "报告标题",
  "subtitle": "副标题",
  "date": "2026-05-13",
  "sections": [
    {"type": "markdown", "title": "章节标题", "content": "markdown文本"},
    {"type": "bar", "title": "图表标题", "labels": [...], "datasets": [...]},
    {"type": "horizontal_bar", ...},
    {"type": "pie", ...},
    {"type": "doughnut", ...},
    {"type": "stacked_bar", ...},
    {"type": "table", "title": "...", "headers": [...], "rows": [...], "highlights": {...}},
    {"type": "gauge", "title": "市场温度计", "score": 68, "label": "偏热", "indicators": [...]},
    {"type": "radar", "title": "情绪雷达", "labels": [...], "datasets": [...]}
  ]
}
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from datetime import datetime

CHART_COLORS = [
    "#c0392b", "#e74c3c", "#e67e22", "#f39c12", "#27ae60",
    "#2ecc71", "#16a085", "#1abc9c", "#2980b9", "#3498db",
    "#8e44ad", "#9b59b6", "#d35400", "#c0392b", "#7f8c8d",
    "#34495e", "#1a5276", "#6c3483", "#a04000", "#117a65",
]

WARM_CHART_COLORS = [
    "#8b6914", "#c4993a", "#a67c28", "#d4a94a", "#6b4c1e",
    "#7a5a2e", "#b8860b", "#cd853f", "#daa520", "#d2691e",
    "#8b4513", "#a0522d", "#bc8f8f", "#f4a460", "#c8a96e",
]


def _inline(text: str) -> str:
    text = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", text)
    text = re.sub(r"\*(.+?)\*", r"<em>\1</em>", text)
    text = re.sub(r"`(.+?)`", r"<code>\1</code>", text)
    return text


def _md_to_html(md: str) -> str:
    lines = md.split("\n")
    html_parts: list[str] = []
    i = 0
    in_ul = False

    while i < len(lines):
        line = lines[i]
        stripped = line.strip()

        if "|" in stripped and i + 1 < len(lines) and re.match(r"^\s*\|[\s\-:|]+\|\s*$", lines[i + 1].strip()):
            if in_ul:
                html_parts.append("</ul>")
                in_ul = False
            table_html, end = _parse_table(lines, i)
            html_parts.append(table_html)
            i = end
            continue

        m = re.match(r"^(#{1,4})\s+(.+)$", stripped)
        if m:
            if in_ul:
                html_parts.append("</ul>")
                in_ul = False
            level = len(m.group(1))
            html_parts.append(f"<h{level}>{_inline(m.group(2))}</h{level}>")
            i += 1
            continue

        if re.match(r"^[-*_]{3,}\s*$", stripped):
            if in_ul:
                html_parts.append("</ul>")
                in_ul = False
            html_parts.append("<hr>")
            i += 1
            continue

        m = re.match(r"^[-*+]\s+(.+)$", stripped)
        if m:
            if not in_ul:
                html_parts.append("<ul>")
                in_ul = True
            html_parts.append(f"<li>{_inline(m.group(1))}</li>")
            i += 1
            continue

        m = re.match(r"^\d+[.)]\s+(.+)$", stripped)
        if m:
            if not in_ul:
                html_parts.append("<ul>")
                in_ul = True
            html_parts.append(f"<li>{_inline(m.group(1))}</li>")
            i += 1
            continue

        if not stripped:
            if in_ul:
                html_parts.append("</ul>")
                in_ul = False
            i += 1
            continue

        if in_ul:
            html_parts.append("</ul>")
            in_ul = False
        html_parts.append(f"<p>{_inline(stripped)}</p>")
        i += 1

    if in_ul:
        html_parts.append("</ul>")
    return "\n".join(html_parts)


def _parse_table(lines, start):
    header_line = lines[start].strip().strip("|")
    headers = [h.strip() for h in header_line.split("|")]
    sep = lines[start + 1].strip()
    aligns = []
    for cell in sep.strip("|").split("|"):
        c = cell.strip()
        if c.startswith(":") and c.endswith(":"):
            aligns.append("center")
        elif c.endswith(":"):
            aligns.append("right")
        else:
            aligns.append("left")
    while len(aligns) < len(headers):
        aligns.append("left")

    rows = []
    i = start + 2
    while i < len(lines):
        l = lines[i].strip()
        if not l or "|" not in l:
            break
        rows.append([c.strip() for c in l.strip("|").split("|")])
        i += 1

    parts = ['<div class="table-wrap"><table><thead><tr>']
    for j, h in enumerate(headers):
        a = aligns[j] if j < len(aligns) else "left"
        parts.append(f'<th style="text-align:{a}">{_inline(h)}</th>')
    parts.append("</tr></thead><tbody>")
    for row in rows:
        parts.append("<tr>")
        for j, cell in enumerate(row):
            a = aligns[j] if j < len(aligns) else "left"
            parts.append(f'<td style="text-align:{a}">{_inline(cell)}</td>')
        parts.append("</tr>")
    parts.append("</tbody></table></div>")
    return "\n".join(parts), i


def _render_chart(section: dict, chart_id: str) -> str:
    chart_type = section["type"]
    if chart_type == "horizontal_bar":
        chart_type = "bar"
        index_axis = "indexAxis: 'y',"
    else:
        index_axis = ""

    if chart_type == "stacked_bar":
        chart_type = "bar"
        stacked = """scales: { x: { stacked: true, ticks:{color:'#6b4c1e'}, grid:{color:'rgba(139,119,85,0.15)'} }, y: { stacked: true, ticks:{color:'#6b4c1e'}, grid:{color:'rgba(139,119,85,0.15)'} } },"""
    else:
        stacked = f"""scales: {{ x: {{ {index_axis} ticks:{{color:'#6b4c1e'}}, grid:{{color:'rgba(139,119,85,0.15)'}} }}, y: {{ ticks:{{color:'#6b4c1e'}}, grid:{{color:'rgba(139,119,85,0.15)'}} }} }},""" if chart_type == "bar" else ""

    labels = json.dumps(section.get("labels", []), ensure_ascii=False)
    datasets = section.get("datasets", [])
    for i, ds in enumerate(datasets):
        if "backgroundColor" not in ds:
            if chart_type in ("pie", "doughnut"):
                ds["backgroundColor"] = WARM_CHART_COLORS[:len(section.get("labels", []))]
            else:
                ds["backgroundColor"] = WARM_CHART_COLORS[i % len(WARM_CHART_COLORS)]
        if "borderColor" not in ds and chart_type in ("pie", "doughnut"):
            ds["borderColor"] = "#f5eed6"
            ds["borderWidth"] = 2

    datasets_json = json.dumps(datasets, ensure_ascii=False)
    height = section.get("height", "320px")
    subtitle = section.get("subtitle", "")
    subtitle_html = f'<p style="font-size:13px;color:#9e8e6e;margin-top:4px;">{subtitle}</p>' if subtitle else ""

    legend_display = "true" if chart_type in ("pie", "doughnut") or len(datasets) > 1 else "false"

    return f"""
    <div class="card">
        <h2>{section.get('title', '')}</h2>
        {subtitle_html}
        <div style="position:relative;height:{height};margin-top:16px;">
            <canvas id="{chart_id}"></canvas>
        </div>
        <script>
        new Chart(document.getElementById('{chart_id}'), {{
            type: '{chart_type}',
            data: {{ labels: {labels}, datasets: {datasets_json} }},
            options: {{
                {index_axis}
                responsive: true,
                maintainAspectRatio: false,
                plugins: {{
                    legend: {{ display: {legend_display}, labels: {{ color: '#6b4c1e', font: {{ size: 12 }} }} }},
                }},
                {stacked}
            }}
        }});
        </script>
    </div>"""


def _render_table(section: dict) -> str:
    headers = section.get("headers", [])
    rows = section.get("rows", [])
    highlights = section.get("highlights", {})
    subtitle = section.get("subtitle", "")
    subtitle_html = f'<p style="font-size:13px;color:#9e8e6e;margin-top:4px;">{subtitle}</p>' if subtitle else ""

    parts = [f'<div class="card"><h2>{section.get("title", "")}</h2>{subtitle_html}']
    parts.append('<div class="table-wrap"><table><thead><tr>')
    for h in headers:
        parts.append(f'<th>{h}</th>')
    parts.append('</tr></thead><tbody>')

    for row in rows:
        parts.append('<tr>')
        for j, cell in enumerate(row):
            style = ""
            cell_str = str(cell) if cell is not None else ""
            if j in highlights.get("positive_cols", []):
                try:
                    val = float(cell_str.replace("%", "").replace("+", ""))
                    if val > 0:
                        style = ' style="color:#c0392b;font-weight:600"'
                    elif val < 0:
                        style = ' style="color:#27ae60;font-weight:600"'
                except ValueError:
                    pass
            if j in highlights.get("tag_cols", []):
                cell_str = f'<span class="tag">{cell_str}</span>'
            parts.append(f'<td{style}>{cell_str}</td>')
        parts.append('</tr>')

    parts.append('</tbody></table></div></div>')
    return "\n".join(parts)


def _render_gauge(section: dict) -> str:
    score = section.get("score", 50)
    label = section.get("label", "")
    indicators = section.get("indicators", [])
    subtitle = section.get("subtitle", "")

    zones = [
        (80, "#c0392b", "极度贪婪", "市场过热，追高风险极大，建议减仓观望"),
        (65, "#e67e22", "贪婪",     "市场偏热，赚钱效应集中于龙头，注意分化"),
        (45, "#d4a94a", "中性",     "市场情绪适中，多空均衡，可正常操作"),
        (25, "#27ae60", "恐惧",     "市场偏冷，恐慌情绪蔓延，关注超跌机会"),
        (0,  "#2980b9", "极度恐惧", "市场冰点，往往是中长期布局的好时机"),
    ]
    zone_color, zone_name, zone_desc = "#d4a94a", "中性", ""
    for threshold, color, name, desc in zones:
        if score >= threshold:
            zone_color, zone_name, zone_desc = color, name, desc
            break
    display_label = label or zone_name

    TUBE_H = 240
    BULB_D = 48
    fill_px = max(6, int(TUBE_H * score / 100))

    scale_data = [
        (0,  "极度恐惧", "#2980b9"), (25, "恐惧", "#27ae60"),
        (50, "中性",     "#d4a94a"), (75, "贪婪", "#e67e22"),
        (100,"极度贪婪", "#c0392b"),
    ]
    scale_html = ""
    for val, txt, col in scale_data:
        y = TUBE_H - int(TUBE_H * val / 100)
        active = " thm-active" if abs(score - val) <= 12 else ""
        scale_html += (
            f'<div class="thm-mark{active}" style="top:{y}px">'
            f'<span class="thm-mv">{val}</span>'
            f'<span class="thm-mt"></span>'
            f'<span class="thm-ml" style="color:{col}">{txt}</span>'
            f'</div>'
        )

    ind_html = ""
    for ind in indicators:
        sig = ind.get("signal", "neutral")
        sc = {"danger":"#c0392b","warning":"#e67e22","neutral":"#a67c28","safe":"#27ae60","cold":"#2980b9"}
        c = sc.get(sig, "#a67c28")
        w = max(4, min(100, ind.get("score", 50)))
        ind_html += (
            f'<div class="thm-ind">'
            f'<div class="thm-ind-r"><span class="thm-ind-n">{ind.get("name","")}</span>'
            f'<span class="thm-ind-v" style="color:{c}">{ind.get("value","")}</span></div>'
            f'<div class="thm-bar-bg"><div class="thm-bar-fg" style="width:{w}%;background:{c}"></div></div>'
            f'</div>'
        )

    return f"""
    <div class="card thm-card">
        <h2>{section.get("title","市场温度计")}</h2>
        {f'<p class="thm-sub">{subtitle}</p>' if subtitle else ""}
        <div class="thm-outer">
          <div class="thm-left" style="height:{TUBE_H + BULB_D + 10}px">
            <div class="thm-marks" style="height:{TUBE_H}px">{scale_html}</div>
            <div class="thm-device">
              <div class="thm-tube" style="height:{TUBE_H}px">
                <div class="thm-fill" style="height:{fill_px}px;background:linear-gradient(to top,{zone_color},{zone_color}cc)"></div>
                <div class="thm-shine"></div>
              </div>
              <div class="thm-bulb">
                <div class="thm-bulb-fill" style="background:radial-gradient(circle at 35% 35%,{zone_color}dd,{zone_color})"></div>
                <div class="thm-bulb-hi"></div>
              </div>
            </div>
          </div>
          <div class="thm-right">
            <div class="thm-score-row">
              <span class="thm-num" style="color:{zone_color}">{score}</span>
              <span class="thm-den">/100</span>
            </div>
            <span class="thm-badge" style="background:{zone_color}">{display_label}</span>
            <p class="thm-desc">{zone_desc}</p>
            {f'<div class="thm-inds">{ind_html}</div>' if indicators else ""}
          </div>
        </div>
    </div>"""


def _render_radar(section: dict, chart_id: str) -> str:
    labels = json.dumps(section.get("labels", []), ensure_ascii=False)
    datasets = section.get("datasets", [])
    for ds in datasets:
        if "backgroundColor" not in ds:
            ds["backgroundColor"] = "rgba(139,105,20,0.2)"
        if "borderColor" not in ds:
            ds["borderColor"] = "#8b6914"
        if "pointBackgroundColor" not in ds:
            ds["pointBackgroundColor"] = "#8b6914"
        if "borderWidth" not in ds:
            ds["borderWidth"] = 2
    datasets_json = json.dumps(datasets, ensure_ascii=False)
    height = section.get("height", "360px")
    subtitle = section.get("subtitle", "")
    subtitle_html = f'<p style="font-size:13px;color:#9e8e6e;margin-top:4px;">{subtitle}</p>' if subtitle else ""

    return f"""
    <div class="card">
        <h2>{section.get('title', '')}</h2>
        {subtitle_html}
        <div style="position:relative;height:{height};margin-top:16px;">
            <canvas id="{chart_id}"></canvas>
        </div>
        <script>
        new Chart(document.getElementById('{chart_id}'), {{
            type: 'radar',
            data: {{ labels: {labels}, datasets: {datasets_json} }},
            options: {{
                responsive: true,
                maintainAspectRatio: false,
                scales: {{
                    r: {{
                        beginAtZero: true,
                        max: 100,
                        ticks: {{ stepSize: 20, color: '#6b4c1e', backdropColor: 'transparent', font: {{ size: 11 }} }},
                        grid: {{ color: 'rgba(139,119,85,0.2)' }},
                        angleLines: {{ color: 'rgba(139,119,85,0.2)' }},
                        pointLabels: {{ color: '#6b4c1e', font: {{ size: 13, weight: '600' }} }}
                    }}
                }},
                plugins: {{
                    legend: {{ display: {str(len(datasets) > 1).lower()}, labels: {{ color: '#6b4c1e' }} }}
                }}
            }}
        }});
        </script>
    </div>"""


STYLE = """
@import url('https://fonts.googleapis.com/css2?family=Noto+Serif+SC:wght@400;600;700&display=swap');
* { margin: 0; padding: 0; box-sizing: border-box; }
body {
  font-family: 'Noto Serif SC', 'Songti SC', Georgia, serif;
  background: #d4c5a9;
  background-image:
    repeating-linear-gradient(0deg, transparent, transparent 28px, rgba(139,119,85,0.06) 28px, rgba(139,119,85,0.06) 29px),
    repeating-linear-gradient(90deg, transparent, transparent 28px, rgba(139,119,85,0.04) 28px, rgba(139,119,85,0.04) 29px);
  color: #3d2e1c; line-height: 1.8; min-height: 100vh;
}
.container { max-width: 960px; margin: 0 auto; padding: 32px 24px; }
.header {
  background: linear-gradient(135deg, #8b6914, #a67c28, #c4993a);
  color: #fdf6e3; padding: 40px 36px; border-radius: 4px; margin-bottom: 28px;
  box-shadow: 0 4px 20px rgba(120,85,30,0.3); border: 1px solid #a67c28;
  position: relative; overflow: hidden;
}
.header::before {
  content: ''; position: absolute; top: 0; left: 0; right: 0; bottom: 0;
  background: url("data:image/svg+xml,%3Csvg width='60' height='60' viewBox='0 0 60 60' xmlns='http://www.w3.org/2000/svg'%3E%3Cg fill='none' fill-rule='evenodd'%3E%3Cg fill='%23ffffff' fill-opacity='0.05'%3E%3Cpath d='M36 34v-4h-2v4h-4v2h4v4h2v-4h4v-2h-4zm0-30V0h-2v4h-4v2h4v4h2V6h4V4h-4zM6 34v-4H4v4H0v2h4v4h2v-4h4v-2H6zM6 4V0H4v4H0v2h4v4h2V6h4V4H6z'/%3E%3C/g%3E%3C/g%3E%3C/svg%3E");
  opacity: 0.3;
}
.header h1 { font-size: 26px; margin-bottom: 8px; position: relative; letter-spacing: 2px; }
.header .meta { opacity: 0.9; font-size: 13px; position: relative; }
.header .badge { display: inline-block; background: rgba(253,246,227,0.2); border: 1px solid rgba(253,246,227,0.3); padding: 5px 16px; border-radius: 3px; margin-top: 14px; font-size: 13px; letter-spacing: 1px; position: relative; }
.card {
  background: #f5eed6; border-radius: 3px; padding: 28px 32px; margin-bottom: 20px;
  border: 1px solid #c4b896; box-shadow: 0 2px 12px rgba(100,75,30,0.1), inset 0 0 60px rgba(200,180,140,0.15);
  position: relative;
}
.card::before { content: ''; position: absolute; top: 0; left: 0; width: 4px; height: 100%; background: linear-gradient(180deg, #a67c28, #c4993a, #a67c28); border-radius: 3px 0 0 3px; }
.card h2 { color: #6b4c1e; margin-bottom: 18px; font-size: 19px; padding-bottom: 10px; border-bottom: 2px solid #d4c5a0; letter-spacing: 1px; }
.card .content { font-size: 14.5px; color: #4a3620; }
.card .content h3 { color: #7a5a2e; margin: 20px 0 10px; font-size: 16px; }
.card .content h4 { color: #8b6914; margin: 16px 0 8px; font-size: 15px; }
.card .content strong { color: #8b4513; }
.card .content code { background: #e8dfc5; padding: 1px 5px; border-radius: 2px; font-size: 13px; color: #6b4c1e; }
.card .content p { margin-bottom: 10px; }
.card .content ul { padding-left: 22px; margin: 8px 0; }
.card .content li { margin-bottom: 5px; }
.card .content li::marker { color: #a67c28; }
.card .content hr { border: none; border-top: 1px dashed #c4b896; margin: 16px 0; }
.table-wrap { overflow-x: auto; margin: 14px 0; }
table { width: 100%; border-collapse: collapse; font-size: 13.5px; background: #faf4e4; border: 1px solid #c4b896; }
thead { background: linear-gradient(180deg, #e8d9b4, #dfd0ab); }
th { padding: 10px 14px; text-align: left; font-weight: 600; color: #5a3e18; border-bottom: 2px solid #c4a96a; font-size: 13px; white-space: nowrap; }
td { padding: 9px 14px; border-bottom: 1px solid #e0d5be; color: #4a3620; }
tbody tr:hover td { background: #f0e8cf; }
tbody tr:nth-child(even) td { background: #f5eed6; }
.tag { display: inline-block; background: linear-gradient(135deg, #a67c28, #c4993a); color: #fdf6e3; padding: 2px 10px; border-radius: 12px; font-size: 11.5px; font-weight: 600; letter-spacing: 0.5px; }
.chart-row { display: flex; gap: 20px; margin-bottom: 0; }
.chart-row .card { flex: 1; min-width: 0; margin-bottom: 20px; }
.disclaimer { background: #f0e4c4; border: 1px solid #c4a96a; border-left: 4px solid #a67c28; border-radius: 3px; padding: 18px 24px; font-size: 12.5px; color: #7a5a2e; margin-top: 28px; line-height: 1.7; }
.disclaimer strong { color: #8b4513; }
.footer { text-align: center; padding: 28px; color: #9e8e6e; font-size: 12px; letter-spacing: 1px; }
@media (max-width: 768px) { .chart-row { flex-direction: column; } }

/* ── Thermometer ── */
.thm-card { overflow: visible; }
.thm-sub  { font-size:13px; color:#9e8e6e; margin:4px 0 0; }

.thm-outer { display:flex; gap:32px; align-items:center; margin-top:18px; }
.thm-left  { position:relative; flex:0 0 auto; display:flex; align-items:flex-start; }
.thm-right { flex:1; min-width:0; }

/* ─ scale marks ─ */
.thm-marks { position:relative; width:80px; margin-right:8px; }
.thm-mark  { position:absolute; left:0; right:0; display:flex; align-items:center;
  transform:translateY(-50%); white-space:nowrap; opacity:.75; transition:opacity .3s; }
.thm-mark.thm-active { opacity:1; }
.thm-mv { font-size:11px; color:#b0a48a; width:22px; text-align:right; font-weight:600; }
.thm-mt { display:inline-block; width:8px; height:1.5px; background:#c4b896; margin:0 5px; }
.thm-ml { font-size:10.5px; font-weight:600; letter-spacing:.3px; }
.thm-active .thm-mv { color:#5a3e18; font-size:12.5px; }
.thm-active .thm-mt { width:12px; height:2.5px; background:#8b6914; }
.thm-active .thm-ml { font-size:12.5px; font-weight:700; }

/* ─ thermometer body ─ */
.thm-device { position:relative; width:30px; }

.thm-tube {
  position:relative; width:30px;
  background: linear-gradient(90deg, #d8d0ba, #f0eadb 30%, #faf6ee 50%, #ede5d2 75%, #d8d0ba);
  border:2px solid #bfb597; border-radius:15px 15px 0 0;
  overflow:hidden;
  box-shadow: inset 2px 0 6px rgba(0,0,0,.04), inset -1px 0 4px rgba(255,255,255,.4),
              2px 2px 8px rgba(100,80,40,.1);
}
.thm-fill {
  position:absolute; bottom:0; left:4px; right:4px;
  border-radius:10px 10px 0 0;
  box-shadow: 0 -2px 6px rgba(0,0,0,.06);
  transition: height 1.2s cubic-bezier(.3,.8,.3,1);
}
.thm-shine {
  position:absolute; top:8px; bottom:8px; left:6px; width:5px;
  background: linear-gradient(180deg, rgba(255,255,255,.5), rgba(255,255,255,.12) 50%, rgba(255,255,255,.25));
  border-radius:3px; pointer-events:none;
}

.thm-bulb {
  position:relative; width:48px; height:48px; margin:-4px auto 0;
  border:2px solid #bfb597; border-radius:50%;
  box-shadow: 0 4px 12px rgba(80,60,20,.15), inset 0 -2px 6px rgba(0,0,0,.08);
}
.thm-bulb-fill {
  position:absolute; inset:3px; border-radius:50%;
  transition: background .6s;
}
.thm-bulb-hi {
  position:absolute; top:8px; left:10px; width:13px; height:13px;
  background: radial-gradient(circle, rgba(255,255,255,.55), transparent 70%);
  border-radius:50%;
}

/* ─ right side ─ */
.thm-score-row { display:flex; align-items:baseline; gap:3px; margin-bottom:8px; }
.thm-num  { font-size:54px; font-weight:700; line-height:1; letter-spacing:-2px; }
.thm-den  { font-size:20px; color:#b0a48a; font-weight:600; }
.thm-badge {
  display:inline-block; color:#fff; padding:5px 18px; border-radius:4px;
  font-size:15px; font-weight:700; letter-spacing:3px; margin-bottom:14px;
  box-shadow:0 2px 8px rgba(0,0,0,.15);
}
.thm-desc { font-size:13.5px; color:#6b4c1e; line-height:1.7; margin-bottom:16px; }

/* ─ indicators ─ */
.thm-inds   { border-top:1.5px solid #d4c5a0; padding-top:14px; }
.thm-ind    { margin-bottom:10px; }
.thm-ind-r  { display:flex; justify-content:space-between; margin-bottom:3px; }
.thm-ind-n  { font-size:12.5px; color:#6b4c1e; font-weight:600; }
.thm-ind-v  { font-size:12px; font-weight:700; }
.thm-bar-bg { height:7px; background:#e8dfc5; border-radius:4px; overflow:hidden; }
.thm-bar-fg { height:100%; border-radius:4px; transition:width .8s ease; }

@media(max-width:768px) {
  .thm-outer { flex-direction:column; align-items:center; }
}
"""


def generate_report(config: dict) -> str:
    title = config.get("title", "投研报告")
    subtitle = config.get("subtitle", "")
    date_str = config.get("date", datetime.now().strftime("%Y-%m-%d"))
    sections = config.get("sections", [])

    cards_html = ""
    chart_counter = 0
    row_buffer = []

    def flush_row():
        nonlocal cards_html, row_buffer
        if not row_buffer:
            return
        if len(row_buffer) == 1:
            cards_html += row_buffer[0]
        else:
            cards_html += '<div class="chart-row">' + "".join(row_buffer) + '</div>'
        row_buffer = []

    for sec in sections:
        sec_type = sec.get("type", "markdown")

        if sec_type == "markdown":
            flush_row()
            content_html = _md_to_html(sec.get("content", ""))
            cards_html += f"""
    <div class="card">
        <h2>{sec.get('title', '')}</h2>
        <div class="content">{content_html}</div>
    </div>"""

        elif sec_type == "table":
            flush_row()
            cards_html += _render_table(sec)

        elif sec_type == "gauge":
            flush_row()
            gauge_html = _render_gauge(sec)
            if sec.get("half_width"):
                row_buffer.append(gauge_html)
                if len(row_buffer) == 2:
                    flush_row()
            else:
                cards_html += gauge_html

        elif sec_type == "radar":
            chart_id = f"chart_{chart_counter}"
            chart_counter += 1
            radar_html = _render_radar(sec, chart_id)
            if sec.get("half_width"):
                row_buffer.append(radar_html)
                if len(row_buffer) == 2:
                    flush_row()
            else:
                flush_row()
                cards_html += radar_html

        elif sec_type in ("bar", "horizontal_bar", "pie", "doughnut", "stacked_bar"):
            chart_id = f"chart_{chart_counter}"
            chart_counter += 1
            chart_html = _render_chart(sec, chart_id)
            if sec.get("half_width"):
                row_buffer.append(chart_html)
                if len(row_buffer) == 2:
                    flush_row()
            else:
                flush_row()
                cards_html += chart_html

        elif sec_type == "row_start":
            flush_row()
        elif sec_type == "row_end":
            flush_row()

    flush_row()

    return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{title}</title>
<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.7/dist/chart.umd.min.js"></script>
<style>{STYLE}</style>
</head>
<body>
<div class="container">
    <div class="header">
        <h1>{title}</h1>
        <div class="meta">{subtitle} | 生成时间：{date_str}</div>
        <div class="badge">Claude Code 全市场分析 Agent</div>
    </div>
    {cards_html}
    <div class="disclaimer">
        <strong>免责声明</strong> — 本报告由 Claude Code AI 分析系统自动生成，仅供参考研究使用，不构成任何投资建议。投资有风险，入市需谨慎。
    </div>
    <div class="footer">Claude Code 全市场投研 Agent | Powered by Claude + AKShare + Chart.js</div>
</div>
</body>
</html>"""


def main():
    parser = argparse.ArgumentParser(description="增强版 HTML 报告生成器（支持图表）")
    parser.add_argument("--config", required=True, help="JSON 配置文件路径")
    parser.add_argument("--output", required=True, help="输出 HTML 文件路径")
    args = parser.parse_args()

    with open(args.config, "r", encoding="utf-8") as f:
        config = json.load(f)

    html = generate_report(config)
    os.makedirs(os.path.dirname(args.output) or ".", exist_ok=True)
    with open(args.output, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"报告已生成: {args.output}")


if __name__ == "__main__":
    main()
