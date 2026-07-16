"""
뉴스 DB 접근 계층.
identifier.sqlite에서 기업명→종목코드 변환과 기사 검색을 담당한다.
(지금은 Python이 SQLite를 직접 조회. 나중에 Spring 소유로 이관 예정)
"""

import sqlite3
from pathlib import Path

# 프로젝트 루트의 DB 파일 경로 (ai/의 부모 폴더)
DB_PATH = Path(__file__).parent.parent / "identifier.sqlite"


def _connect() -> sqlite3.Connection:
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row   # 결과를 컬럼명으로 꺼낼 수 있게 (dict처럼)
    return con


def resolve_ticker(topic: str) -> str | None:
    """topic 안에 들어있는 기업명을 companies 테이블과 대조해 종목코드를 찾는다.
    예: "삼성전자 HBM 전망" → "005930". 못 찾으면 None."""
    con = _connect()
    rows = con.execute("SELECT ticker, corp_name FROM companies").fetchall()
    con.close()

    # corp_name이 긴 것부터 검사 (예: '삼성전자우'가 '삼성전자'보다 먼저 매칭되게)
    for row in sorted(rows, key=lambda r: len(r["corp_name"]), reverse=True):
        if row["corp_name"] in topic:
            return row["ticker"]
    return None


def search_news(ticker: str, keyword: str = "", limit: int = 5) -> list[dict]:
    """해당 종목의 최근 기사를 조회. keyword가 있으면 제목·본문에서 필터링.
    ? 자리표시자로 값을 바인딩 → SQL 인젝션 방지."""
    con = _connect()
    if keyword:
        rows = con.execute(
            "SELECT id, title, source, url, published_at FROM articles "
            "WHERE ticker = ? AND (title LIKE ? OR content LIKE ?) "
            "ORDER BY published_at DESC LIMIT ?",
            (ticker, f"%{keyword}%", f"%{keyword}%", limit), 
            # Where ticker = ticker AND (title like %{keyword}% OR content like %{keyword}%)
            # Order by published_at DESC Limit limit
        ).fetchall()
    else:
        rows = con.execute(
            "SELECT id, title, source, url, published_at FROM articles "
            "WHERE ticker = ? ORDER BY published_at DESC LIMIT ?",
            (ticker, limit),
        ).fetchall()
    con.close()
    return [dict(row) for row in rows]
