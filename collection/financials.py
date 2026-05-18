import argparse
import json
import os
import sqlite3
import time
from datetime import datetime
from pathlib import Path

import requests
from dotenv import load_dotenv


BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "identifier.sqlite"
DART_FINANCIALS_URL = "https://opendart.fss.or.kr/api/fnlttSinglAcnt.json"


load_dotenv(BASE_DIR / ".env")


REPORT_CODES = {
    1: "11013",  # 1분기보고서
    2: "11012",  # 반기보고서
    3: "11014",  # 3분기보고서
    4: "11011",  # 사업보고서
}


def parse_amount(value):
    if value in (None, "", "-"):
        return None

    text = str(value).strip().replace(",", "")

    if text.startswith("(") and text.endswith(")"):
        text = f"-{text[1:-1]}"

    try:
        return int(float(text))
    except ValueError:
        return None


def safe_ratio(numerator, denominator):
    if numerator is None or denominator in (None, 0):
        return None
    return round((numerator / denominator) * 100, 4)


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


def fetch_financial_accounts(api_key, corp_code, year, report_code):
    response = requests.get(
        DART_FINANCIALS_URL,
        params={
            "crtfc_key": api_key,
            "corp_code": corp_code,
            "bsns_year": str(year),
            "reprt_code": report_code,
        },
        timeout=30,
    )
    response.raise_for_status()

    payload = response.json()
    status = payload.get("status")

    if status == "013":
        return []

    if status != "000":
        raise RuntimeError(f"{payload.get('message')} (status={status})")

    return payload.get("list", [])


def prefer_consolidated(accounts):
    cfs = [row for row in accounts if row.get("fs_div") == "CFS"]
    if cfs:
        return "CFS", cfs

    ofs = [row for row in accounts if row.get("fs_div") == "OFS"]
    if ofs:
        return "OFS", ofs

    return None, []


def find_account_amount(accounts, names, statement_divs=None):
    for row in accounts:
        account_name = (row.get("account_nm") or "").replace(" ", "")
        statement_div = row.get("sj_div")

        if statement_divs and statement_div not in statement_divs:
            continue

        for name in names:
            if name.replace(" ", "") == account_name:
                return parse_amount(row.get("thstrm_amount"))

    for row in accounts:
        account_name = (row.get("account_nm") or "").replace(" ", "")
        statement_div = row.get("sj_div")

        if statement_divs and statement_div not in statement_divs:
            continue

        for name in names:
            if name.replace(" ", "") in account_name:
                return parse_amount(row.get("thstrm_amount"))

    return None


def extract_metrics(accounts):
    revenue = find_account_amount(
        accounts,
        ["매출액", "영업수익", "수익(매출액)", "이자수익", "보험수익", "Revenue"],
        statement_divs={"IS", "CIS"},
    )
    op_profit = find_account_amount(
        accounts,
        ["영업이익", "영업손실", "Operating income"],
        statement_divs={"IS", "CIS"},
    )
    net_income = find_account_amount(
        accounts,
        ["당기순이익", "당기순손실", "분기순이익", "반기순이익", "Profit"],
        statement_divs={"IS", "CIS"},
    )
    total_assets = find_account_amount(
        accounts,
        ["자산총계", "Total assets"],
        statement_divs={"BS"},
    )
    total_equity = find_account_amount(
        accounts,
        ["자본총계", "Total equity"],
        statement_divs={"BS"},
    )
    total_debt = find_account_amount(
        accounts,
        ["부채총계", "Total liabilities"],
        statement_divs={"BS"},
    )

    return {
        "revenue": revenue,
        "op_profit": op_profit,
        "net_income": net_income,
        "total_assets": total_assets,
        "total_equity": total_equity,
        "total_debt": total_debt,
        "op_margin": safe_ratio(op_profit, revenue),
        "debt_ratio": safe_ratio(total_debt, total_equity),
        "roe": safe_ratio(net_income, total_equity),
    }


def ingest_financials(year, quarters, limit=None, sleep_sec=0.2):
    api_key = os.environ.get("DART_API_KEY")
    if not api_key:
        raise RuntimeError("DART_API_KEY 환경 변수가 설정되지 않았습니다.")

    companies = get_target_companies(limit=limit)
    if not companies:
        print("corp_code가 있는 companies 행이 없습니다.")
        return

    insert_query = """
        INSERT INTO financials (
            ticker, year, quarter, fs_div,
            revenue, op_profit, net_income,
            total_assets, total_equity, total_debt,
            op_margin, debt_ratio, roe, statements_json
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(ticker, year, quarter, fs_div) DO UPDATE SET
            revenue = excluded.revenue,
            op_profit = excluded.op_profit,
            net_income = excluded.net_income,
            total_assets = excluded.total_assets,
            total_equity = excluded.total_equity,
            total_debt = excluded.total_debt,
            op_margin = excluded.op_margin,
            debt_ratio = excluded.debt_ratio,
            roe = excluded.roe,
            statements_json = excluded.statements_json
    """

    print(f"[{year}] financials 수집 시작...")
    print(f"대상 기업 수: {len(companies)}, 대상 분기: {quarters}")

    success_count = 0
    empty_count = 0
    failed_count = 0

    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()

        for idx, (ticker, corp_code, corp_name) in enumerate(companies, start=1):
            for quarter in quarters:
                report_code = REPORT_CODES[quarter]

                try:
                    accounts = fetch_financial_accounts(api_key, corp_code, year, report_code)
                    fs_div, preferred_accounts = prefer_consolidated(accounts)

                    if not preferred_accounts:
                        empty_count += 1
                        print(f"  [{idx}/{len(companies)}] {ticker} {corp_name} {year}Q{quarter}: 데이터 없음")
                        continue

                    metrics = extract_metrics(preferred_accounts)
                    cursor.execute(
                        insert_query,
                        (
                            ticker,
                            year,
                            quarter,
                            fs_div,
                            metrics["revenue"],
                            metrics["op_profit"],
                            metrics["net_income"],
                            metrics["total_assets"],
                            metrics["total_equity"],
                            metrics["total_debt"],
                            metrics["op_margin"],
                            metrics["debt_ratio"],
                            metrics["roe"],
                            json.dumps(preferred_accounts, ensure_ascii=False),
                        ),
                    )
                    success_count += 1
                    print(f"  [{idx}/{len(companies)}] {ticker} {corp_name} {year}Q{quarter}: 저장 완료({fs_div})")

                except Exception as e:
                    failed_count += 1
                    print(f"  [{idx}/{len(companies)}] {ticker} {corp_name} {year}Q{quarter}: 조회 실패 - {e}")

                time.sleep(sleep_sec)

        conn.commit()

    print(f"완료: 저장 {success_count}건, 데이터 없음 {empty_count}건, 실패 {failed_count}건")


def parse_quarters(value):
    if value.lower() == "all":
        return [1, 2, 3, 4]

    quarters = []
    for item in value.split(","):
        quarter = int(item.strip())
        if quarter not in REPORT_CODES:
            raise argparse.ArgumentTypeError("quarter는 1,2,3,4 또는 all이어야 합니다.")
        quarters.append(quarter)

    return quarters


def parse_args():
    parser = argparse.ArgumentParser(description="OpenDART 주요 재무계정을 financials 테이블에 저장합니다.")
    parser.add_argument("--year", type=int, default=datetime.today().year - 1, help="사업연도")
    parser.add_argument("--quarters", type=parse_quarters, default=[4], help="대상 분기: 1,2,3,4 또는 all")
    parser.add_argument("--limit", type=int, default=None, help="시가총액 상위 N개 기업만 테스트")
    parser.add_argument("--sleep", type=float, default=0.2, help="API 호출 간 대기 초")
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    ingest_financials(
        year=args.year,
        quarters=args.quarters,
        limit=args.limit,
        sleep_sec=args.sleep,
    )
