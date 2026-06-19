"""
종목 인식 + 별칭
"""

import sqlite3
from pathlib import Path

import faiss
import numpy as np

from rag.embedder import embed_query
from rag.sentiment import sentiment_score

BASE_DIR = Path(__file__).resolve().parent.parent
DB_PATH = BASE_DIR / "identifier.sqlite"
FAISS_DIR = Path(__file__).resolve().parent / "faiss_store"

# 인덱스 캐시 (한 번 로드 후 메모리 유지)
_indexes: dict[str, faiss.Index] = {}

# 회사명 → ticker 매핑 캐시
_corp_map: dict[str, str] = {}


def _get_corp_map() -> dict[str, str]:
    """DB에서 {corp_name, ticker} 뽑아냄"""
    global _corp_map
    if not _corp_map:
        with sqlite3.connect(DB_PATH) as conn:
            rows = conn.execute("SELECT corp_name, ticker FROM companies").fetchall()
        _corp_map = {name: ticker for name, ticker in rows}
    return _corp_map


def _detect_ticker(query: str) -> str | None:
    """쿼리에서 회사명을 감지해 ticker 반환. 못 찾으면 None.

    2-pass 매칭:
      1) 정식 corp_name 부분일치 ("SK하이닉스 전망")
      2) 별칭(접두사 제거형) 부분일치 ("하이닉스 전망" → SK하이닉스)
    정식명을 우선 시도해 별칭 충돌(예: 'LG전자' vs '전자') 위험을 줄임.
    """
    corp_map = _get_corp_map()
    # 1) 정식명 우선
    for name, ticker in corp_map.items():
        if name in query:
            return ticker
    # 2) 별칭 폴백 — _name_aliases는 _ticker_to_name 아래에 정의돼 있음
    for name, ticker in corp_map.items():
        for alias in _name_aliases(name):
            if alias != name and alias in query:
                return ticker
    return None


def _ticker_to_name(ticker: str) -> str:
    """ticker → 회사명. 없으면 빈 문자열."""
    for name, t in _get_corp_map().items():
        if t == ticker:
            return name
    return ""


# 시황/시장요약 등 영양가 낮은 기사를 거르는 제목 키워드 블록리스트
MARKET_NOISE_KEYWORDS = [
    "코스피", "코스닥", "증시", "시황", "특징주", "급등주", "급락주", "마감 시황",
]

# 그룹 접두사 — 제거해 별칭 생성 (예: "SK하이닉스" → "하이닉스")
GROUP_PREFIXES = ("SK", "LG", "GS", "CJ", "KT", "NH", "DB", "HD", "DL", "POSCO")

# 수동 별칭 맵 — 기사 제목/검색어 표기가 정식 종목명과 다른 종목 (영문↔한글·약칭)
# ✏️ 무관 기사가 많은 종목을 발견하면 여기에 추가하세요.
MANUAL_ALIASES = {
    "삼성에스디에스":  ["삼성SDS"],
    "POSCO홀딩스":    ["포스코", "POSCO"],
    "POSCO퓨처엠":    ["포스코퓨처엠", "포스코"],
    "NAVER":         ["네이버"],
    "S-Oil":         ["에쓰오일", "S오일"],
    "LS ELECTRIC":   ["LS일렉트릭", "LS일렉", "LS산전"],
    "신한지주":       ["신한금융", "신한은행"],
    "BNK금융지주":    ["BNK금융", "부산은행", "경남은행"],
    "iM금융지주":     ["iM뱅크", "iM금융", "DGB금융"],
    "메리츠금융지주":  ["메리츠금융", "메리츠증권", "메리츠화재"],
    "JB금융지주":     ["JB금융", "전북은행", "광주은행"],
    "우리금융지주":    ["우리금융", "우리은행"],
    "하나금융지주":    ["하나금융", "하나은행"],
    "카카오뱅크":     ["카뱅"],
}


def _noise_clause() -> str:
    """제목 블록리스트를 SQL AND 절로 변환 (키워드는 상수이므로 인젝션 위험 없음)."""
    return " ".join(f"AND title NOT LIKE '%{kw}%'" for kw in MARKET_NOISE_KEYWORDS)


def _name_aliases(corp_name: str) -> list[str]:
    """제목 매칭용 별칭 목록.
      · 정식명
      · 그룹 접두사 제거형 (예: "SK하이닉스" → "하이닉스")
      · "○○금융지주" → "○○금융" 규칙 (기사가 '지주'를 잘 안 씀)
      · 수동 별칭 맵 (영문↔한글·약칭)
    별칭은 오탐 방지를 위해 3자 이상만 사용.
    """
    aliases = [corp_name]
    # 그룹 접두사 제거 (3자 이상 남을 때만)
    for p in GROUP_PREFIXES:
        if corp_name.startswith(p) and len(corp_name) - len(p) >= 3:
            aliases.append(corp_name[len(p):])
    # "○○금융지주" → "○○금융" (지주 표기 생략 대응)
    if corp_name.endswith("금융지주"):
        aliases.append(corp_name[:-2])
    # 수동 별칭
    aliases.extend(MANUAL_ALIASES.get(corp_name, []))
    # 3자 미만 별칭 제거 + 중복 제거
    return list(dict.fromkeys(a for a in aliases if len(a) >= 3))


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
                   a.title, a.content, a.source, a.published_at, a.url, a.sentiment
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


def _recent_faiss_ids(ticker: str | None, pool_size: int) -> list[int]:
    """종목의 최신 후보 풀(faiss_id)을 published_at 내림차순으로 반환.

    품질 필터 (검색 시점):
      · 시황/시장요약 등 노이즈 제목 제외 (MARKET_NOISE_KEYWORDS)
      · Tier1: 제목에 종목명(별칭 포함)이 든 "그 기업 중심" 기사만
      · Tier2: Tier1이 완전히 비었을 때만 폴백 (빈 결과 방지용).
               → 평소엔 제목 무관 기사로 풀을 채우지 않아 타사 중심 기사가 섞이지 않음
    ticker가 None이면 노이즈만 제외한 전체 최신 기사.
    """
    noise = _noise_clause()
    with sqlite3.connect(DB_PATH) as conn:
        if not ticker:
            rows = conn.execute(f"""
                SELECT faiss_id FROM articles
                WHERE faiss_id IS NOT NULL {noise}
                ORDER BY published_at DESC
                LIMIT ?
            """, (pool_size,)).fetchall()
            return [int(r[0]) for r in rows]

        corp_name = _ticker_to_name(ticker)
        aliases = _name_aliases(corp_name)
        like_clause = " OR ".join("title LIKE ?" for _ in aliases)
        like_params = [f"%{a}%" for a in aliases]

        # Tier1: 제목에 종목명(별칭 포함)이 든 기사만 + 노이즈 제외
        tier1 = conn.execute(f"""
            SELECT faiss_id FROM articles
            WHERE ticker = ? AND faiss_id IS NOT NULL
              AND ({like_clause}) {noise}
            ORDER BY published_at DESC
            LIMIT ?
        """, (ticker, *like_params, pool_size)).fetchall()
        ids = [int(r[0]) for r in tier1]

        # Tier2: Tier1이 완전히 비었을 때만 폴백 (빈 결과 방지)
        if not ids:
            tier2 = conn.execute(f"""
                SELECT faiss_id FROM articles
                WHERE ticker = ? AND faiss_id IS NOT NULL {noise}
                ORDER BY published_at DESC
                LIMIT ?
            """, (ticker, pool_size)).fetchall()
            ids = [int(r[0]) for r in tier2]

    return ids


def _get_sentiment(a: dict) -> float:
    """기사의 감성 점수. LLM이 미리 채점해 저장한 값(sentiment)을 우선 사용하고,
    아직 라벨링 안 된 기사는 단어 사전(sentiment_score)으로 폴백."""
    s = a.get("sentiment")
    if s is not None:
        return float(s)
    return sentiment_score(a.get("title"), a.get("content"))


def _rank_pool(
    index: faiss.Index,
    query_vec: np.ndarray,
    pool_ids: list[int],
    top_k: int,
    bias: str | None = None,        # "bull" | "bear" | None
    sentiment_weight: float = 0.0,
) -> list[dict]:
    """후보 풀(pool_ids)을 query 유사도 + 감성 보정으로 정렬해 top_k 기사 반환.

    감성 필터 (bias가 bull/bear일 때):
        · bias="bull" → 호재(sent > 0) 기사만 통과, 부호 +1로 가산
        · bias="bear" → 악재(sent < 0) 기사만 통과, 부호 -1로 가산
        · 중립(sent == 0)은 양쪽 모두 제외 → 해당 진영 기사가 부족하면 적게/비워서 반환
        · bias=None(common) → 필터·가산 없음, 순수 유사도로 전부 후보

        최종점수 = cosine 유사도 + sentiment_weight × bias부호 × 감성점수(-1~1)

    IndexFlatIP.reconstruct로 빌드 시 정규화된 벡터를 되찾아 내적(=cosine)을 계산한다.
    각 기사 dict에는 'score'(순수 유사도)를 기록한다.
    """
    bias_sign = {"bull": 1.0, "bear": -1.0}.get(bias, 0.0)
    filter_active = bias_sign != 0.0   # bull/bear면 감성 필터 적용

    q = query_vec[0]
    ntotal = index.ntotal

    articles = _fetch_articles(pool_ids)   # 텍스트(title/content) 포함
    ranked: list[tuple[float, dict]] = []
    for a in articles:
        fid = a["faiss_id"]
        if fid >= ntotal:                  # 인덱스보다 큰 faiss_id(스테일) 방어
            continue
        sim = float(np.dot(q, index.reconstruct(fid)))
        a["score"] = sim
        final = sim
        if filter_active:
            sent = _get_sentiment(a)   # 저장된 LLM 점수 우선, 없으면 단어 사전 폴백
            # bull은 호재만, bear는 악재만 (중립/반대극성 제외)
            if bias_sign > 0 and sent <= 0:
                continue
            if bias_sign < 0 and sent >= 0:
                continue
            final = sim + sentiment_weight * bias_sign * sent
        ranked.append((final, a))

    ranked.sort(key=lambda x: x[0], reverse=True)
    return [a for _, a in ranked[:top_k]]


def search(
    query: str,
    source: str = "articles",  # "articles" | "dart"
    top_k: int = 5,
    ticker: str = None,         # 특정 종목만 필터링 (선택)
    auto_detect: bool = True,   # 쿼리에서 회사명 자동 감지해 ticker 부스팅
    recent_pool: int = 30,      # 하이브리드 최신 후보 풀 크기 (앱에서는 config.RECENT_POOL 주입)
    bias: str = None,           # "bull"|"bear"|None — 감성 보정 방향
    sentiment_weight: float = 0.0,  # 감성 가중치 (앱에서는 config.SENTIMENT_WEIGHT 주입)
) -> list[dict]:
    """
    query를 임베딩해 FAISS로 유사 문서를 검색하고 SQLite 메타데이터를 반환

    Args:
        query: 검색 쿼리 (자연어)
        source: "articles" 또는 "dart"
        top_k: 반환할 결과 수 (ticker 필터 시 여유있게 크게 설정)
        ticker: 특정 종목 코드로 필터링 (예: "005930")
        auto_detect: True이면 쿼리에서 회사명 자동 감지 → 해당 종목 결과 우선 정렬
        recent_pool: 하이브리드 검색 시 종목별 최신 후보 풀 크기

    Returns:
        유사도 순으로 정렬된 문서 메타데이터 리스트

    검색 전략:
        articles + 종목 감지 시 → "최신 풀 → 유사도 정렬" 하이브리드
            (해당 종목의 최신 recent_pool개 기사만 후보로 두고, 그 안에서 유사도 top_k)
        그 외(dart / 종목 미감지 / 빈 풀) → 기존 전역 유사도 검색으로 폴백
    """
    index = _load_index(source)

    # 쿼리 임베딩 → 정규화
    query_vec = np.array([embed_query(query)], dtype="float32")
    faiss.normalize_L2(query_vec)

    # ticker 필터 또는 자동 감지 시 여유있게 검색 후 필터
    detected_for_boost = _detect_ticker(query) if (auto_detect and not ticker) else None

    # ── 하이브리드: articles + 종목 감지 시 "최신 풀 → 유사도 정렬" ──
    hybrid_ticker = ticker or detected_for_boost
    if source == "articles" and hybrid_ticker:
        pool_ids = _recent_faiss_ids(hybrid_ticker, recent_pool)
        if pool_ids:
            return _rank_pool(
                index, query_vec, pool_ids, top_k,
                bias=bias, sentiment_weight=sentiment_weight,
            )
        # 풀이 비면(=해당 종목 faiss_id 없음) 아래 전역 검색으로 폴백

    # ── 폴백: 기존 전역 유사도 검색 ──
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
