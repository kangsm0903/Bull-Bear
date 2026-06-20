# Tool Calling · 유저 페르소나 · 환각 방지 가드 — 설계 문서

> 이 문서는 기존 고정 RAG 파이프라인에 추가한 세 가지 에이전트 기능을 설명한다.
> ① **Tool calling 기반 자료 조사 방식**(per_step / upfront / hybrid), ② **설문 기반 유저 페르소나**(독자 수준 맞춤 답변), ③ **환각 방지 가드**(결정적 숫자검증 + Self-Reflection).
> 모든 내용은 현재 소스 코드 기준이며, 조사 모드 실측 수치는 `compare_research_modes.py`로 재현 가능하다.

---

## 1. 배경 / 동기

기존 구조는 orchestrator가 DB에서 기사를 미리(`pre-fetch`) 가져와 Bull·Bear에게 동일하게 떠먹여주는 **고정 RAG 파이프라인**이었다. 그 결과:

- 양측이 같은 기사 세트를 받아 **주장이 비슷해지는 경향**이 있었다.
- "자료 조사" 자체가 에이전트의 능력인데, 이를 활용하지 못했다.
- 답변이 항상 동일한 톤·난이도로 생성되어 **독자 수준을 고려하지 못했다**.

이를 개선하기 위해 (1) 각 에이전트가 자기 입장 근거를 **직접 조사**하도록 tool calling을 도입하고, (2) 사용자의 투자 지식 수준을 **설문으로 받아 답변을 맞춤화**했다.

---

## 2. Tool Calling — 자료 조사 방식

### 2.1 도구 (`agents/tools.py`)

| 도구 | 기능 |
|---|---|
| `search_articles(query, top_k)` | 뉴스/기사 의미 기반(임베딩) 검색 (`rag.retriever.search` 래핑) |
| `fetch_quant(ticker)` | 재무·컨센서스·주가 정량 데이터 조회 (`rag.quant_fetcher` 래핑). 6자리 코드 또는 회사명 허용 |

- `dispatch(name, args)` → `{"text": 모델용 텍스트, "articles": 검색 기사 리스트}` 반환. 빈 query/ticker 방어, JSON 파싱 예외 처리, 유사도(`TOOL_SEARCH_MIN_SCORE`) 미만 결과 필터링.
- `cache_key()` 로 같은 step 내 동일 호출 중복을 판별한다.

### 2.2 조사 방식 3종 (`RESEARCH_MODE`)

`ENABLE_TOOL_CALLING=True`일 때만 의미가 있으며, `agents/config.py`에서 설정하거나 env로 덮어쓴다.

```python
RESEARCH_MODE = os.getenv("RESEARCH_MODE", "hybrid")   # 기본값
```

| 모드 | 조사 시점 | 발언 중 도구 | 특징 |
|---|---|---|---|
| `per_step` | 발언(argue/rebut)마다 **필수** 조사 | 사용 | 근거 두툼·균형, 비용 높음 |
| `upfront` | 토론 시작 전 각 측 **1회** 통합 조사 | 미사용 | 비용 최저, 근거 얕음 |
| **`hybrid`(기본)** | upfront 1회 + **rebut에서만** 선택적 추가 조사 | rebut만 | 균형, 비용 중간 |

- **per_step**: `analyst._run_llm`이 발언 직전 `_research_with_tools`로 조사 후, 도구 없이 최종 발언 생성.
- **upfront**: orchestrator `_run_upfront_research`가 토론 전 Bull/Bear를 **병렬**로 각 1회 조사(`analyst.research`) → 결과 기사를 `articles_by_side`에 채워 이후 라운드에 재사용. 발언은 도구 없이 생성.
- **hybrid**: upfront로 근거를 깔아두고, **argue는 그 근거만 사용**(`can_top_up=False`), **rebut만** 상대 논점 반박을 위해 추가 조사 허용(`can_top_up=True`). 모델이 "선택" 조사를 자제하지 않아 코드(action 분기)로 제한했다.

> off-path 보존: `ENABLE_TOOL_CALLING=False`면 기존처럼 `expand_query` 기반 스탠스별 pre-fetch로 동작한다.

### 2.3 비용/품질 가드 (`config.py`)

```python
TOOL_MAX_ROUNDS_PER_STEP   = 2     # 한 발언 내 tool-call 왕복 최대
TOOL_MAX_CALLS_PER_STEP    = 4     # 한 발언 내 실제 실행 tool call 최대
TOOL_SEARCH_TOP_K_MAX      = 3     # 검색 기사 수 상한
TOOL_SEARCH_MIN_SCORE      = 0.50  # 유사도 미만 결과 제외
TOOL_MAX_ARTICLES_PER_SIDE = 12    # 사이드바 보관 기사 상한
```

### 2.4 모드 비교 실측 (`compare_research_modes.py`, 주제: 삼성전자)

| 지표 | per_step | upfront | hybrid |
|---|---|---|---|
| 조사 도구 호출 | 22 | 7 | ~15 |
| 소요 시간 | 44.5s | 30.7s | (편차 큼) |
| Bull / Bear 조사 기사 | 10 / 12 | 6 / 2 | 12 / 9 |
| 최종 판단 | 분할 매수 | 분할 매수 | 분할 매수 |

- 순수 `upfront`는 가장 싸지만 Bear 근거가 2건으로 빈약·불균형.
- `hybrid`가 근거 균형(12/9)을 회복하면서 per_step보다 호출 수를 줄임 → **기본값으로 채택**.
- 라운드가 길어질수록 per_step 비용은 step 수에 비례해 증가, upfront/hybrid는 상대적으로 완만.

실행:
```bash
RESEARCH_MODE=per_step python compare_research_modes.py per_step 삼성전자
RESEARCH_MODE=upfront  python compare_research_modes.py upfront  삼성전자
RESEARCH_MODE=hybrid   python compare_research_modes.py hybrid   삼성전자
```

> 주의: `agents/__init__.py`가 orchestrator를 eager import하므로, 실험 시 모드는 **import 전에 env로** 주입해야 한다(파이썬 모듈이 import 시점에 `RESEARCH_MODE` 값을 바인딩하기 때문).

---

## 3. 유저 페르소나 — 설문 기반 독자 맞춤

### 3.1 전체 흐름

```
프론트 6문항 설문
   │  POST /api/debate {topic, survey}
   ▼
main.py → orchestrator.run(survey=...)
   │
   ├─ ProfilerAgent.profile(survey)  ── LLM 1회 ──▶ "독자 맞춤 작성 지침" 문자열
   ├─ resolve_persona_tier(survey)   ── 규칙 ──────▶ tier (beginner/intermediate/expert)
   ▼
프로필 문자열 → _persona_block 으로 Bull/Bear/Moderator 프롬프트에 주입
tier            → few-shot 변형(쉬운/dense) 선택
   ▼
Moderator 결론에 면책 고지 자동 추가
```

### 3.2 설문 (6문항)

`frontend/.../InputScreen.tsx`에서 수집, `{gender, age, experience, level, terminology, depth}` 형태로 전송.

| 필드 | 질문 | 선택지 |
|---|---|---|
| gender | 성별 | 남성 / 여성 / 응답 안 함 |
| age | 나이대 | 20대 이하 / 30대 / 40대 / 50대 이상 |
| experience | 투자 기간 | 1년 미만 / 1~3년 / 3~7년 / 7년 이상 |
| level | 개인 수준 | 입문자 / 개인투자자 / 전문가 |
| terminology | 용어 숙지 | 낮음 / 보통 / 높음 |
| depth | 설명 깊이 | 쉽고 간단 / 균형 / 심층·정밀 |

### 3.3 프로파일러 (`agents/profiler.py`)

- `ProfilerAgent.profile(survey)` → 설문을 읽고 "독자 맞춤 작성 지침"(불릿 3~5개) 문자열을 LLM으로 1회 생성.
- 프롬프트(`build_profile_prompt`)에 명시된 규칙:
  - **지식 필드**(투자기간·자가수준·용어숙지·설명깊이) → 설명 깊이·용어 풀이·분석 밀도 결정.
  - **나이대** → 톤·예시에만 가볍게 반영.
  - **성별** → 분석 내용·투자 판단·결론에 **절대 영향 금지**(편향 방지). 사용자 결정 사항.

### 3.4 프로필 주입 (`agents/prompts.py`)

- `_persona_block(user_persona)`: 지시형 블록("독자 맞춤 작성 지침 (필수)")으로 주입. 프리셋 키(입문자/개인투자자/전문가)면 `PERSONA_PROFILES`로 확장, 아니면 자유형 문자열(프로파일러 출력) 그대로 사용.
- `_persona_directive(user_persona)`: argue/rebut/conclude/moderator **지시부 끝**에 "독자 수준에 맞춰 용어·설명 깊이를 조절하되, 분석·결론·수치는 동일하게 유지" 리마인더 추가.

### 3.5 tier 기반 few-shot (C1)

few-shot 예시가 곧 답변 "문체 선생님"이므로, 입문자에게는 예시 자체를 바꾼다.

- `resolve_persona_tier(user_persona, survey)`: 설문이 있으면 규칙으로, 없으면 프리셋 키(`PRESET_TIER`)로 tier 산출.
  - `beginner`: level=입문자 또는 terminology=낮음 또는 depth=쉽고 간단
  - `expert`: level=전문가 또는 terminology=높음
  - 그 외 `intermediate`
- `_few_shot_argue(role, tier)` / `_few_shot_rebut(tier)`:
  - `tier == "beginner"` → **쉬운 설명 버전**(`_FEW_SHOT_*_PLAIN`: 용어 괄호 풀이, 첫째/둘째 구조, "쉽게 말해" 재진술)
  - 그 외 → 기존 dense 애널리스트 예시
- tier는 `orchestrator.run` → `_run_round`/`_run_dynamic_rounds` → `analyst.run_action` → `build_argue/rebut_prompt`로 전달된다.

### 3.6 페르소나 강도 튜닝 경과 (입문자 기준)

| 단계 | 결과 |
|---|---|
| 튜닝 전 | 빽빽, `이익 모멘텀`·`밸류에이션` 풀이 없이 사용 |
| A+B (지시형 블록 + 지시부 리마인더) | 첫째/둘째 구조·설명형 어투 등장, 단 전문용어는 여전 |
| **C1 (tier별 쉬운 few-shot)** | 전문용어 제거(→ "이익 증가 추세"), "쉽게 말해 ~" 재진술, 용어를 뜻으로 풀이 |

### 3.7 기타 결정

- **역할 레이블 비활성**: persona 켜질 때 메시지 앞에 `[매수(Bull) 측 주장]`을 붙이던 `_inject_context`는 UI 말풍선/CLI가 이미 Bull/Bear를 표시해 **중복**이므로 호출하지 않는다(함수는 남아있음).
- **면책 고지**: persona 설정 시 Moderator 결론 뒤에 `_inject_disclaimer`로 투자 책임 고지를 추가한다.

---

## 4. 환각 방지 가드 (Hallucination Guards)

### 4.1 동기

gpt-4o-mini는 답변 생성 시 (a) 데이터에 없는 수치를 **지어내거나(날조)**, (b) 두 수치를 **잘못 연결(오귀속)** 하거나(예: 목표가 59만원에 다른 목표가의 상승률 18.4%를 갖다붙임), (c) 근거 없는 **인과 비약**을 한다. 이를 줄이기 위해 *결정적(규칙 기반) 검증* + *LLM 자기검토*를 결합했다.

### 4.2 결정적 숫자검증기 (`agents/verifier.py`)

```python
verify_numbers(content, source) -> list[str]   # source에서 못 찾은 수치 목록
```

- 출력(content)에서 금융 수치(`%`·`배`·`원`·`만원`·`조원` 등)를 추출해 입력 데이터(source)와 **콤마 무시 문자열로 대조**, 못 찾은 수치를 돌려준다.
- 의미 없는 잡음(목록번호·연도, 단위 없는 한 자리 수)은 제외하고 중복을 제거한다.
- **LLM 비용 0, 오탐 0**(존재 여부만 판정). → **날조 수치**를 안정적으로 잡는다.
- 한계: *짝오류*(두 값 모두 데이터에 존재)·*인과비약*은 못 잡는다 → 이는 Reflection(LLM)이 담당.
- `analyst._reflect`가 Reflection 직전에 호출해, 못 찾은 수치를 reflection 프롬프트에 **결정적 근거**로 주입하고(`_num_check_block`) `[NumCheck]` 로그를 남긴다.

### 4.3 Self-Reflection (`config.ENABLE_REFLECTION=True`)

- 이전엔 **OFF**였다. 활성화하면서 버그도 고쳤다: 기존엔 `_reflect`에 **research가 빠진 원본 prompt**를 넘겨, tool로 정당하게 조사한 수치를 환각으로 **오판**했다. 이제 `_run_llm`이 실제 사용한 프롬프트(조사 결과 포함)를 함께 반환해 `_reflect`에 전달한다.
- 검토 기준 4개: **할루시네이션**(수치/사실이 데이터에 있나) · **역할 일관성** · **근거 인용** · **논리 비약**(데이터에 없는 인과 연결 금지).
- 비용: argue/rebut마다 LLM 1회 추가.

### 4.4 보조 가드

- **base-RAG 유사도 하한** `RAG_MIN_SCORE=0.35` (`retriever.search(min_score=)`). 저관련 롱테일 기사를 근거에서 제외. 전부 미달이면 토론이 깨지지 않게 `top_k`를 유지하는 fallback 포함. *단 "on-topic이지만 한 주제로 쏠림"은 못 고친다.*
- **argue/rebut 온도 0.7 → 0.4** (날조 경향 감소).

### 4.5 시도 후 폐기 — faithfulness 중심 Reflection

초안을 *사실 vs 해석*으로 나눠 사실만 증거 대조하고 오귀속까지 잡는 방식을 시도했다. 오귀속(59만원/18.4%)·날조는 잘 잡았으나, **gpt-4o-mini가 토론의 본질인 미래 전망·리스크 추론**("재평가 위험", "둔화 우려")을 환각으로 **over-flag** → Bear 측이 매 턴 REVISE되며 체계적으로 약화됐다. "전망/리스크/해석은 검사 제외" 명시 + 보수 편향 + 스코프 축소까지 **3회 튜닝해도 실패** → mini의 한계로 판단하고 폐기했다.

> 교훈: **약한 생성기 + 비싼 LLM 판정기**보다 **생성기 자체를 gpt-4o로 격상**하는 편이 합리적이다(판정기는 큰 input_prompt 전체를 읽어 오히려 더 비쌀 수 있음). 결정적 숫자검증기는 어떤 생성기든 싸게 유지할 가치가 있다.

---

## 5. 파일별 변경 요약

| 파일 | 변경 |
|---|---|
| `agents/config.py` | `RESEARCH_MODE`(env), tool 가드, `TEMPERATURE["profiler"]`, `ENABLE_REFLECTION=True`, `RAG_MIN_SCORE`, argue/rebut 온도 0.4 |
| `agents/tools.py` | 도구 스키마·`dispatch`·`cache_key` (방어/필터 포함) |
| `agents/base_agent.py` | `_chat_with_tools`, `_research_with_tools`(조사 전용 루프) |
| `agents/analyst.py` | `research()`(upfront), `_run_llm`(모드/`can_top_up` 분기, 사용 프롬프트 반환), `_reflect`(숫자검증+research 근거 검토), persona_tier 전달 |
| `agents/orchestrator.py` | `_run_upfront_research`, `_merge_sides`, 프로파일러·persona_tier 배선, 면책고지 주입, base-RAG `min_score` 배선 |
| `agents/verifier.py` | **신규** 결정적 숫자검증기 (`verify_numbers`) |
| `agents/profiler.py` | **신규** `ProfilerAgent` |
| `agents/prompts.py` | 모드/액션별 `_tools_block`, `build_research_prompt`, `_persona_block`(지시형·키겸용), `_persona_directive`, `build_profile_prompt`, tier·쉬운 few-shot, `resolve_persona_tier`, `build_reflection_prompt`(4기준+`_num_check_block`) |
| `rag/retriever.py` | `search(min_score=)` 유사도 하한(fallback 포함) |
| `agents/moderator.py` | persona 인지 |
| `main.py` | `DebateRequest {topic, survey}` |
| `test_debate.py` | CLI `[topic] [persona]` |
| `frontend/.../InputScreen.tsx` | 6문항 설문 UI |
| `frontend/.../App.tsx` | `{topic, survey}` 전송 |
| `compare_research_modes.py` | **신규** 모드 비교 실험 러너 |

---

## 6. 실행 / 토글

```bash
# CLI (프리셋 키로 페르소나)
python test_debate.py 삼성전자 입문자

# 조사 모드 전환
RESEARCH_MODE=upfront python test_debate.py 삼성전자

# API
uvicorn main:app --reload --port 8000   # POST /api/debate {topic, survey}
```

주요 플래그(`config.py`): `ENABLE_TOOL_CALLING`, `RESEARCH_MODE`, `ENABLE_DYNAMIC_ROUNDS`, `ENABLE_FEW_SHOT`, `ENABLE_REFLECTION`, `RAG_MIN_SCORE`.

---

## 7. 알려진 한계 / TODO

- 페르소나 적응은 argue/rebut에서 A+B+C1로 크게 개선됐으나, 셀사이드 애널리스트 system prompt의 영향으로 **수치 밀도는 여전히 다소 높을 수 있다**.
- `upfront` 단독은 한 측 근거가 빈약해질 수 있다(그래서 기본은 hybrid).
- 프론트는 `node_modules` 미설치 상태로 **tsc/빌드 미검증**.
- `tier`는 설문 규칙 기반이라 자가신고가 부정확하면 어긋날 수 있다(안전하게 beginner 우선 판정).
- 환각 가드는 **날조 수치**를 결정적으로 잡지만, **짝오류·인과비약**은 Reflection(LLM)에 의존하며 완벽하지 않다. 더 강한 가드가 필요하면 생성기를 `gpt-4o`로 격상하는 편이 LLM 판정기 추가보다 합리적이다(§4.5).
- Reflection은 argue/rebut마다 LLM 호출 1회를 추가한다(비용/지연 ↑).
- `RAG_MIN_SCORE`는 저관련 기사는 거르지만, 검색 결과가 한 주제로 쏠리는 문제(예: "삼성전자" → 노사 기사 편중)는 해결하지 못한다.
