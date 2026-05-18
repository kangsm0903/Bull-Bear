# Bull vs Bear — AI 주식 토론 시스템

> **Bull** vs **Bear** 토론하고, **Moderator** 가 최종 투자 의견을 제시하는 시스템.  
> RAG(뉴스) + 정량 데이터(재무·컨센서스·주가)를 모두 활용합니다.

---

## 📌 핵심 한눈에 보기

```
사용자 입력 (예: "삼성전자")
        ↓
   ┌───────────────────────────────────────┐
   │ Round 1 (정성)  → 뉴스 기사 기반 토론       │
   │ Round 2 (정량)  → 재무·주가 기반 토론       │
   │ Round 3 (통합)  → 양측 최종 결론           │
   │ Moderator      → 투자 판단 종합           │
   └───────────────────────────────────────┘
        ↓
  React UI에 순차 출력 (Bull / Bear 메시지)
```

**한 번 토론 = LLM 호출 11회 ≈ $0.05~0.08** (gpt-4o 기준)

---

## 🚀 빠른 시작

### 1️⃣ 환경 설정

```bash
python -m venv myenv
source myenv/bin/activate
pip install -r requirements.txt
```

`.env` 파일 생성:
```bash
OPENAI_API_KEY=sk-...
```

### 2️⃣ 데이터 수집 (한 번만 실행)

```bash
# 시가총액 상위 200개 기업 초기화
python -m collection.companies

# 뉴스 크롤링 (기업당 최대 50건)
python -m collection.naver_news_crawling

# 재무제표 / 컨센서스 / 주가
python -m collection.financials
python -m collection.consensus
python -m collection.quant_macro_daily
```

### 3️⃣ FAISS 인덱스 빌드

```bash
# 전체 기사 임베딩
python -m rag.index_builder --articles

# 특정 종목만 (테스트)
python -m rag.index_builder --articles --ticker 005930
```

### 4️⃣ 프론트엔드 빌드

```bash
cd frontend
npm install
npm run build
```

### 5️⃣ 서버 실행

```bash
uvicorn main:app --reload --port 8000
```

→ 브라우저에서 **http://localhost:8000** 접속

---

## 📂 폴더 구조

```
BullBear/
│
├── main.py                       # FastAPI 서버 엔트리포인트
│
├── agents/                       # AI 에이전트 (★ 토론 로직 핵심)
│   ├── config.py                    # ⭐ 설정 (모델, 온도, 발언 순서)
│   ├── prompts.py                   # ⭐ 프롬프트 텍스트
│   ├── analyst.py                   # Bull/Bear 통합 (AnalystAgent)
│   ├── moderator.py                 # 사회자
│   ├── orchestrator.py              # 토론 흐름 실행 엔진
│   ├── base_agent.py                # OpenAI 호출 기반
│   └── query_expander.py            # 주제 → 검색 쿼리 확장
│
├── rag/                          # RAG (검색 증강 생성)
│   ├── retriever.py                 # FAISS 검색 + SQLite 메타 조회
│   ├── index_builder.py             # 벡터 인덱스 빌드
│   ├── embedder.py                  # OpenAI 임베딩 래퍼
│   ├── quant_fetcher.py             # 정량 데이터 조회·포맷
│   └── faiss_store/articles.index   # 벡터 인덱스 (빌드 후 생성)
│
├── collection/                   # 데이터 수집 스크립트
│   ├── companies.py                 # 기업 목록 초기화 (KOSPI 200)
│   ├── naver_news_crawling.py       # 네이버 증권 뉴스 크롤러
│   ├── financials.py                # 분기 재무제표
│   ├── consensus.py                 # 증권사 컨센서스
│   ├── quant_macro_daily.py         # 일별 주가·수급·PER·PBR
│   └── dart_disclosures.py          # DART 공시 (선택)
│
├── frontend/                     # React + Vite + Tailwind
│   └── src/app/
│       ├── App.tsx
│       └── components/
│           ├── InputScreen.tsx      # 종목 입력 화면
│           ├── LoadingScreen.tsx    # 로딩 화면
│           ├── DebateChat.tsx       # 토론 채팅 화면
│           ├── DebateMessage.tsx    # 메시지 버블
│           └── ArticleReference.tsx # 참고 기사 카드
│
├── streamlit_app.py                 # (구버전) Streamlit UI
├── test_debate.py                   # 터미널 토론 테스트
├── identifier.sqlite                # 메인 DB
└── .env                             # API 키
```

---

## 🎭 토론 구조 (핵심)

### 라운드별 발언 순서

| 라운드 | 데이터 | 선공 | 발언 순서 |
|:---:|:---|:---:|:---|
| **R1** | 뉴스 기사 | Bull | ① 찬성 주장 → ② 반대 반론 → ③ 반대 주장 → ④ 찬성 반론 |
| **R2** | 재무·주가 | Bear | ① 반대 주장 → ② 찬성 반론 → ③ 찬성 주장 → ④ 반대 반론 |
| **R3** | 통합 | — | ① 찬성 최종 결론 → ② 반대 최종 결론 |
| **Mod** | 전체 토론 | — | 투자 판단 (매수 적극 / 분할 매수 / 관망 / 매도 고려) |

### 핵심 원칙

1. **반론은 상대 주장을 받아서 생성**  
   → 반론자의 프롬프트에 상대방의 직전 주장이 입력으로 들어감

2. **라운드 간 독립성**  
   → R2는 R1 출력을 참조하지 않음. 각 라운드는 raw 데이터만 사용

3. **병렬 호출로 속도 최적화**  
   → 의존성 없는 주장은 동시에 호출 (Bull.argue + Bear.argue 병렬)

---

## ⚙️ 토론 커스터마이징

모든 설정은 **`agents/config.py`** 하나에 모여 있습니다.

### 모델·온도 변경

```python
# agents/config.py
MODEL_NAME = "gpt-4o"          # → "gpt-4o-mini"로 바꾸면 비용 1/10

TEMPERATURE = {
    "argue":     0.7,          # 주장: 다양성
    "rebut":     0.7,          # 반론: 다양성
    "conclude":  0.3,          # 결론: 일관성
    "moderator": 0.3,          # 사회자: 일관성
}
```

### 발언 순서 변경

```python
# agents/config.py
DEBATE_FLOW = [
    {
        "round": 1,
        "name":  "정성 분석",
        "data":  ["articles"],          # ["quant"], ["articles","quant"] 가능
        "steps": [
            {"role": "bull", "action": "argue"},
            {"role": "bear", "action": "rebut", "rebuts": ("bull", "argue")},
            {"role": "bear", "action": "argue"},
            {"role": "bull", "action": "rebut", "rebuts": ("bear", "argue")},
        ],
    },
    # ... 라운드 추가/제거 자유
]
```

| 필드 | 값 | 설명 |
|:---|:---|:---|
| `role` | `"bull"` / `"bear"` | 누가 발언하는지 |
| `action` | `"argue"` / `"rebut"` / `"conclude"` | 주장 / 반론 / 결론 |
| `rebuts` | `("role", "action")` | 반론 대상 (action=rebut일 때만) |
| `data` | `["articles"]` / `["quant"]` / `["articles","quant"]` | 사용 데이터 종류 |

> 💡 의존성 없는 step은 **자동 병렬 실행**

### 프롬프트 수정

`agents/prompts.py`에 모든 프롬프트가 모여 있습니다:

```
SYSTEM_PROMPT_BULL       Bull 페르소나
SYSTEM_PROMPT_BEAR       Bear 페르소나
SYSTEM_PROMPT_MODERATOR  Moderator 페르소나
build_argue_prompt()     주장 프롬프트
build_rebut_prompt()     반론 프롬프트
build_conclude_prompt()  결론 프롬프트
build_moderator_prompt() 사회자 프롬프트
```

---

## 🔍 RAG 동작 방식

```
사용자 입력
    ↓
[query_expander]  ─→  3종 쿼리 생성 (룰 기반, LLM 호출 X)
                        • common: 중립 (예: "삼성전자 최근 실적 현황")
                        • bull:   긍정 (예: "삼성전자 성장 호재")
                        • bear:   부정 (예: "삼성전자 리스크 악재")
    ↓
[embedder]        ─→  OpenAI text-embedding-3-small (1536차원)
    ↓
[FAISS]           ─→  벡터 유사도 검색
    ↓
[SQLite]          ─→  faiss_id로 메타데이터(title, content, url) 조회
    ↓
Bull에게: common(3) + bull(2) = 5개 기사
Bear에게: common(3) + bear(2) = 5개 기사
```

---

## 🗄️ DB 스키마

| 테이블 | 내용 |
|:---|:---|
| `companies` | 시가총액 상위 200개 기업 (ticker, name, market_cap) |
| `articles` | 네이버 증권 뉴스 + faiss_id (제목, 본문, URL, 출처) |
| `financials` | 분기별 재무제표 (매출/영업이익/순이익) |
| `consensus_snapshots` | 증권사 목표주가·투자의견 스냅샷 |
| `quant_daily` | 주가·수급·PER·PBR 일별 데이터 |
| `dart_disclosures` | DART 공시 목록 |

---

## 💰 비용 추정

| 항목 | 토큰 | 단가 (GPT-4o) | 비용 |
|:---|:---:|:---:|:---:|
| 입력 (11회 × ~1,300) | ~14,000 | $2.50/1M | $0.035 |
| 출력 (11회 × ~180) | ~2,000 | $10.00/1M | $0.020 |
| **1회 토론** | | | **$0.05~0.08** |

> 🪙 `gpt-4o-mini` 사용 시 약 **1/10 수준**으로 절감

---

## 🛠️ 트러블슈팅

| 증상 | 해결 |
|:---|:---|
| `ModuleNotFoundError: faiss` | `pip install faiss-cpu` |
| `OPENAI_API_KEY` 없음 | 프로젝트 루트에 `.env` 생성 |
| `database is locked` | 크롤링 진행 중 → 잠시 후 재시도 |
| 화면 빈 흰 화면 | 브라우저 `Cmd + Shift + R` 강제 새로고침 |
| 빌드 후 변경 반영 안 됨 | `cd frontend && npm run build` 후 uvicorn 재시작 |

---

## 📚 참고

- **모델**: GPT-4o + `response_format={"type": "json_object"}`
- **임베딩**: OpenAI `text-embedding-3-small`
- **벡터 DB**: FAISS (IndexFlatL2)
- **데이터 소스**: 네이버 증권, FinanceDataReader, pykrx, DART
