"""邮件发送工具 — Resend API（HTTPS，不受沙箱 SMTP 封锁影响）。

用法:
    python tools/send_email.py --subject "标题" --body "纯文本" --html /tmp/email.html --to anc3776@gmail.com --cc 1498964760@qq.com
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.request
import urllib.error

RESEND_API_KEY = os.environ.get("RESEND_API_KEY", "re_QpgMupGv_PfPHQX1BiCTfNLaPgurXoW8c")
SENDER = "stock-agent@tagwall.top"


def send(subject: str, body: str, html_file: str | None, to: list[str], cc: list[str] | None = None):
    html_content = ""
    if html_file and os.path.exists(html_file):
        with open(html_file, "r", encoding="utf-8") as f:
            html_content = f.read()

    payload = {
        "from": SENDER,
        "to": to,
        "subject": subject,
    }
    if cc:
        payload["cc"] = cc
    if html_content:
        payload["html"] = html_content
    if body:
        payload["text"] = body

    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        "https://api.resend.com/emails",
        data=data,
        headers={
            "Authorization": f"Bearer {RESEND_API_KEY}",
            "Content-Type": "application/json",
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            result = json.loads(resp.read().decode())
            print(f"邮件已发送: {subject} -> {', '.join(to)} (id: {result.get('id', 'unknown')})")
    except urllib.error.HTTPError as e:
        error_body = e.read().decode() if e.fp else str(e)
        print(f"发送失败 ({e.code}): {error_body}", file=sys.stderr)
        sys.exit(1)


def main():
    parser = argparse.ArgumentParser(description="Resend API 邮件发送")
    parser.add_argument("--subject", required=True, help="邮件主题")
    parser.add_argument("--body", default="", help="纯文本正文")
    parser.add_argument("--html", default=None, help="HTML 文件路径（作为富文本正文）")
    parser.add_argument("--to", required=True, nargs="+", help="收件人")
    parser.add_argument("--cc", nargs="+", default=None, help="抄送")
    args = parser.parse_args()

    send(args.subject, args.body, args.html, args.to, args.cc)


if __name__ == "__main__":
    main()
