"""
build_ml_v2a.py — ML v2-A: 임베딩 기반 감성 모델 (입력만 글자조각→의미벡터로 교체)

v1과 동일: 정답=4o-mini 라벨, 회귀=Ridge(alpha=1), 악재가중 3.5, 출력 -1~1.
v1과 차이: 입력이 TF-IDF 글자조각 대신 FAISS에 이미 있는 1536차원 의미벡터.

평가: 같은 500건(test 격리) · gpt-5.4 정답지 캐시 → v1과 직접 비교.
실행:  python build_ml_v2a.py
"""
import json
import sqlite3
from pathlib import Path

import faiss
import numpy as np
from sklearn.linear_model import Ridge

import experiment_sentiment_3way as E
from train_sentiment_model import _sample_weights

BASE = Path(__file__).resolve().parent
DB = BASE / "identifier.sqlite"
INDEX = BASE / "rag" / "faiss_store" / "articles.index"

print("■ FAISS 임베딩 로드 (이미 만들어둔 벡터 재활용)...")
idx = faiss.read_index(str(INDEX))
vecs = idx.reconstruct_n(0, idx.ntotal)         # (N, 1536)
print(f"  벡터: {vecs.shape}")

rows = sqlite3.connect(DB).execute(
    "SELECT id, faiss_id, sentiment FROM articles "
    "WHERE sentiment IS NOT NULL AND faiss_id IS NOT NULL"
).fetchall()
fid_of = {i: f for i, f, _ in rows}

sample = E.fetch_strata()
test_ids = {a["id"] for a in sample}

Xtr = np.array([vecs[f] for i, f, _ in rows if i not in test_ids])
ytr = np.array([float(s) for i, _, s in rows if i not in test_ids])
print(f"■ ML v2-A 학습: {len(Xtr)}건 (임베딩 → Ridge, 악재가중 3.5)")
model = Ridge(alpha=1.0)
model.fit(Xtr, ytr, sample_weight=_sample_weights(ytr))

truth = json.loads(E.CACHE.read_text())
ids = [a["id"] for a in sample if a["id"] in fid_of]
Xte = np.array([vecs[fid_of[i]] for i in ids])
pred_arr = np.clip(model.predict(Xte), -1, 1)
preds = {i: float(p) for i, p in zip(ids, pred_arr)}

r = E.evaluate("ML v2-A (임베딩)", truth, preds)
print(f"\n■ ML v2-A 결과 (정답=gpt-5.4, {r['n']}건)")
print(f"    3분류 {r['acc3']:.1f}% | 부호 {r['sign']:.1f}% | "
      f"호재재현 {r['pos_rec']:.1f}% | 악재재현 {r['neg_rec']:.1f}%")
print("    [참고 v1] 3분류 44.6% | 부호 84.7% | 호재 81.3% | 악재 81.6%")

print("\n■ 중립 띠(band)별 3분류 (v2-A)")
y = np.array([truth[i] for i in ids]); s = np.array([preds[i] for i in ids])
for band in [0.05, 0.10, 0.20, 0.30, 0.40]:
    p = np.where(s > band, 1, np.where(s < -band, -1, 0))
    print(f"    ±{band:.2f}: 중립 {int((p==0).sum()):3d} | 3분류 {(p==y).mean()*100:.1f}%")

name = {1: "호재", -1: "악재", 0: "중립"}
print("\n■ 혼동행렬 v2-A (행=gpt-5.4 정답)")
print("    정답＼예측   호재  악재  중립")
for k, a in enumerate([1, -1, 0]):
    row = r["mat"][k]
    print(f"    {name[a]:>6s}     {row[0]:4d} {row[1]:4d} {row[2]:4d}")

# 다음 단계(v2-B)에서 재사용하도록 모델 저장
import joblib
joblib.dump(model, BASE / "rag" / "sentiment_model_v2a.joblib")
print(f"\n저장: rag/sentiment_model_v2a.joblib")
