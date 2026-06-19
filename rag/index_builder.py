"""
SQLite 데이터를 읽어 FAISS 인덱스를 빌드하고 저장

실행:
    python -m rag.index_builder           # articles + dart 전체 빌드
    python -m rag.index_builder --articles # articles만
    python -m rag.index_builder --dart     # dart만
"""

import argparse
import sqlite3
from pathlib import Path

import faiss
import numpy as np

from rag.embedder import embed_texts

BASE_DIR = Path(__file__).resolve().parent.parent
DB_PATH = BASE_DIR / "identifier.sqlite"
FAISS_DIR = Path(__file__).resolve().parent / "faiss_store"


def _normalize_and_build_index(embeddings: list[list[float]]) -> faiss.Index:
    """벡터 정규화 후 IndexFlatIP 생성 (= cosine similarity)"""
    vectors = np.array(embeddings, dtype="float32")
    faiss.normalize_L2(vectors)  # OpenAI 임베딩은 정규화 후 IP = cosine
    dim = vectors.shape[1]
    index = faiss.IndexFlatIP(dim)
    index.add(vectors)
    return index


def build_articles_index(ticker: str = None):
    """articles 테이블 → articles.index. ticker 지정 시 해당 종목만."""
    label = f"articles ({ticker})" if ticker else "articles"
    print(f"=== {label} 인덱스 빌드 ===")

    query = """
        SELECT a.id, c.corp_name, a.title, a.content
        FROM articles a
        JOIN companies c ON a.ticker = c.ticker
        WHERE a.title IS NOT NULL
    """
    params: tuple = ()
    if ticker:
        query += " AND a.ticker = ?"
        params = (ticker,)
    query += " ORDER BY a.published_at DESC"

    with sqlite3.connect(DB_PATH) as conn:
        rows = conn.execute(query, params).fetchall()

    if not rows:
        print("articles 데이터 없음. 종료.")
        return

    print(f"  대상: {len(rows)}건")

    # 임베딩 텍스트 구성: 제목을 2회 반복해 주제 신호를 강화하고, 본문은 300자로 축소
    # (긴 본문이 제목을 희석해 주변부 기사가 끼는 문제 완화)
    texts = [
        f"[{corp_name}] {title}\n{title}\n{(content or '')[:300]}".strip()
        for _, corp_name, title, content in rows
    ]

    print("  임베딩 생성 중...")
    embeddings = embed_texts(texts)

    index = _normalize_and_build_index(embeddings)

    FAISS_DIR.mkdir(exist_ok=True)
    index_path = FAISS_DIR / "articles.index"
    faiss.write_index(index, str(index_path))
    print(f"  저장 완료 → {index_path}")

    # SQLite faiss_id 업데이트 (크롤링 중 락 대비 timeout=30초)
    with sqlite3.connect(DB_PATH, timeout=30) as conn:
        for faiss_id, (article_id, *_) in enumerate(rows):
            conn.execute(
                "UPDATE articles SET faiss_id = ? WHERE id = ?",
                (faiss_id, article_id),
            )
        conn.commit()
    print(f"  faiss_id 업데이트 완료 ({len(rows)}건)")
    print(f"✅ articles.index 빌드 완료 (dim={len(embeddings[0])})\n")


def build_dart_index():
    """dart_disclosures 테이블 → dart.index"""
    print("=== dart 인덱스 빌드 ===")

    with sqlite3.connect(DB_PATH) as conn:
        rows = conn.execute("""
            SELECT d.rcept_no, c.corp_name, d.report_name, d.submitted_at
            FROM dart_disclosures d
            JOIN companies c ON d.ticker = c.ticker
            ORDER BY d.submitted_at DESC
        """).fetchall()

    if not rows:
        print("dart_disclosures 데이터 없음. 종료.")
        return

    print(f"  대상: {len(rows)}건")

    # 임베딩 텍스트 구성: [종목명] 공시명 (제출일)
    texts = [
        f"[{corp_name}] {report_name} ({submitted_at})"
        for _, corp_name, report_name, submitted_at in rows
    ]

    print("  임베딩 생성 중... (28,000건 기준 약 1~2분 소요)")
    embeddings = embed_texts(texts)

    index = _normalize_and_build_index(embeddings)

    FAISS_DIR.mkdir(exist_ok=True)
    index_path = FAISS_DIR / "dart.index"
    faiss.write_index(index, str(index_path))
    print(f"  저장 완료 → {index_path}")

    # SQLite faiss_id 업데이트
    with sqlite3.connect(DB_PATH) as conn:
        for faiss_id, (rcept_no, *_) in enumerate(rows):
            conn.execute(
                "UPDATE dart_disclosures SET faiss_id = ? WHERE rcept_no = ?",
                (faiss_id, rcept_no),
            )
        conn.commit()
    print(f"  faiss_id 업데이트 완료 ({len(rows)}건)")
    print(f"✅ dart.index 빌드 완료 (dim={len(embeddings[0])})\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--articles", action="store_true", help="articles만 빌드")
    parser.add_argument("--dart",     action="store_true", help="dart만 빌드")
    parser.add_argument("--ticker",   type=str, default=None,
                        help="특정 종목만 임베딩 (예: 005930)")
    args = parser.parse_args()

    # 플래그 없으면 둘 다 빌드
    run_all = not args.articles and not args.dart

    if args.articles or run_all:
        build_articles_index(ticker=args.ticker)
    if args.dart or run_all:
        build_dart_index()
