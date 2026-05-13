"""HTML 报告生成器 — 将 Markdown 分析报告转为暖黄纸质风格 HTML。

用法:
    python tools/report.py --code 600519 --name 贵州茅台 --input report.md --output reports/600519.html
    echo "markdown内容" | python tools/report.py --code 600519 --name 贵州茅台 --output reports/600519.html
"""

from __future__ import annotations

import argparse
import os
import re
import sys
from datetime import datetime


def _inline(text: str) -> str:
    text = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", text)
    text = re.sub(r"\*(.+?)\*", r"<em>\1</em>", text)
    text = re.sub(r"`(.+?)`", r"<code>\1</code>", text)
    return text


def _parse_table(lines: list[str], start: int) -> dict:
    header_line = lines[start].strip().strip("|")
    headers = [h.strip() for h in header_line.split("|")]

    sep_line = lines[start + 1].strip()
    aligns: list[str] = []
    for cell in sep_line.strip("|").split("|"):
        cell = cell.strip()
        if cell.startswith(":") and cell.endswith(":"):
            aligns.append("center")
        elif cell.endswith(":"):
            aligns.append("right")
        else:
            aligns.append("left")
    while len(aligns) < len(headers):
        aligns.append("left")

    rows: list[list[str]] = []
    i = start + 2
    while i < len(lines):
        line = lines[i].strip()
        if not line or "|" not in line:
            break
        cells = [c.strip() for c in line.strip("|").split("|")]
        rows.append(cells)
        i += 1

    parts = ['<div class="table-wrap"><table>']
    parts.append("<thead><tr>")
    for j, h in enumerate(headers):
        align = aligns[j] if j < len(aligns) else "left"
        parts.append(f'<th style="text-align:{align}">{_inline(h)}</th>')
    parts.append("</tr></thead><tbody>")
    for row in rows:
        parts.append("<tr>")
        for j, cell in enumerate(row):
            align = aligns[j] if j < len(aligns) else "left"
            parts.append(f'<td style="text-align:{align}">{_inline(cell)}</td>')
        parts.append("</tr>")
    parts.append("</tbody></table></div>")
    return {"html": "\n".join(parts), "end": i}


def md_to_html(md: str) -> str:
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
            table_html = _parse_table(lines, i)
            html_parts.append(table_html["html"])
            i = table_html["end"]
            continue

        m = re.match(r"^(#{1,4})\s+(.+)$", stripped)
        if m:
            if in_ul:
                html_parts.append("</ul>")
                in_ul = False
            level = len(m.group(1))
            text = _inline(m.group(2))
            html_parts.append(f"<h{level}>{text}</h{level}>")
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
.container { max-width: 900px; margin: 0 auto; padding: 32px 24px; }
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
.header .badge {
  display: inline-block; background: rgba(253,246,227,0.2); border: 1px solid rgba(253,246,227,0.3);
  padding: 5px 16px; border-radius: 3px; margin-top: 14px; font-size: 13px; letter-spacing: 1px; position: relative;
}
.card {
  background: #f5eed6; border-radius: 3px; padding: 28px 32px; margin-bottom: 20px;
  border: 1px solid #c4b896; box-shadow: 0 2px 12px rgba(100,75,30,0.1), inset 0 0 60px rgba(200,180,140,0.15);
  position: relative;
}
.card::before {
  content: ''; position: absolute; top: 0; left: 0; width: 4px; height: 100%;
  background: linear-gradient(180deg, #a67c28, #c4993a, #a67c28); border-radius: 3px 0 0 3px;
}
.card h2 { color: #6b4c1e; margin-bottom: 18px; font-size: 19px; padding-bottom: 10px; border-bottom: 2px solid #d4c5a0; letter-spacing: 1px; }
.card .content { font-size: 14.5px; color: #4a3620; }
.card .content h3 { color: #7a5a2e; margin: 20px 0 10px; font-size: 16px; }
.card .content h4 { color: #8b6914; margin: 16px 0 8px; font-size: 15px; }
.card .content strong { color: #8b4513; }
.card .content code { background: #e8dfc5; padding: 1px 5px; border-radius: 2px; font-size: 13px; color: #6b4c1e; }
.card .content em { color: #7a5a2e; }
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
.disclaimer {
  background: #f0e4c4; border: 1px solid #c4a96a; border-left: 4px solid #a67c28;
  border-radius: 3px; padding: 18px 24px; font-size: 12.5px; color: #7a5a2e; margin-top: 28px; line-height: 1.7;
}
.disclaimer strong { color: #8b4513; }
.footer { text-align: center; padding: 28px; color: #9e8e6e; font-size: 12px; letter-spacing: 1px; }
"""


def generate_html(
    markdown: str,
    stock_code: str,
    stock_name: str = "",
    sections: list[dict] | None = None,
) -> str:
    date_str = datetime.now().strftime("%Y-%m-%d %H:%M")
    title = f"{stock_code} {stock_name}".strip()

    if sections:
        cards = ""
        for sec in sections:
            content_html = md_to_html(sec["content"])
            cards += f"""
    <div class="card">
        <h2>{sec['title']}</h2>
        <div class="content">{content_html}</div>
    </div>"""
    else:
        content_html = md_to_html(markdown)
        cards = f"""
    <div class="card">
        <h2>投研分析报告</h2>
        <div class="content">{content_html}</div>
    </div>"""

    return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>A股投研报告 - {title}</title>
<style>{STYLE}</style>
</head>
<body>
<div class="container">
    <div class="header">
        <h1>A股投研报告 | {title}</h1>
        <div class="meta">生成时间：{date_str} | Claude Code AI 深度分析</div>
        <div class="badge">Claude Code 基本面分析 Agent</div>
    </div>
    {cards}
    <div class="disclaimer">
        <strong>免责声明</strong> — 本报告由 Claude Code AI 分析系统自动生成，仅供参考研究使用，不构成任何投资建议。投资有风险，入市需谨慎。数据来源于 AKShare 公开接口，可能存在延迟或缺失。
    </div>
    <div class="footer">Claude Code 基本面分析 Agent | Powered by Claude + AKShare</div>
</div>
</body>
</html>"""


def main():
    parser = argparse.ArgumentParser(description="生成 HTML 投研报告")
    parser.add_argument("--code", required=True, help="股票代码")
    parser.add_argument("--name", default="", help="股票名称")
    parser.add_argument("--input", help="Markdown 文件路径 (不提供则从 stdin 读取)")
    parser.add_argument("--output", required=True, help="输出 HTML 文件路径")
    args = parser.parse_args()

    if args.input:
        with open(args.input, "r", encoding="utf-8") as f:
            markdown = f.read()
    else:
        markdown = sys.stdin.read()

    html = generate_html(markdown, args.code, args.name)

    os.makedirs(os.path.dirname(args.output) or ".", exist_ok=True)
    with open(args.output, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"报告已生成: {args.output}")


if __name__ == "__main__":
    main()
