"""A股市场全局数据获取 CLI — 大盘指数、板块排名、资金流向、涨跌统计。

用法:
    python tools/market.py indices                  # 大盘主要指数
    python tools/market.py sector-ranking            # 行业板块涨跌排名
    python tools/market.py sector-flow               # 板块资金流向
    python tools/market.py northbound                # 北向资金 (沪深港通)
    python tools/market.py top-stocks gainers         # 涨幅榜 Top20
    python tools/market.py top-stocks losers          # 跌幅榜 Top20
    python tools/market.py top-stocks volume          # 成交额榜 Top20
    python tools/market.py limit-stats               # 涨跌停统计
    python tools/market.py stock-flow 600519          # 个股资金流向
    python tools/market.py concept-ranking            # 概念板块排名
    python tools/market.py macro                     # 最新宏观经济指标
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
from urllib.parse import quote

import requests
import pandas as pd

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
    "Referer": "https://finance.eastmoney.com/",
}

SESSION = requests.Session()
SESSION.headers.update(HEADERS)


def _req(url: str, timeout: int = 15, **kwargs) -> requests.Response:
    proxies = kwargs.pop("proxies", None)
    if proxies is None and os.environ.get("NO_PROXY_MARKET"):
        proxies = {"http": None, "https": None}
    return SESSION.get(url, timeout=timeout, proxies=proxies, **kwargs)


def _safe_float(v, default=0.0):
    try:
        return float(v)
    except (ValueError, TypeError):
        return default


# ---------------------------------------------------------------------------
# 1. 大盘指数
# ---------------------------------------------------------------------------

def get_indices() -> str:
    codes = "sh000001,sz399001,sz399006,sh000688,sh000300,sh000016,sh000905,sh000852,sz399303"
    names = {
        "000001": "上证指数", "399001": "深证成指", "399006": "创业板指",
        "000688": "科创50", "000300": "沪深300", "000016": "上证50",
        "000905": "中证500", "000852": "中证1000", "399303": "国证2000",
    }
    try:
        r = _req(f"https://qt.gtimg.cn/q={codes}")
        results = []
        for line in r.text.strip().split(";"):
            line = line.strip()
            if not line or "=" not in line:
                continue
            parts = line.split('"')[1].split("~") if '"' in line else []
            if len(parts) < 45:
                continue
            code = parts[2]
            results.append({
                "名称": names.get(code, parts[1]),
                "代码": code,
                "最新": _safe_float(parts[3]),
                "昨收": _safe_float(parts[4]),
                "涨跌额": _safe_float(parts[31]),
                "涨跌幅%": _safe_float(parts[32]),
                "最高": _safe_float(parts[33]),
                "最低": _safe_float(parts[34]),
                "成交额(亿)": round(_safe_float(parts[37]) / 10000, 2),
                "振幅%": _safe_float(parts[43]),
            })
        return json.dumps(results, ensure_ascii=False, indent=2)
    except Exception as e:
        return json.dumps({"error": f"获取指数失败: {e}"}, ensure_ascii=False)


# ---------------------------------------------------------------------------
# 2. 行业板块涨跌排名
# ---------------------------------------------------------------------------

def get_sector_ranking() -> str:
    url = (
        "https://push2.eastmoney.com/api/qt/clist/get?"
        "pn=1&pz=50&po=1&np=1&ut=bd1d9ddb04089700cf9c27f6f7426281"
        "&fltt=2&invt=2&fid=f3&fs=m:90+t:2+f:!50"
        "&fields=f2,f3,f4,f8,f12,f14,f20,f104,f105,f128,f140,f141"
    )
    try:
        r = _req(url)
        data = r.json()
        if data.get("data") is None:
            return json.dumps({"error": "板块数据为空"}, ensure_ascii=False)
        items = data["data"].get("diff", [])
        results = []
        for item in items:
            results.append({
                "板块名称": item.get("f14", ""),
                "板块代码": item.get("f12", ""),
                "涨跌幅%": item.get("f3"),
                "最新价": item.get("f2"),
                "涨跌额": item.get("f4"),
                "换手率%": item.get("f8"),
                "总市值(亿)": round(item.get("f20", 0) / 100000000, 2) if item.get("f20") else 0,
                "上涨家数": item.get("f104"),
                "下跌家数": item.get("f105"),
            })
        return json.dumps(results, ensure_ascii=False, indent=2)
    except Exception as e:
        return _fallback_sector_ranking(e)


def _fallback_sector_ranking(orig_error) -> str:
    try:
        import akshare as ak
        df = ak.stock_board_industry_name_em()
        if df.empty:
            raise ValueError("空数据")
        cols_map = {}
        for col in df.columns:
            if "涨跌" in col and "幅" in col:
                cols_map["涨跌幅%"] = col
            elif "板块名称" in col or "名称" in col:
                cols_map["板块名称"] = col
            elif "板块代码" in col or "代码" in col:
                cols_map["板块代码"] = col
        records = df.head(40).to_dict(orient="records")
        return json.dumps(records, ensure_ascii=False, default=str, indent=2)
    except Exception:
        return json.dumps({"error": f"板块排名获取失败: {orig_error}"}, ensure_ascii=False)


# ---------------------------------------------------------------------------
# 3. 板块资金流向
# ---------------------------------------------------------------------------

def get_sector_flow() -> str:
    url = (
        "https://push2.eastmoney.com/api/qt/clist/get?"
        "pn=1&pz=30&po=1&np=1&ut=bd1d9ddb04089700cf9c27f6f7426281"
        "&fltt=2&invt=2&fid=f62&fs=m:90+t:2+f:!50"
        "&fields=f12,f14,f2,f3,f62,f184,f66,f69,f72,f75,f78,f81,f84,f87"
    )
    try:
        r = _req(url)
        data = r.json()
        if data.get("data") is None:
            return json.dumps({"error": "资金流向数据为空"}, ensure_ascii=False)
        items = data["data"].get("diff", [])
        results = []
        for item in items:
            results.append({
                "板块名称": item.get("f14", ""),
                "涨跌幅%": item.get("f3"),
                "主力净流入(万)": round(item.get("f62", 0) / 10000, 2) if item.get("f62") else 0,
                "主力净流入占比%": item.get("f184"),
                "超大单净流入(万)": round(item.get("f66", 0) / 10000, 2) if item.get("f66") else 0,
                "大单净流入(万)": round(item.get("f72", 0) / 10000, 2) if item.get("f72") else 0,
                "中单净流入(万)": round(item.get("f78", 0) / 10000, 2) if item.get("f78") else 0,
                "小单净流入(万)": round(item.get("f84", 0) / 10000, 2) if item.get("f84") else 0,
            })
        return json.dumps(results, ensure_ascii=False, indent=2)
    except Exception as e:
        return json.dumps({"error": f"板块资金流向获取失败: {e}"}, ensure_ascii=False)


# ---------------------------------------------------------------------------
# 4. 北向资金 (沪深港通)
# ---------------------------------------------------------------------------

def get_northbound() -> str:
    url = (
        "https://push2his.eastmoney.com/api/qt/kamt.kline/get?"
        "fields1=f1,f3,f5&fields2=f51,f52,f53,f54,f55,f56"
        "&klt=101&lmt=10&ut=b955304f3a4e458ba18e36e1e5c5c07e"
    )
    try:
        r = _req(url)
        data = r.json()
        if data.get("data") is None:
            raise ValueError("空数据")
        s2n = data["data"].get("s2n", [])
        result = {"北向资金(近10日)": []}
        for item in s2n:
            fields = item.split(",")
            if len(fields) >= 4:
                result["北向资金(近10日)"].append({
                    "日期": fields[0],
                    "沪股通净流入(亿)": round(_safe_float(fields[1]) / 10000, 2) if fields[1] != "-" else None,
                    "深股通净流入(亿)": round(_safe_float(fields[2]) / 10000, 2) if fields[2] != "-" else None,
                    "北向合计净流入(亿)": round(_safe_float(fields[3]) / 10000, 2) if fields[3] != "-" else None,
                })
        return json.dumps(result, ensure_ascii=False, indent=2)
    except Exception as e:
        return json.dumps({"error": f"北向资金获取失败: {e}"}, ensure_ascii=False)


# ---------------------------------------------------------------------------
# 5. 涨幅榜 / 跌幅榜 / 成交额榜
# ---------------------------------------------------------------------------

def get_top_stocks(rank_type: str = "gainers", limit: int = 20) -> str:
    fid_map = {"gainers": "f3", "losers": "f3", "volume": "f6"}
    po_map = {"gainers": "1", "losers": "0", "volume": "1"}
    fid = fid_map.get(rank_type, "f3")
    po = po_map.get(rank_type, "1")
    url = (
        f"https://push2.eastmoney.com/api/qt/clist/get?"
        f"pn=1&pz={limit}&po={po}&np=1&ut=bd1d9ddb04089700cf9c27f6f7426281"
        f"&fltt=2&invt=2&fid={fid}&fs=m:0+t:6,m:0+t:80,m:1+t:2,m:1+t:23,m:0+t:81+s:2048"
        f"&fields=f2,f3,f4,f5,f6,f7,f8,f9,f10,f12,f14,f15,f16,f17,f18,f20,f21"
    )
    try:
        r = _req(url)
        data = r.json()
        if data.get("data") is None:
            return json.dumps({"error": "排行数据为空"}, ensure_ascii=False)
        items = data["data"].get("diff", [])
        results = []
        for item in items:
            results.append({
                "名称": item.get("f14", ""),
                "代码": item.get("f12", ""),
                "最新价": item.get("f2"),
                "涨跌幅%": item.get("f3"),
                "涨跌额": item.get("f4"),
                "成交量(手)": item.get("f5"),
                "成交额(万)": round(item.get("f6", 0) / 10000, 2) if item.get("f6") else 0,
                "振幅%": item.get("f7"),
                "换手率%": item.get("f8"),
                "PE(TTM)": item.get("f9"),
                "量比": item.get("f10"),
                "最高": item.get("f15"),
                "最低": item.get("f16"),
                "今开": item.get("f17"),
                "昨收": item.get("f18"),
                "总市值(亿)": round(item.get("f20", 0) / 100000000, 2) if item.get("f20") else 0,
            })
        return json.dumps(results, ensure_ascii=False, indent=2)
    except Exception as e:
        return json.dumps({"error": f"排行榜获取失败: {e}"}, ensure_ascii=False)


# ---------------------------------------------------------------------------
# 6. 涨跌停统计
# ---------------------------------------------------------------------------

def get_limit_stats() -> str:
    try:
        import akshare as ak
        df_up = ak.stock_zt_pool_em(date=pd.Timestamp.now().strftime("%Y%m%d"))
        df_down = ak.stock_zt_pool_dtgc_em(date=pd.Timestamp.now().strftime("%Y%m%d"))
        time.sleep(0.5)
        result = {
            "涨停数量": len(df_up) if not df_up.empty else 0,
            "跌停数量": len(df_down) if not df_down.empty else 0,
        }
        if not df_up.empty:
            up_records = df_up.head(20).to_dict(orient="records")
            for r in up_records:
                for k, v in r.items():
                    if pd.isna(v):
                        r[k] = None
                    elif hasattr(v, "isoformat"):
                        r[k] = str(v)
            result["涨停个股"] = up_records
        return json.dumps(result, ensure_ascii=False, default=str, indent=2)
    except Exception as e:
        return _fallback_limit_stats(e)


def _fallback_limit_stats(orig_error) -> str:
    url = (
        "https://push2ex.eastmoney.com/getTopicZTPool?"
        "ut=7eea3edcaed734bea9cbfc24409ed989"
        f"&date={pd.Timestamp.now().strftime('%Y%m%d')}"
        "&Ession=runQry"
    )
    try:
        r = _req(url)
        data = r.json()
        pool = data.get("data", {}).get("pool", [])
        result = {
            "涨停数量": len(pool),
            "涨停个股": [],
        }
        for item in pool[:20]:
            result["涨停个股"].append({
                "代码": item.get("c"),
                "名称": item.get("n"),
                "最新价": item.get("p") / 1000 if item.get("p") else 0,
                "涨停原因": item.get("hybk", ""),
                "封单额(万)": round(item.get("fund", 0) / 10000, 2),
                "连板数": item.get("days", 1),
            })
        return json.dumps(result, ensure_ascii=False, indent=2)
    except Exception as e2:
        return json.dumps({"error": f"涨跌停数据获取失败: {orig_error} / {e2}"}, ensure_ascii=False)


# ---------------------------------------------------------------------------
# 7. 个股资金流向
# ---------------------------------------------------------------------------

def get_stock_flow(code: str) -> str:
    code = code.strip().split(".")[0].zfill(6)
    secid = f"1.{code}" if code.startswith(("6", "5")) else f"0.{code}"
    url = (
        f"https://push2his.eastmoney.com/api/qt/stock/fflow/kline/get?"
        f"secid={secid}&lmt=10&klt=101"
        f"&fields1=f1,f2,f3,f7&fields2=f51,f52,f53,f54,f55,f56,f57"
        f"&ut=b955304f3a4e458ba18e36e1e5c5c07e"
    )
    try:
        r = _req(url)
        data = r.json()
        if data.get("data") is None:
            return json.dumps({"error": f"个股{code}资金流向数据为空"}, ensure_ascii=False)
        klines = data["data"].get("klines", [])
        results = []
        for line in klines:
            fields = line.split(",")
            if len(fields) >= 7:
                results.append({
                    "日期": fields[0],
                    "主力净流入(万)": round(_safe_float(fields[1]) / 10000, 2),
                    "小单净流入(万)": round(_safe_float(fields[2]) / 10000, 2),
                    "中单净流入(万)": round(_safe_float(fields[3]) / 10000, 2),
                    "大单净流入(万)": round(_safe_float(fields[4]) / 10000, 2),
                    "超大单净流入(万)": round(_safe_float(fields[5]) / 10000, 2),
                })
        return json.dumps(results, ensure_ascii=False, indent=2)
    except Exception as e:
        return json.dumps({"error": f"个股资金流向获取失败: {e}"}, ensure_ascii=False)


# ---------------------------------------------------------------------------
# 8. 概念板块排名
# ---------------------------------------------------------------------------

def get_concept_ranking() -> str:
    url = (
        "https://push2.eastmoney.com/api/qt/clist/get?"
        "pn=1&pz=40&po=1&np=1&ut=bd1d9ddb04089700cf9c27f6f7426281"
        "&fltt=2&invt=2&fid=f3&fs=m:90+t:3+f:!50"
        "&fields=f2,f3,f4,f8,f12,f14,f20,f104,f105"
    )
    try:
        r = _req(url)
        data = r.json()
        if data.get("data") is None:
            return json.dumps({"error": "概念板块数据为空"}, ensure_ascii=False)
        items = data["data"].get("diff", [])
        results = []
        for item in items:
            results.append({
                "概念名称": item.get("f14", ""),
                "涨跌幅%": item.get("f3"),
                "换手率%": item.get("f8"),
                "上涨家数": item.get("f104"),
                "下跌家数": item.get("f105"),
                "总市值(亿)": round(item.get("f20", 0) / 100000000, 2) if item.get("f20") else 0,
            })
        return json.dumps(results, ensure_ascii=False, indent=2)
    except Exception as e:
        return json.dumps({"error": f"概念板块获取失败: {e}"}, ensure_ascii=False)


# ---------------------------------------------------------------------------
# 9. 宏观经济指标
# ---------------------------------------------------------------------------

def get_macro_data() -> str:
    result = {}

    try:
        import akshare as ak
        try:
            df = ak.macro_china_pmi()
            if not df.empty:
                latest = df.tail(3).to_dict(orient="records")
                for r in latest:
                    for k, v in r.items():
                        if pd.isna(v):
                            r[k] = None
                        elif hasattr(v, "isoformat"):
                            r[k] = str(v)
                result["PMI(制造业)"] = latest
        except Exception:
            pass
        time.sleep(0.3)

        try:
            df = ak.macro_china_cpi_monthly()
            if not df.empty:
                latest = df.tail(3).to_dict(orient="records")
                for r in latest:
                    for k, v in r.items():
                        if pd.isna(v):
                            r[k] = None
                        elif hasattr(v, "isoformat"):
                            r[k] = str(v)
                result["CPI(月度)"] = latest
        except Exception:
            pass
        time.sleep(0.3)

        try:
            df = ak.macro_china_gdp()
            if not df.empty:
                latest = df.tail(4).to_dict(orient="records")
                for r in latest:
                    for k, v in r.items():
                        if pd.isna(v):
                            r[k] = None
                        elif hasattr(v, "isoformat"):
                            r[k] = str(v)
                result["GDP"] = latest
        except Exception:
            pass

    except ImportError:
        result["error"] = "需要安装 akshare: pip install akshare"

    if not result:
        result["error"] = "宏观数据获取失败，请检查网络连接"

    return json.dumps(result, ensure_ascii=False, default=str, indent=2)


# ---------------------------------------------------------------------------
# 10. 个股资金流向排行 (当日主力净流入/流出 Top N)
# ---------------------------------------------------------------------------

def get_stock_flow_rank(direction: str = "inflow", limit: int = 20) -> str:
    po = "1" if direction == "inflow" else "0"
    url = (
        f"https://push2.eastmoney.com/api/qt/clist/get?"
        f"pn=1&pz={limit}&po={po}&np=1&ut=bd1d9ddb04089700cf9c27f6f7426281"
        f"&fltt=2&invt=2&fid=f62&fs=m:0+t:6,m:0+t:80,m:1+t:2,m:1+t:23,m:0+t:81+s:2048"
        f"&fields=f12,f14,f2,f3,f62,f184,f66,f69,f72,f75,f78,f81,f84,f87"
    )
    try:
        r = _req(url)
        data = r.json()
        if data.get("data") is None:
            raise ValueError("数据为空")
        items = data["data"].get("diff", [])
        results = []
        for item in items:
            results.append({
                "名称": item.get("f14", ""),
                "代码": item.get("f12", ""),
                "最新价": item.get("f2"),
                "涨跌幅%": item.get("f3"),
                "主力净流入(万)": round(item.get("f62", 0) / 10000, 2) if item.get("f62") else 0,
                "主力净流入占比%": item.get("f184"),
                "超大单净流入(万)": round(item.get("f66", 0) / 10000, 2) if item.get("f66") else 0,
                "大单净流入(万)": round(item.get("f72", 0) / 10000, 2) if item.get("f72") else 0,
                "中单净流入(万)": round(item.get("f78", 0) / 10000, 2) if item.get("f78") else 0,
                "小单净流入(万)": round(item.get("f84", 0) / 10000, 2) if item.get("f84") else 0,
            })
        label = "净流入" if direction == "inflow" else "净流出"
        return json.dumps({"类型": f"个股主力{label}Top{limit}", "数据": results}, ensure_ascii=False, indent=2)
    except Exception as e:
        return json.dumps({"error": f"个股资金流向排行获取失败(push2不可用): {e}，请改用 WebSearch 搜索「今日A股 主力资金净流入 个股排名」获取数据"}, ensure_ascii=False)


# ---------------------------------------------------------------------------
# 10b. 板块资金流向 (datacenter-web 备用)
# ---------------------------------------------------------------------------

def get_sector_flow_dc() -> str:
    plates = [
        ("沪深两市", "沪深两市"), ("沪深300", "沪深300"), ("上证50", "上证50"),
        ("创业板指", "创业板指"), ("科创50", "科创板"),
    ]
    results = []
    for label, plate in plates:
        from urllib.parse import quote
        url = (
            f"https://datacenter-web.eastmoney.com/api/data/v1/get?"
            f"reportName=RPT_MARKET_CAPITALFLOW&columns=ALL"
            f"&pageSize=1&sortColumns=TRADE_DATE&sortTypes=-1&pageNumber=1"
            f"&filter=(BONDTYPE=%22A%E8%82%A1%22)(PLATE=%22{quote(plate)}%22)"
        )
        try:
            r = _req(url)
            data = r.json()
            if data.get("success") and data["result"]["data"]:
                d = data["result"]["data"][0]
                results.append({
                    "板块": label,
                    "日期": str(d.get("TRADE_DATE", ""))[:10],
                    "涨家数": d.get("INNUM"),
                    "跌家数": d.get("OUTNUM"),
                    "主力净流入(万)": round(_safe_float(d.get("NET_INFLOW")), 2),
                    "超大单净流入(万)": round(_safe_float(d.get("SUPERDEAL_NET", 0)), 2),
                    "大单净流入(万)": round(_safe_float(d.get("BIGDEAL_NET", 0)), 2),
                    "主力流入(万)": round(_safe_float(d.get("MAIN_INFLOW")), 2),
                    "主力流出(万)": round(_safe_float(d.get("MAIN_OUTFLOW")), 2),
                })
        except Exception:
            pass
    if results:
        return json.dumps(results, ensure_ascii=False, indent=2)
    return json.dumps({"error": "板块资金分层数据获取失败"}, ensure_ascii=False)


# ---------------------------------------------------------------------------
# 11. 大盘资金流向 (整体市场)
# ---------------------------------------------------------------------------

def get_market_flow() -> str:
    url = (
        "https://datacenter-web.eastmoney.com/api/data/v1/get?"
        "reportName=RPT_MARKET_CAPITALFLOW&columns=ALL"
        "&pageSize=10&sortColumns=TRADE_DATE&sortTypes=-1&pageNumber=1"
        "&filter=(BONDTYPE=%22A%E8%82%A1%22)(PLATE=%22%E6%B2%AA%E6%B7%B1%E4%B8%A4%E5%B8%82%22)"
    )
    try:
        r = _req(url)
        data = r.json()
        if not data.get("success") or not data.get("result") or not data["result"].get("data"):
            return json.dumps({"error": "大盘资金流向数据为空"}, ensure_ascii=False)
        items = data["result"]["data"]
        results = []
        for item in items:
            results.append({
                "日期": str(item.get("TRADE_DATE", ""))[:10],
                "上涨家数": item.get("INNUM"),
                "下跌家数": item.get("OUTNUM"),
                "主力净流入(万)": round(_safe_float(item.get("NET_INFLOW")), 2),
                "超大单净流入(万)": round(_safe_float(item.get("SUPERDEAL_NET", 0)), 2),
                "大单净流入(万)": round(_safe_float(item.get("BIGDEAL_NET", 0)), 2),
                "中单净流入(万)": round(_safe_float(item.get("MIDDEAL_NET", 0)), 2),
                "小单净流入(万)": round(_safe_float(item.get("SMALLDEAL_NET", 0)), 2),
                "主力流入(万)": round(_safe_float(item.get("MAIN_INFLOW")), 2),
                "主力流出(万)": round(_safe_float(item.get("MAIN_OUTFLOW")), 2),
            })
        return json.dumps(results, ensure_ascii=False, indent=2)
    except Exception as e:
        return json.dumps({"error": f"大盘资金流向获取失败: {e}"}, ensure_ascii=False)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="A股市场全局数据获取工具")
    parser.add_argument("--no-proxy", action="store_true", help="禁用代理")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("indices", help="大盘主要指数")
    sub.add_parser("sector-ranking", help="行业板块涨跌排名")
    sub.add_parser("sector-flow", help="板块资金流向 Top30")
    sub.add_parser("northbound", help="北向资金 (沪深港通)")
    sub.add_parser("market-flow", help="大盘资金流向 (近10日)")

    p_top = sub.add_parser("top-stocks", help="涨幅/跌幅/成交额排行")
    p_top.add_argument("type", choices=["gainers", "losers", "volume"], help="排行类型")
    p_top.add_argument("--limit", type=int, default=20)

    sub.add_parser("limit-stats", help="涨跌停统计")

    p_flow = sub.add_parser("stock-flow", help="个股资金流向")
    p_flow.add_argument("code", help="6位股票代码")

    p_sfr = sub.add_parser("stock-flow-rank", help="个股资金流向排行")
    p_sfr.add_argument("direction", choices=["inflow", "outflow"], help="inflow=净流入榜 outflow=净流出榜")
    p_sfr.add_argument("--limit", type=int, default=20)

    sub.add_parser("sector-flow-dc", help="板块资金分层流向 (沪深两市/300/50/创业板/科创)")
    sub.add_parser("concept-ranking", help="概念板块涨跌排名")
    sub.add_parser("macro", help="宏观经济指标 (PMI/CPI/GDP)")

    args = parser.parse_args()

    if args.no_proxy:
        for key in ["HTTP_PROXY", "HTTPS_PROXY", "http_proxy", "https_proxy"]:
            os.environ.pop(key, None)
        os.environ["NO_PROXY_MARKET"] = "1"

    try:
        if args.command == "indices":
            result = get_indices()
        elif args.command == "sector-ranking":
            result = get_sector_ranking()
        elif args.command == "sector-flow":
            result = get_sector_flow()
        elif args.command == "northbound":
            result = get_northbound()
        elif args.command == "market-flow":
            result = get_market_flow()
        elif args.command == "top-stocks":
            result = get_top_stocks(args.type, args.limit)
        elif args.command == "limit-stats":
            result = get_limit_stats()
        elif args.command == "stock-flow":
            result = get_stock_flow(args.code)
        elif args.command == "stock-flow-rank":
            result = get_stock_flow_rank(args.direction, args.limit)
        elif args.command == "sector-flow-dc":
            result = get_sector_flow_dc()
        elif args.command == "concept-ranking":
            result = get_concept_ranking()
        elif args.command == "macro":
            result = get_macro_data()
        else:
            result = json.dumps({"error": f"未知命令: {args.command}"})

        print(result)
    except Exception as e:
        print(json.dumps({"error": str(e)}, ensure_ascii=False))
        sys.exit(1)


if __name__ == "__main__":
    main()
