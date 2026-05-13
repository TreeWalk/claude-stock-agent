"""A股数据获取 CLI — 基于 AKShare，供 Claude Code 通过 Bash 调用。

用法:
    python tools/fetch.py stock-info 600519
    python tools/fetch.py indicators 600519
    python tools/fetch.py income 600519
    python tools/fetch.py balance 600519
    python tools/fetch.py cashflow 600519
    python tools/fetch.py price 600519 --days 60
    python tools/fetch.py dividends 600519
    python tools/fetch.py sector 白酒

网络选项:
    python tools/fetch.py --no-proxy stock-info 600519   # 禁用代理
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time

import akshare as ak
import pandas as pd


def _normalize_code(code: str) -> str:
    return code.strip().split(".")[0].zfill(6)


def _df_to_json(df: pd.DataFrame, limit: int | None = None) -> str:
    if df.empty:
        return json.dumps({"error": "未获取到数据"}, ensure_ascii=False)
    if limit:
        df = df.tail(limit)
    records = df.to_dict(orient="records")
    for r in records:
        for k, v in r.items():
            if pd.isna(v):
                r[k] = None
            elif hasattr(v, "isoformat"):
                r[k] = str(v)
    return json.dumps(records, ensure_ascii=False, default=str, indent=2)


def _sleep():
    time.sleep(0.5)


def stock_info(code: str) -> str:
    code = _normalize_code(code)
    df = ak.stock_individual_info_em(symbol=code)
    _sleep()
    info = {}
    for _, row in df.iterrows():
        info[str(row["item"])] = str(row["value"])
    return json.dumps(info, ensure_ascii=False, indent=2)


def financial_indicators(code: str, limit: int = 10) -> str:
    code = _normalize_code(code)
    try:
        df = ak.stock_a_indicator_lg(symbol=code)
    except AttributeError:
        df = ak.stock_zh_a_hist(
            symbol=code, period="daily",
            start_date=(pd.Timestamp.now() - pd.Timedelta(days=limit * 3)).strftime("%Y%m%d"),
            end_date=pd.Timestamp.now().strftime("%Y%m%d"),
            adjust="qfq",
        )
    _sleep()
    return _df_to_json(df, limit)


def financial_statements(code: str, report_type: str) -> str:
    code = _normalize_code(code)
    try:
        df = ak.stock_financial_report_sina(stock=code, symbol=report_type)
    except Exception:
        type_map = {"利润表": "yjbb", "资产负债表": "zcfz", "现金流量表": "xjll"}
        indicator = type_map.get(report_type, "yjbb")
        try:
            if report_type == "利润表":
                df = ak.stock_profit_sheet_by_report_em(symbol=code)
            elif report_type == "资产负债表":
                df = ak.stock_balance_sheet_by_report_em(symbol=code)
            elif report_type == "现金流量表":
                df = ak.stock_cash_flow_sheet_by_report_em(symbol=code)
            else:
                df = pd.DataFrame()
        except (AttributeError, Exception):
            df = pd.DataFrame()
    _sleep()
    if not df.empty:
        df = df.head(5)
    return _df_to_json(df)


def price_history(code: str, days: int = 60) -> str:
    code = _normalize_code(code)
    end_date = pd.Timestamp.now().strftime("%Y%m%d")
    start_date = (pd.Timestamp.now() - pd.Timedelta(days=days * 2)).strftime("%Y%m%d")
    df = ak.stock_zh_a_hist(
        symbol=code, period="daily",
        start_date=start_date, end_date=end_date, adjust="qfq",
    )
    _sleep()
    return _df_to_json(df, days)


def dividend_history(code: str) -> str:
    code = _normalize_code(code)
    try:
        df = ak.stock_history_dividend_detail(symbol=code, indicator="分红")
    except Exception:
        try:
            df = ak.stock_dividend_cninfo(symbol=code)
        except (AttributeError, Exception):
            df = pd.DataFrame()
    _sleep()
    return _df_to_json(df)


def sector_stocks(sector_name: str) -> str:
    df = ak.stock_board_industry_cons_em(symbol=sector_name)
    _sleep()
    if not df.empty:
        df = df.head(20)
    return _df_to_json(df)


def main():
    parser = argparse.ArgumentParser(description="A股数据获取工具")
    parser.add_argument("--no-proxy", action="store_true", help="禁用代理")
    sub = parser.add_subparsers(dest="command", required=True)

    p1 = sub.add_parser("stock-info", help="个股基本信息")
    p1.add_argument("code", help="6位股票代码")

    p2 = sub.add_parser("indicators", help="关键财务指标 (PE/PB/PS/股息率等)")
    p2.add_argument("code")
    p2.add_argument("--limit", type=int, default=10, help="最近N条记录")

    p3 = sub.add_parser("income", help="利润表")
    p3.add_argument("code")

    p4 = sub.add_parser("balance", help="资产负债表")
    p4.add_argument("code")

    p5 = sub.add_parser("cashflow", help="现金流量表")
    p5.add_argument("code")

    p6 = sub.add_parser("price", help="历史行情 (日K)")
    p6.add_argument("code")
    p6.add_argument("--days", type=int, default=60)

    p7 = sub.add_parser("dividends", help="历史分红记录")
    p7.add_argument("code")

    p8 = sub.add_parser("sector", help="行业板块成分股")
    p8.add_argument("name", help="板块名称，如 白酒、半导体")

    args = parser.parse_args()

    if args.no_proxy:
        for key in ["HTTP_PROXY", "HTTPS_PROXY", "http_proxy", "https_proxy"]:
            os.environ.pop(key, None)

    try:
        if args.command == "stock-info":
            result = stock_info(args.code)
        elif args.command == "indicators":
            result = financial_indicators(args.code, args.limit)
        elif args.command == "income":
            result = financial_statements(args.code, "利润表")
        elif args.command == "balance":
            result = financial_statements(args.code, "资产负债表")
        elif args.command == "cashflow":
            result = financial_statements(args.code, "现金流量表")
        elif args.command == "price":
            result = price_history(args.code, args.days)
        elif args.command == "dividends":
            result = dividend_history(args.code)
        elif args.command == "sector":
            result = sector_stocks(args.name)
        else:
            result = json.dumps({"error": f"未知命令: {args.command}"})

        print(result)
    except Exception as e:
        print(json.dumps({"error": str(e)}, ensure_ascii=False))
        sys.exit(1)


if __name__ == "__main__":
    main()
