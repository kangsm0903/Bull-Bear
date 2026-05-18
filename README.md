# Bull vs Bear AI 토론 시스템

뉴스 기사와 재무 데이터를 기반으로 GPT-4o가 Bull·Bear 관점에서 주식 토론을 진행하는 시스템

---

## 폴더 구조

```
BullBear/
│
├── streamlit_app.py          # 프론트엔드 (Streamlit UI)
├── query_expander.py         # 토론 주제 → 3종 검색 쿼리 확장
├── test_debate.py            # 터미널 토론 테스트 스크립트
│
├── agents/                   # AI 에이전트
│   ├── base_agent.py         # GPT-4o 호출 공통 기반
│   ├── bull_agent.py         # 강세 논거 생성
│   ├── bear_agent.py         # 약세 논거 생성
│   ├── moderator.py          # 최종 결론 도출
│   └── orchestrator.py       # 전체 토론 흐름 제어
│
├── rag/                      # 검색 증강 생성 (RAG)
│   ├── embedder.py           # OpenAI text-embedding-3-small 래퍼
│   ├── index_builder.py      # FAISS 인덱스 빌드
│   ├── retriever.py          # FAISS 검색 + SQLite 메타데이터 조회
│   ├── quant_fetcher.py      # 정량 데이터 조회 (재무/컨센서스/주가)
│   └── faiss_store/
│       └── articles.index    # 벡터 인덱스 (빌드 후 생성)
│
├── ingest_naver_news.py      # 네이버 증권 뉴스 크롤러
├── ingest_dart_disclosures.py# DART 공시 수집
├── ingest_financials.py      # 재무제표 수집
├── ingest_consensus_snapshots.py # 컨센서스(목표주가) 수집
├── init_companies.py         # 시가총액 상위 200개 기업 초기화
├── quant_macro_daily.py      # 주가/수급 일별 데이터 수집
│
├── identifier.sqlite         # 메인 DB (articles, financials 등)
├── requirements.txt          # 패키지 목록
└── .env                      # API 키 (OPENAI_API_KEY)
```

---

## 실행 순서

### 1. 환경 설정
```bash
python -m venv myenv
source myenv/bin/activate
pip install -r requirements.txt
```

`.env` 파일 생성:
```
OPENAI_API_KEY=sk-...
```

### 2. DB 초기화 (기업 목록)
```bash
python init_companies.py
```

### 3. 데이터 수집
```bash
# 뉴스 크롤링 (시가총액 상위 200개, 기업당 50건)
python ingest_naver_news.py

# 재무제표
python ingest_financials.py

# 컨센서스(목표주가)
python ingest_consensus_snapshots.py

# 주가/수급 일별 데이터
python quant_macro_daily.py
```

### 4. FAISS 인덱스 빌드
```bash
# 전체 기사 임베딩
python -m rag.index_builder --articles

# 특정 종목만 (테스트용)
python -m rag.index_builder --articles --ticker 005930
```

### 5. 실행
```bash
# Streamlit UI
streamlit run streamlit_app.py

# 터미널 테스트
python test_debate.py
```

---

## 토론 구조

| 라운드 | 데이터 | 목적 |
|--------|--------|------|
| Round 1 | 뉴스 기사 (정성) | 기사 근거 핵심 논거 |
| Round 2 | 재무·컨센서스·주가 (정량) | 숫자 기반 반박 |
| Round 3 | 기사 + 정량 통합 | 최종 주장 완성 |
| Moderator | 전체 토론 종합 | 투자 판단 결론 |

---

## DB 테이블

| 테이블 | 내용 |
|--------|------|
| companies | 시가총액 상위 200개 기업 |
| articles | 네이버 증권 뉴스 (기업당 50건) |
| financials | 분기별 재무제표 |
| consensus_snapshots | 목표주가·투자의견 |
| quant_daily | 주가·수급·PER·PBR 일별 |
| dart_disclosures | DART 공시 목록 |
