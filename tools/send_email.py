"""Gmail SMTP 邮件发送工具 — 支持 HTML 正文直接发送。

用法:
    python tools/send_email.py --subject "标题" --body "纯文本" --html /tmp/email.html --to anc3776@gmail.com --cc 1498964760@qq.com
"""

from __future__ import annotations

import argparse
import os
import smtplib
import sys
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

SMTP_HOST = "smtp.gmail.com"
SMTP_PORT = 587
SENDER = "anc3776@gmail.com"
APP_PASSWORD = os.environ.get("GMAIL_APP_PASSWORD", "wiyc wyrr vsgi wotb")


def send(subject: str, body: str, html_file: str | None, to: list[str], cc: list[str] | None = None):
    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = SENDER
    msg["To"] = ", ".join(to)
    if cc:
        msg["Cc"] = ", ".join(cc)

    msg.attach(MIMEText(body, "plain", "utf-8"))

    if html_file and os.path.exists(html_file):
        with open(html_file, "r", encoding="utf-8") as f:
            html_content = f.read()
        msg.attach(MIMEText(html_content, "html", "utf-8"))

    recipients = list(to) + (cc or [])

    with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
        server.starttls()
        server.login(SENDER, APP_PASSWORD.replace(" ", ""))
        server.sendmail(SENDER, recipients, msg.as_string())

    print(f"邮件已发送: {subject} -> {', '.join(recipients)}")


def main():
    parser = argparse.ArgumentParser(description="Gmail SMTP 邮件发送")
    parser.add_argument("--subject", required=True, help="邮件主题")
    parser.add_argument("--body", default="", help="纯文本正文")
    parser.add_argument("--html", default=None, help="HTML 文件路径（作为富文本正文）")
    parser.add_argument("--to", required=True, nargs="+", help="收件人")
    parser.add_argument("--cc", nargs="+", default=None, help="抄送")
    args = parser.parse_args()

    try:
        send(args.subject, args.body, args.html, args.to, args.cc)
    except Exception as e:
        print(f"发送失败: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
