"""
정량 데이터 조회 — 크롤링 영향 없는 읽기 전용

financials + consensus_snapshots + quant_daily (최신 1행) 조합
"""

import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).resolve().parent.parent / "identifier.sqlite"

# 매크로 지표 표시 설정: indicator → (라벨, 값 포맷 함수)
MACRO_DISPLAY = {
    "usd_krw": ("원/달러 환율", lambda v: f"{v:,.1f}원"),
    "us_10y":  ("미국 10년물 금리", lambda v: f"{v:.2f}"),
    "wti":     ("WTI 유가", lambda v: f"${v:.1f}"),
    "kospi":   ("KOSPI", lambda v: f"{v:,.1f}p"),
    "kosdaq":  ("KOSDAQ", lambda v: f"{v:,.1f}p"),
    "sp500":   ("S&P500", lambda v: f"{v:,.1f}p"),
    "nasdaq":  ("나스닥", lambda v: f"{v:,.1f}p"),
}


def fetch_quant(ticker: str) -> dict | None:
    """
    ticker에 대한 정량 데이터를 하나의 dict로 반환.
    데이터가 없으면 None 반환.

    Returns:
        {
            "financials":  {"year": 2025, "quarter": 4, "revenue": ..., ...},
            "consensus":   {"target_price": ..., "label": ..., "upside_pct": ...},
            "price":       {"date": ..., "close": ..., "per": ..., "pbr": ..., ...},
        }
    """
    with sqlite3.connect(DB_PATH, timeout=10) as conn:
        conn.row_factory = sqlite3.Row

        fin = conn.execute("""
            SELECT year, quarter, revenue, op_profit, net_income,
                   op_margin, roe, debt_ratio
            FROM financials
            WHERE ticker = ?
            ORDER BY year DESC, quarter DESC
            LIMIT 1
        """, (ticker,)).fetchone()

        con = conn.execute("""
            SELECT target_price_avg, option_label, current_price, upside_pct
            FROM consensus_snapshots
            WHERE ticker = ?
            ORDER BY as_of_date DESC
            LIMIT 1
        """, (ticker,)).fetchone()

        price = conn.execute("""
            SELECT date, close, change_pct, per, pbr,
                   foreign_hold_pct, short_ratio
            FROM quant_daily
            WHERE ticker = ?
            ORDER BY date DESC
            LIMIT 1
        """, (ticker,)).fetchone()

        # 매크로 지표 (종목 무관, 시장 전체) — 가장 최근 날짜의 모든 지표
        macro_rows = conn.execute("""
            SELECT indicator, close, change_pct
            FROM macro_daily
            WHERE date = (SELECT MAX(date) FROM macro_daily)
        """).fetchall()

    if not fin and not con and not price and not macro_rows:
        return None

    result = {}
    if fin:
        result["financials"] = dict(fin)
    if con:
        result["consensus"] = dict(con)
    if price:
        result["price"] = dict(price)
    if macro_rows:
        result["macro"] = {
            r["indicator"]: {"close": r["close"], "change_pct": r["change_pct"]}
            for r in macro_rows
        }

    return result


def format_quant(quant: dict) -> str:
    """
    정량 데이터 dict → 프롬프트용 텍스트 변환
    """
    if not quant:
        return "  (정량 데이터 없음)"

    lines = []

    if "financials" in quant:
        f = quant["financials"]
        rev  = f.get("revenue",   0) or 0
        op   = f.get("op_profit", 0) or 0
        net  = f.get("net_income",0) or 0
        lines.append(f"[재무지표 {f.get('year','')}/{f.get('quarter','')}Q]")
        lines.append(f"  매출액:    {rev/1e12:.2f}조원")
        lines.append(f"  영업이익:  {op/1e12:.2f}조원  (영업이익률 {f.get('op_margin',0):.1f}%)")
        lines.append(f"  순이익:    {net/1e12:.2f}조원")
        lines.append(f"  ROE: {f.get('roe',0):.1f}%  |  부채비율: {f.get('debt_ratio',0):.1f}%")

    if "consensus" in quant:
        c = quant["consensus"]
        lines.append(f"\n[컨센서스]")
        lines.append(f"  투자의견:  {c.get('option_label','')}")
        lines.append(f"  현재가:    {c.get('current_price',0):,}원")
        lines.append(f"  목표주가:  {c.get('target_price_avg',0):,}원  (상승여력 {c.get('upside_pct',0):.1f}%)")

    if "price" in quant:
        p = quant["price"]
        lines.append(f"\n[주가/수급 ({p.get('date','')})]")
        lines.append(f"  종가:      {p.get('close',0):,}원  ({p.get('change_pct',0):+.2f}%)")
        lines.append(f"  PER: {p.get('per',0):.1f}배  |  PBR: {p.get('pbr',0):.2f}배")
        short = p.get("short_ratio", 0) or 0
        fgn   = p.get("foreign_hold_pct", 0) or 0
        if short:
            lines.append(f"  공매도비율: {short:.2f}%")
        if fgn:
            lines.append(f"  외국인보유: {fgn:.1f}%")

    if "macro" in quant:
        m = quant["macro"]
        lines.append(f"\n[매크로 지표 (시장 전체)]")
        for key, (label, fmt) in MACRO_DISPLAY.items():
            if key not in m:
                continue
            close = m[key].get("close")
            if close is None:
                continue
            chg = m[key].get("change_pct")
            chg_text = f"  ({chg:+.2f}%)" if chg is not None else ""
            lines.append(f"  {label}: {fmt(close)}{chg_text}")

    return "\n".join(lines)
