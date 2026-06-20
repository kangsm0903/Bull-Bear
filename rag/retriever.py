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
    """쿼리에서 회사명을 감지해 ticker 반환. 못 찾으면 None.

    여러 회사명이 부분 문자열로 걸리면 가장 긴(=구체적인) 이름을 우선한다.
    (예: 'SK하이닉스'가 'SK'를 이김 — 짧은 종목명의 오매칭 방지)
    """
    corp_map = _get_corp_map()
    matches = [(name, ticker) for name, ticker in corp_map.items() if name in query]
    if not matches:
        return None
    return max(matches, key=lambda nt: len(nt[0]))[1]


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
    min_score: float = 0.0,     # 이 유사도 미만 결과 제외 (전부 미달이면 무시하고 top_k 유지)
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

    # ticker 명시 또는 쿼리에서 회사명 자동 감지 → 해당 종목으로 한정.
    detected = _detect_ticker(query) if (auto_detect and not ticker) else None
    filter_ticker = ticker or detected

    # 특정 종목으로 좁힐 땐 후보 풀을 넉넉히 잡는다.
    # (FAISS는 메타데이터 필터를 지원하지 않아 검색 후 필터링하므로,
    #  풀이 작으면 해당 종목 기사가 top_k만큼 안 잡혀 타사 기사가 섞인다.)
    search_k = top_k
    if filter_ticker:
        search_k = min(max(top_k * 50, 300), index.ntotal)
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

    # 종목 필터링 (검색 후 처리)
    if ticker:
        # 명시 종목: 엄격 필터 (해당 종목 기사만, 없으면 빈 결과)
        results = [r for r in results if r.get("ticker") == ticker]
    elif detected:
        # 감지 종목: 해당 종목만 남김. 단 후보에 하나도 없으면
        # 감지 오류로 보고 원본 의미검색 결과를 유지(안전장치).
        matched = [r for r in results if r.get("ticker") == detected]
        if matched:
            results = matched

    # 유사도 하한: 저관련 기사를 근거에서 제외. 단 전부 미달이면
    # 근거가 0건이 되어 토론이 깨지므로 하한을 무시하고 원본을 유지한다.
    if min_score > 0.0:
        passed = [r for r in results if r.get("score", 0.0) >= min_score]
        if passed:
            results = passed

    return results[:top_k]
