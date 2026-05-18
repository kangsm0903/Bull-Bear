"""
네이버 증권 뉴스 크롤러
- companies 테이블 기준 시가총액 상위 200개 종목
- 종목당 최대 50건 수집
- 기사 전문(content)을 DB에 저장

실행:
    python ingest_naver_news.py                  # 전체 200개 종목
    python ingest_naver_news.py --limit 10       # 종목당 10건
    python ingest_naver_news.py --start 000660   # 특정 ticker부터 재시작
    python ingest_naver_news.py --ticker 005930  # 단일 종목만
"""

import argparse
import hashlib
import re
import sqlite3
import time
from datetime import datetime
from pathlib import Path

import requests
from bs4 import BeautifulSoup

BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "identifier.sqlite"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Referer": "https://finance.naver.com/",
    "Accept-Language": "ko-KR,ko;q=0.9",
}

NEWS_LIST_URL = "https://finance.naver.com/item/news_news.naver"   # 실제 뉴스 목록 (iframe 내부)
NEWS_READ_URL = "https://finance.naver.com/item/news_read.naver"


# ── DB 스키마 마이그레이션 ────────────────────────────────
def ensure_schema():
    """summary → content 컬럼 이름 변경 + 인덱스 생성"""
    with sqlite3.connect(DB_PATH) as conn:
        cols = [row[1] for row in conn.execute("PRAGMA table_info(articles)").fetchall()]

        if "content" not in cols:
            if "summary" in cols:
                try:
                    conn.execute("ALTER TABLE articles RENAME COLUMN summary TO content")
                    print("✅ articles.summary → content 컬럼 이름 변경 완료")
                except Exception:
                    conn.execute("ALTER TABLE articles ADD COLUMN content TEXT")
                    print("✅ articles.content 컬럼 추가 완료")
            else:
                conn.execute("ALTER TABLE articles ADD COLUMN content TEXT")
                print("✅ articles.content 컬럼 추가 완료")

        # ticker + published_at 복합 인덱스 (검색 최적화)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_articles_ticker_date
            ON articles(ticker, published_at DESC)
        """)


# ── 종목 목록 ────────────────────────────────────────────
def get_target_tickers(limit: int = 200) -> list[tuple]:
    """companies 테이블에서 시가총액 상위 N개 (ticker, corp_name)"""
    with sqlite3.connect(DB_PATH) as conn:
        return conn.execute(
            "SELECT ticker, corp_name FROM companies ORDER BY market_cap DESC LIMIT ?",
            (limit,),
        ).fetchall()


# ── 뉴스 목록 파싱 ───────────────────────────────────────
def fetch_news_list(ticker: str, page: int) -> list[dict]:
    """네이버 증권 뉴스 목록 한 페이지 파싱 (약 20건)"""
    try:
        resp = requests.get(
            NEWS_LIST_URL,
            params={"code": ticker, "page": page},
            headers=HEADERS,
            timeout=15,
        )
        resp.encoding = "euc-kr"
        soup = BeautifulSoup(resp.text, "html.parser")
    except Exception as e:
        print(f"\n    목록 요청 실패 (page={page}): {e}")
        return []

    items = []
    table = soup.find("table", class_="type5")
    if not table:
        return []

    for tr in table.find_all("tr"):
        td_title = tr.find("td", class_="title")
        td_info  = tr.find("td", class_="info")
        td_date  = tr.find("td", class_="date")

        if not td_title or not td_date:
            continue

        a_tag = td_title.find("a")
        if not a_tag:
            continue

        href = a_tag.get("href", "")
        m_aid = re.search(r"article_id=(\d+)", href)
        m_oid = re.search(r"office_id=(\d+)", href)
        if not m_aid or not m_oid:
            continue

        article_id = m_aid.group(1)
        office_id  = m_oid.group(1)
        naver_url  = f"https://n.news.naver.com/mnews/article/{office_id}/{article_id}"

        items.append({
            "article_id":  article_id,
            "office_id":   office_id,
            "title":       a_tag.get_text(strip=True),
            "source":      td_info.get_text(strip=True) if td_info else "",
            "published_at": parse_date(td_date.get_text(strip=True)),
            "url":         naver_url,
        })

    return items


# ── 기사 전문 추출 ───────────────────────────────────────
def fetch_article_content(office_id: str, article_id: str) -> str:
    """
    네이버 뉴스 기사 본문 추출
    1차: n.news.naver.com/mnews/article/{oid}/{aid}
    2차: finance.naver.com/item/news_read.naver 에서 iframe URL 추적
    """
    url = f"https://n.news.naver.com/mnews/article/{office_id}/{article_id}"

    try:
        resp = requests.get(url, headers=HEADERS, timeout=15)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")

        # 본문 영역 우선순위별 탐색
        content_div = (
            soup.find("div", id="dic_area") or
            soup.find("div", id="articeBody") or
            soup.find("div", class_=re.compile(r"_article_content")) or
            soup.find("div", id="newsct_article") or
            soup.find("article")
        )

        if content_div:
            # 불필요 요소 제거
            for tag in content_div.find_all(["script", "style", "figure",
                                              "figcaption", "button", "a"]):
                tag.decompose()

            text = content_div.get_text(separator="\n", strip=True)
            text = re.sub(r"\n{3,}", "\n\n", text).strip()
            if len(text) > 50:
                return text

    except Exception:
        pass

    # 2차 시도: news_read 페이지에서 iframe URL 추적
    try:
        read_url = (
            f"{NEWS_READ_URL}?article_id={article_id}"
            f"&office_id={office_id}"
        )
        resp2 = requests.get(read_url, headers=HEADERS, timeout=15)
        resp2.encoding = "euc-kr"
        soup2 = BeautifulSoup(resp2.text, "html.parser")

        iframe = soup2.find("iframe", id="news_frame")
        if iframe:
            iframe_src = iframe.get("src", "")
            if iframe_src.startswith("http"):
                resp3 = requests.get(iframe_src, headers=HEADERS, timeout=15)
                soup3 = BeautifulSoup(resp3.text, "html.parser")
                body = soup3.find("div", id="dic_area") or soup3.find("article")
                if body:
                    return body.get_text(separator="\n", strip=True)[:3000]

    except Exception:
        pass

    return ""


# ── 날짜 파싱 ────────────────────────────────────────────
def parse_date(date_str: str) -> str:
    """
    '2026.05.14 09:30' 또는 '2026.05.14' → 'YYYY-MM-DD HH:MM:SS'
    '05.14 09:30' 형식도 처리 (연도 없을 때 현재 연도 사용)
    """
    date_str = date_str.strip()

    formats = [
        (r"\d{4}\.\d{2}\.\d{2} \d{2}:\d{2}", "%Y.%m.%d %H:%M"),
        (r"\d{4}\.\d{2}\.\d{2}",              "%Y.%m.%d"),
    ]
    for pattern, fmt in formats:
        if re.match(pattern, date_str):
            try:
                return datetime.strptime(date_str[:len(fmt)], fmt).strftime("%Y-%m-%d %H:%M:%S")
            except ValueError:
                pass

    # 월.일 시:분 (연도 없음)
    m = re.match(r"(\d{2})\.(\d{2}) (\d{2}):(\d{2})", date_str)
    if m:
        year = datetime.now().year
        return f"{year}-{m.group(1)}-{m.group(2)} {m.group(3)}:{m.group(4)}:00"

    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


# ── 고유 ID ──────────────────────────────────────────────
def make_article_id(url: str) -> str:
    return hashlib.md5(url.encode()).hexdigest()[:16]


# ── 종목별 크롤링 ────────────────────────────────────────
def ingest_ticker(conn: sqlite3.Connection, ticker: str, corp_name: str,
                  limit: int = 50) -> int:
    """한 종목의 뉴스를 최대 limit건 수집하여 DB 저장. 저장 건수 반환."""

    # 이미 limit건 이상 있으면 스킵
    existing = conn.execute(
        "SELECT COUNT(*) FROM articles WHERE ticker = ?", (ticker,)
    ).fetchone()[0]
    if existing >= limit:
        print(f"  ⏭️  이미 {existing}건 존재 — 스킵")
        return 0

    need = limit - existing

    insert_sql = """
        INSERT INTO articles (id, faiss_id, ticker, source, title, content, url, published_at)
        VALUES (?, NULL, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(id) DO NOTHING
    """

    saved = 0
    page  = 1

    while saved < need:
        items = fetch_news_list(ticker, page)
        if not items:
            break

        for item in items:
            if saved >= need:
                break

            uid = make_article_id(item["url"])

            # 중복 URL 체크
            dup = conn.execute(
                "SELECT 1 FROM articles WHERE id = ?", (uid,)
            ).fetchone()
            if dup:
                continue

            # 본문 수집
            content = fetch_article_content(item["office_id"], item["article_id"])
            time.sleep(0.3)

            try:
                conn.execute(insert_sql, (
                    uid, ticker,
                    item["source"], item["title"],
                    content, item["url"], item["published_at"],
                ))
                saved += 1
                print(
                    f"  [{existing + saved}/{limit}] "
                    f"{item['title'][:38]}",
                    end="\r",
                )
            except Exception as e:
                print(f"\n  저장 오류: {e}")

        page += 1
        time.sleep(0.5)

    conn.commit()
    print()  # 줄바꿈
    return saved


# ── 메인 ────────────────────────────────────────────────
def main(limit: int = 50, start_from: str = None, only_ticker: str = None):
    ensure_schema()

    if only_ticker:
        with sqlite3.connect(DB_PATH) as conn:
            corp = conn.execute(
                "SELECT corp_name FROM companies WHERE ticker = ?", (only_ticker,)
            ).fetchone()
        corp_name = corp[0] if corp else only_ticker
        tickers = [(only_ticker, corp_name)]
    else:
        tickers = get_target_tickers(200)
        if start_from:
            idx = next((i for i, (t, _) in enumerate(tickers) if t == start_from), 0)
            tickers = tickers[idx:]
            print(f"  → {start_from}부터 재시작 ({len(tickers)}개 남음)")

    print(f"대상 종목 수: {len(tickers)} | 종목당 최대 {limit}건\n")
    total = 0

    with sqlite3.connect(DB_PATH) as conn:
        for idx, (ticker, corp_name) in enumerate(tickers, 1):
            print(f"[{idx}/{len(tickers)}] {ticker} {corp_name}")
            count = ingest_ticker(conn, ticker, corp_name, limit)
            total += count
            print(f"  ✅ +{count}건 저장 (누적 {total}건)")
            time.sleep(1.0)

    print(f"\n🎉 완료: 총 {total}건 신규 저장")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="네이버 증권 뉴스 크롤러")
    parser.add_argument("--limit",  type=int, default=50,   help="종목당 최대 수집 건수 (기본 50)")
    parser.add_argument("--start",  default=None,            help="재시작할 ticker (예: 000660)")
    parser.add_argument("--ticker", default=None,            help="단일 종목 테스트 (예: 005930)")
    args = parser.parse_args()

    main(limit=args.limit, start_from=args.start, only_ticker=args.ticker)
