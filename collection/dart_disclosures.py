# 기간 조정
# myenv/bin/python ingest_dart_disclosures.py --start 20260213 --end 20260513 

import argparse
import os
import sqlite3
import time
from datetime import datetime, timedelta
from pathlib import Path

import requests
from dotenv import load_dotenv


BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "identifier.sqlite"
DART_LIST_URL = "https://opendart.fss.or.kr/api/list.json"


load_dotenv(BASE_DIR / ".env")


def default_start_date():
    return (datetime.today() - timedelta(days=365)).strftime("%Y%m%d")


def default_end_date():
    return datetime.today().strftime("%Y%m%d")


def get_target_companies(limit=None):
    query = """
        SELECT ticker, corp_code, corp_name
        FROM companies
        WHERE corp_code IS NOT NULL
          AND corp_code != ''
        ORDER BY market_cap DESC
    """

    with sqlite3.connect(DB_PATH) as conn:
        rows = conn.execute(query).fetchall()

    unique_companies = []
    seen_corp_codes = set()

    for ticker, corp_code, corp_name in rows:
        if corp_code in seen_corp_codes:
            continue
        seen_corp_codes.add(corp_code)
        unique_companies.append((ticker, corp_code, corp_name))

        if limit and len(unique_companies) >= limit:
            break

    return unique_companies


def fetch_disclosures(api_key, corp_code, start_date, end_date, page_count=100):
    disclosures = []
    page_no = 1

    while True:
        response = requests.get(
            DART_LIST_URL,
            params={
                "crtfc_key": api_key,
                "corp_code": corp_code,
                "bgn_de": start_date,
                "end_de": end_date,
                "page_no": page_no,
                "page_count": page_count,
            },
            timeout=30,
        )
        response.raise_for_status()

        payload = response.json()
        status = payload.get("status")

        if status == "013":
            return disclosures

        if status != "000":
            raise RuntimeError(f"{payload.get('message')} (status={status})")

        disclosures.extend(payload.get("list", []))

        total_page = int(payload.get("total_page", 1))
        if page_no >= total_page:
            return disclosures

        page_no += 1


def ingest_dart_disclosures(start_date, end_date, limit=None, sleep_sec=0.1):
    api_key = os.environ.get("DART_API_KEY")
    if not api_key:
        raise RuntimeError("DART_API_KEY 환경 변수가 설정되지 않았습니다.")

    companies = get_target_companies(limit=limit)
    if not companies:
        print("corp_code가 있는 companies 행이 없습니다.")
        return

    insert_query = """
        INSERT INTO dart_disclosures (rcept_no, ticker, report_name, submitted_at)
        VALUES (?, ?, ?, ?)
        ON CONFLICT(rcept_no) DO UPDATE SET
            ticker = excluded.ticker,
            report_name = excluded.report_name,
            submitted_at = excluded.submitted_at
    """

    print(f"[{start_date}~{end_date}] dart_disclosures 수집 시작...")
    print(f"대상 기업 수: {len(companies)}")

    success_count = 0
    skipped_count = 0

    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()

        for idx, (ticker, corp_code, corp_name) in enumerate(companies, start=1):
            try:
                disclosures = fetch_disclosures(api_key, corp_code, start_date, end_date)

                for item in disclosures:
                    cursor.execute(
                        insert_query,
                        (
                            item.get("rcept_no"),
                            ticker,
                            item.get("report_nm"),
                            item.get("rcept_dt"),
                        ),
                    )
                    success_count += 1

                print(f"  [{idx}/{len(companies)}] {ticker} {corp_name}: {len(disclosures)}건")

            except Exception as e:
                skipped_count += 1
                print(f"  [{idx}/{len(companies)}] {ticker} {corp_name}: 조회 실패 - {e}")

            time.sleep(sleep_sec)

        conn.commit()

    print(f"완료: 공시 {success_count}건 저장, 실패 기업 {skipped_count}개")


def parse_args():
    parser = argparse.ArgumentParser(description="OpenDART 공시 목록을 dart_disclosures 테이블에 저장합니다.")
    parser.add_argument("--start", default=default_start_date(), help="조회 시작일 YYYYMMDD")
    parser.add_argument("--end", default=default_end_date(), help="조회 종료일 YYYYMMDD")
    parser.add_argument("--limit", type=int, default=None, help="시가총액 상위 N개 기업만 테스트")
    parser.add_argument("--sleep", type=float, default=0.1, help="기업별 API 호출 간 대기 초")
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    ingest_dart_disclosures(
        start_date=args.start,
        end_date=args.end,
        limit=args.limit,
        sleep_sec=args.sleep,
    )
