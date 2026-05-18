"""
FAISS 검색 → SQLite 메타데이터 조회

사용 예:
    from rag.retriever import search
    results = search("삼성전자 반도체 수익성", source="articles", top_k=5)
"""

import sqlite3
from pathlib import Path

import faiss
import numpy as np

from rag.embedder import embed_query

BASE_DIR = Path(__file__).resolve().parent.parent
DB_PATH = BASE_DIR / "identifier.sqlite"
FAISS_DIR = Path(__file__).resolve().parent / "faiss_store"

# 인덱스 캐시 (한 번 로드 후 메모리 유지)
_indexes: dict[str, faiss.Index] = {}

# 회사명 → ticker 매핑 캐시
_corp_map: dict[str, str] = {}


def _get_corp_map() -> dict[str, str]:
    """DB에서 회사명 → ticker 매핑 로드 (캐시)"""
    global _corp_map
    if not _corp_map:
        with sqlite3.connect(DB_PATH) as conn:
            rows = conn.execute("SELECT corp_name, ticker FROM companies").fetchall()
        _corp_map = {name: ticker for name, ticker in rows}
    return _corp_map


def _detect_ticker(query: str) -> str | None:
    """쿼리에서 회사명을 감지해 ticker 반환. 못 찾으면 None."""
    corp_map = _get_corp_map()
    for corp_name, ticker in corp_map.items():
        if corp_name in query:
            return ticker
    return None


def _load_index(source: str) -> faiss.Index:
    if source not in _indexes:
        index_path = FAISS_DIR / f"{source}.index"
        if not index_path.exists():
            raise FileNotFoundError(
                f"{index_path} 없음. 먼저 index_builder.py를 실행하세요."
            )
        _indexes[source] = faiss.read_index(str(index_path))
    return _indexes[source]


def _fetch_articles(faiss_ids: list[int]) -> list[dict]:
    placeholders = ",".join("?" * len(faiss_ids))
    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(f"""
            SELECT a.faiss_id, a.ticker, c.corp_name,
                   a.title, a.content, a.source, a.published_at, a.url
            FROM articles a
            JOIN companies c ON a.ticker = c.ticker
            WHERE a.faiss_id IN ({placeholders})
        """, faiss_ids).fetchall()

    # FAISS 반환 순서(유사도 순) 보존
    id_to_row = {row["faiss_id"]: dict(row) for row in rows}
    return [id_to_row[fid] for fid in faiss_ids if fid in id_to_row]


def _fetch_dart(faiss_ids: list[int]) -> list[dict]:
    placeholders = ",".join("?" * len(faiss_ids))
    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(f"""
            SELECT d.faiss_id, d.ticker, c.corp_name,
                   d.report_name, d.submitted_at, d.rcept_no
            FROM dart_disclosures d
            JOIN companies c ON d.ticker = c.ticker
            WHERE d.faiss_id IN ({placeholders})
        """, faiss_ids).fetchall()

    id_to_row = {row["faiss_id"]: dict(row) for row in rows}
    return [id_to_row[fid] for fid in faiss_ids if fid in id_to_row]


def search(
    query: str,
    source: str = "articles",  # "articles" | "dart"
    top_k: int = 5,
    ticker: str = None,         # 특정 종목만 필터링 (선택)
    auto_detect: bool = True,   # 쿼리에서 회사명 자동 감지해 ticker 부스팅
) -> list[dict]:
    """
    query를 임베딩해 FAISS로 유사 문서를 검색하고 SQLite 메타데이터를 반환

    Args:
        query: 검색 쿼리 (자연어)
        source: "articles" 또는 "dart"
        top_k: 반환할 결과 수 (ticker 필터 시 여유있게 크게 설정)
        ticker: 특정 종목 코드로 필터링 (예: "005930")
        auto_detect: True이면 쿼리에서 회사명 자동 감지 → 해당 종목 결과 우선 정렬

    Returns:
        유사도 순으로 정렬된 문서 메타데이터 리스트
    """
    index = _load_index(source)

    # 쿼리 임베딩 → 정규화
    query_vec = np.array([embed_query(query)], dtype="float32")
    faiss.normalize_L2(query_vec)

    # ticker 필터 또는 자동 감지 시 여유있게 검색 후 필터
    detected_for_boost = _detect_ticker(query) if (auto_detect and not ticker) else None
    search_k = top_k * 10 if (ticker or detected_for_boost) else top_k
    scores, faiss_ids = index.search(query_vec, search_k)

    valid_ids = [int(fid) for fid in faiss_ids[0] if fid >= 0]

    # SQLite에서 메타데이터 조회
    if source == "articles":
        results = _fetch_articles(valid_ids)
    else:
        results = _fetch_dart(valid_ids)

    # 유사도 점수 추가
    score_map = {int(fid): float(score) for fid, score in zip(faiss_ids[0], scores[0])}
    for r in results:
        r["score"] = score_map.get(r["faiss_id"], 0.0)

    # ticker 필터링 (FAISS는 메타데이터 필터 미지원 → 검색 후 처리)
    if ticker:
        results = [r for r in results if r.get("ticker") == ticker]

    # 회사명 자동 감지 → 해당 종목 결과를 상위로 부스팅
    elif auto_detect and detected_for_boost:
        detected = detected_for_boost
        if detected:
            matched = [r for r in results if r.get("ticker") == detected]
            others  = [r for r in results if r.get("ticker") != detected]
            results = matched + others

    return results[:top_k]
