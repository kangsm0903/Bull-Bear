"""
build_ml_v2b.py — ML v2-B: 하이브리드 (글자조각 TF-IDF + 임베딩 결합)

v1(글자조각만)에 임베딩을 추가 피처로 붙여 학습. 둘의 스케일이 달라 임베딩이
묻힐 수 있어, 두 변형 비교:
  · raw     : TF-IDF + 임베딩 원본 결합
  · scaled  : TF-IDF + 표준화한 임베딩 결합 (임베딩에 공정한 가중)

평가: 같은 500건(test 격리) · gpt-5.4 정답지 → v1/v2-A와 직접 비교.
실행:  python build_ml_v2b.py
"""
import json
import sqlite3
from pathlib import Path

import faiss
import numpy as np
from scipy.sparse import hstack, csr_matrix
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import Ridge
from sklearn.preprocessing import StandardScaler

import experiment_sentiment_3way as E
from train_sentiment_model import _sample_weights, BODY_CHARS

BASE = Path(__file__).resolve().parent
DB = BASE / "identifier.sqlite"
INDEX = BASE / "rag" / "faiss_store" / "articles.index"

print("■ 임베딩 + 텍스트 로드...")
idx = faiss.read_index(str(INDEX))
vecs = idx.reconstruct_n(0, idx.ntotal)

rows = sqlite3.connect(DB).execute(
    "SELECT id, faiss_id, title, content, sentiment FROM articles "
    "WHERE sentiment IS NOT NULL AND faiss_id IS NOT NULL"
).fetchall()

sample = E.fetch_strata()
test_ids = {a["id"] for a in sample}
truth = json.loads(E.CACHE.read_text())

def text_of(t, c):
    return f"{(t or '')} {(c or '')[:BODY_CHARS]}".strip()

tr = [(text_of(t, c), vecs[f], s) for i, f, t, c, s in rows if i not in test_ids]
te = [(i, text_of(t, c), vecs[f]) for i, f, t, c, s in rows
      if i in test_ids and i in truth]

txt_tr = [x[0] for x in tr]
emb_tr = np.array([x[1] for x in tr])
ytr = np.array([x[2] for x in tr])
ids_te = [x[0] for x in te]
txt_te = [x[1] for x in te]
emb_te = np.array([x[2] for x in te])

print(f"■ 학습 {len(txt_tr)}건 / 테스트 {len(ids_te)}건")
tfidf = TfidfVectorizer(analyzer="char_wb", ngram_range=(2, 4),
                        min_df=3, max_features=50000).fit(txt_tr)
Xtr_t = tfidf.transform(txt_tr)
Xte_t = tfidf.transform(txt_te)
w = _sample_weights(ytr)

def run(name, emb_tr_f, emb_te_f):
    Xtr = hstack([Xtr_t, csr_matrix(emb_tr_f)]).tocsr()
    Xte = hstack([Xte_t, csr_matrix(emb_te_f)]).tocsr()
    m = Ridge(alpha=1.0, solver="lsqr")
    m.fit(Xtr, ytr, sample_weight=w)
    pred = np.clip(m.predict(Xte), -1, 1)
    preds = {i: float(p) for i, p in zip(ids_te, pred)}
    r = E.evaluate(name, truth, preds)
    print(f"    {name:18s} 3분류 {r['acc3']:.1f}% | 부호 {r['sign']:.1f}% | "
          f"호재 {r['pos_rec']:.1f}% | 악재 {r['neg_rec']:.1f}%")
    return r

print("\n■ v2-B 변형 비교 (정답=gpt-5.4)")
scaler = StandardScaler().fit(emb_tr)
run("v2-B raw", emb_tr, emb_te)
run("v2-B scaled", scaler.transform(emb_tr), scaler.transform(emb_te))
print("    " + "-"*64)
print(f"    {'[v1 글자조각]':18s} 3분류 44.6% | 부호 84.7% | 호재 81.3% | 악재 81.6%")
print(f"    {'[v2-A 임베딩만]':16s} 3분류 43.4% | 부호 77.8% | 호재 74.0% | 악재 76.5%")
