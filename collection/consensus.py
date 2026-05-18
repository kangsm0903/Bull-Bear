import argparse
import re
import sqlite3
import time
from datetime import datetime
from pathlib import Path

import requests
from bs4 import BeautifulSoup
from dotenv import load_dotenv


BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "identifier.sqlite"
NAVER_ITEM_URL = "https://finance.naver.com/item/main.naver"


load_dotenv(BASE_DIR / ".env")


HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Referer": "https://finance.naver.com/",
}


def parse_number(value, as_float=False):
    if value is None:
        return None

    text = str(value).strip().replace(",", "")
    text = re.sub(r"[^0-9.\-]", "", text)
    if not text:
        return None

    try:
        return float(text) if as_float else int(float(text))
    except ValueError:
        return None


def compact_text(element):
    if element is None:
        return ""
    return " ".join(element.get_text(" ", strip=True).split())


def ensure_schema():
    """consensus_snapshots 테이블 존재 여부 확인 (이미 init 단계에서 생성됨)"""
    pass


def get_target_companies(limit=None):
    query = """
        SELECT ticker, corp_code, corp_name
        FROM companies
        ORDER BY market_cap DESC
    """

    with sqlite3.connect(DB_PATH) as conn:
        rows = conn.execute(query).fetchall()

    unique_companies = []
    seen_keys = set()

    for ticker, corp_code, corp_name in rows:
        key = corp_code or ticker
        if key in seen_keys:
            continue

        seen_keys.add(key)
        unique_companies.append((ticker, corp_name))

        if limit and len(unique_companies) >= limit:
            break

    return unique_companies


def fetch_naver_item_page(ticker):
    response = requests.get(
        NAVER_ITEM_URL,
        params={"code": ticker},
        headers=HEADERS,
        timeout=20,
    )
    response.raise_for_status()
    return response.text


def parse_current_price(soup):
    blind = soup.select_one("dl.blind")
    blind_text = compact_text(blind)
    match = re.search(r"현재가\s+([0-9,]+)", blind_text)
    if match:
        return parse_number(match.group(1))

    today = soup.select_one("p.no_today")
    first_blind = today.select_one(".blind") if today else None
    if first_blind:
        return parse_number(first_blind.get_text(strip=True))

    return None


def parse_consensus_box(soup):
    table = soup.find("table", attrs={"summary": "투자의견 정보"})
    if table is None:
        table = soup.find("caption", string=lambda s: s and "투자의견" in s)
        table = table.find_parent("table") if table else None

    if table is None:
        return None

    rows = table.find_all("tr")
    if not rows:
        return None

    first_row = rows[0]
    header_text = compact_text(first_row.find("th"))
    if "투자의견" not in header_text or "목표주가" not in header_text:
        return None

    em_values = [em.get_text(strip=True) for em in first_row.find_all("em")]

    opinion_score = parse_number(em_values[0], as_float=True) if len(em_values) >= 1 else None
    target_price = parse_number(em_values[1]) if len(em_values) >= 2 else None

    row_text = compact_text(first_row)
    opinion_label = None
    label_match = re.search(r"([0-9.]+)\s*([가-힣A-Za-z]+)\s*l", row_text)
    if label_match:
        opinion_label = label_match.group(2)

    return {
        "option_score": opinion_score,
        "option_label": opinion_label,
        "target_price_avg": target_price,
    }


def parse_naver_consensus(ticker):
    html = fetch_naver_item_page(ticker)
    soup = BeautifulSoup(html, "html.parser")

    current_price = parse_current_price(soup)
    consensus = parse_consensus_box(soup)

    if not consensus or consensus["target_price_avg"] is None:
        return None

    target_price_avg = consensus["target_price_avg"]
    upside_pct = None
    if current_price:
        upside_pct = round(((target_price_avg - current_price) / current_price) * 100, 4)

    return {
        "target_price_avg": target_price_avg,
        "current_price": current_price,
        "upside_pct": upside_pct,
        "option_score": consensus["option_score"],
        "option_label": consensus["option_label"],
        "source": "naver_finance",
    }


def ingest_consensus_snapshots(as_of_date=None, limit=None, sleep_sec=0.3):
    ensure_schema()

    if as_of_date is None:
        as_of_date = datetime.today().strftime("%Y%m%d")

    companies = get_target_companies(limit=limit)
    if not companies:
        print("companies 테이블에 대상 기업이 없습니다.")
        return

    insert_query = """
        INSERT INTO consensus_snapshots (
            ticker, as_of_date,
            target_price_avg, current_price, upside_pct,
            option_score, option_label, source
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(ticker, as_of_date) DO UPDATE SET
            target_price_avg = excluded.target_price_avg,
            current_price = excluded.current_price,
            upside_pct = excluded.upside_pct,
            option_score = excluded.option_score,
            option_label = excluded.option_label,
            source = excluded.source
    """

    print(f"[{as_of_date}] consensus_snapshots 수집 시작...")
    print(f"대상 기업 수: {len(companies)}")

    success_count = 0
    empty_count = 0
    failed_count = 0

    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()

        for idx, (ticker, corp_name) in enumerate(companies, start=1):
            try:
                data = parse_naver_consensus(ticker)

                if data is None:
                    empty_count += 1
                    print(f"  [{idx}/{len(companies)}] {ticker} {corp_name}: 컨센서스 없음")
                    continue

                cursor.execute(
                    insert_query,
                    (
                        ticker,
                        as_of_date,
                        data["target_price_avg"],
                        data["current_price"],
                        data["upside_pct"],
                        data["option_score"],
                        data["option_label"],
                        data["source"],
                    ),
                )
                success_count += 1
                print(
                    f"  [{idx}/{len(companies)}] {ticker} {corp_name}: "
                    f"{data['option_score']} {data['option_label']} / "
                    f"목표가 {data['target_price_avg']} / 상승여력 {data['upside_pct']}%"
                )

            except Exception as e:
                failed_count += 1
                print(f"  [{idx}/{len(companies)}] {ticker} {corp_name}: 조회 실패 - {e}")

            time.sleep(sleep_sec)

        conn.commit()

    print(f"완료: 저장 {success_count}건, 컨센서스 없음 {empty_count}건, 실패 {failed_count}건")


def parse_args():
    parser = argparse.ArgumentParser(description="Naver 증권 컨센서스를 consensus_snapshots 테이블에 저장합니다.")
    parser.add_argument("--date", default=None, help="저장 기준일 YYYYMMDD. 기본값은 오늘")
    parser.add_argument("--limit", type=int, default=None, help="시가총액 상위 N개 기업만 테스트")
    parser.add_argument("--sleep", type=float, default=0.3, help="종목별 요청 간 대기 초")
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    ingest_consensus_snapshots(
        as_of_date=args.date,
        limit=args.limit,
        sleep_sec=args.sleep,
    )
