"""
Bull vs Bear AI 토론
실행: streamlit run streamlit_app.py
"""

import datetime
import streamlit as st
from agents.orchestrator import DebateOrchestrator

st.set_page_config(
    page_title="Bull vs Bear AI",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ── CSS ──────────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');

/* ── 기본 리셋 ── */
header[data-testid="stHeader"] { display:none; }
#MainMenu { display:none; }
footer { display:none; }
.stApp { background-color:#000000; color:#ffffff; font-family:'Inter',sans-serif; }
.block-container { padding: 2rem 2rem 2rem 2rem !important; max-width:100% !important; }
div[data-testid="stVerticalBlock"] > div { gap: 0 !important; }

/* ── 버튼 기본 리셋 ── */
.stButton > button {
    background: rgba(255,255,255,0.05);
    color: #94a3b8;
    border: 1px solid rgba(255,255,255,0.1);
    border-radius: 10px;
    font-family: 'Inter', sans-serif;
    font-size: 14px;
    transition: all 0.2s;
    width: 100%;
}
.stButton > button:hover {
    background: rgba(255,255,255,0.1);
    border-color: rgba(255,255,255,0.2);
    color: #ffffff;
}

/* ── 입력창 ── */
.stTextInput > div > div > input {
    background: rgba(255,255,255,0.05) !important;
    color: #ffffff !important;
    border: 1px solid rgba(255,255,255,0.1) !important;
    border-radius: 12px !important;
    font-size: 16px !important;
    font-family: 'Inter', sans-serif !important;
    padding: 14px 16px !important;
}
.stTextInput > div > div > input:focus {
    border-color: rgba(16,185,129,0.5) !important;
    box-shadow: 0 0 0 2px rgba(16,185,129,0.15) !important;
}
.stTextInput > div > div > input::placeholder { color:#64748b !important; }
.stTextInput label { display:none !important; }

/* ── Analyze 버튼 ── */
.btn-analyze > button {
    background: linear-gradient(135deg, #10b981, #059669) !important;
    color: #ffffff !important;
    border: none !important;
    border-radius: 10px !important;
    font-weight: 600 !important;
    font-size: 15px !important;
    height: 52px !important;
}
.btn-analyze > button:hover { opacity: 0.9 !important; }

/* ── 배지 ── */
.badge-platform {
    display:inline-flex; align-items:center; gap:6px;
    background:rgba(255,255,255,0.05);
    border:1px solid rgba(255,255,255,0.1);
    border-radius:9999px;
    padding:6px 14px;
    font-size:13px; color:#94a3b8;
    margin-bottom:20px;
}

/* ── 히어로 타이틀 ── */
.hero-title {
    display:flex; align-items:center; justify-content:center;
    gap:16px; margin-bottom:12px;
}
.hero-icon-bull {
    width:64px; height:64px; border-radius:16px;
    background:linear-gradient(135deg,#10b981,#059669);
    display:flex; align-items:center; justify-content:center;
    font-size:28px;
    box-shadow: 0 0 30px rgba(16,185,129,0.4);
}
.hero-icon-bear {
    width:64px; height:64px; border-radius:16px;
    background:linear-gradient(135deg,#f43f5e,#e11d48);
    display:flex; align-items:center; justify-content:center;
    font-size:28px;
    box-shadow: 0 0 30px rgba(244,63,94,0.4);
}
.hero-bull-text {
    font-size:52px; font-weight:700;
    background:linear-gradient(135deg,#10b981,#34d399);
    -webkit-background-clip:text; -webkit-text-fill-color:transparent;
}
.hero-divider { font-size:40px; color:rgba(255,255,255,0.2); font-weight:100; }
.hero-bear-text {
    font-size:52px; font-weight:700;
    background:linear-gradient(135deg,#f43f5e,#fb7185);
    -webkit-background-clip:text; -webkit-text-fill-color:transparent;
}

/* ── Popular 카드 ── */
.popular-card {
    background:rgba(255,255,255,0.05);
    border:1px solid rgba(255,255,255,0.1);
    border-radius:12px;
    padding:16px 20px;
    cursor:pointer;
    transition:all 0.2s;
    height:100px;
}
.popular-card:hover {
    background:rgba(255,255,255,0.08);
    border-color:rgba(255,255,255,0.2);
}
.popular-ticker {
    font-size:16px; font-weight:700; color:#ffffff;
    display:flex; align-items:center; gap:8px; margin-bottom:4px;
}
.popular-dot { width:8px; height:8px; border-radius:50%; background:#10b981; display:inline-block; }
.popular-name { font-size:13px; color:#94a3b8; margin-bottom:6px; }
.popular-topic { font-size:12px; color:#64748b; }

/* ── 배경 글로우 ── */
.bg-glow-wrap {
    position:fixed; top:0; left:0; width:100%; height:100%;
    pointer-events:none; z-index:0; overflow:hidden;
}
.bg-glow-bull {
    position:absolute; top:10%; left:15%;
    width:400px; height:400px; border-radius:50%;
    background:radial-gradient(circle, rgba(16,185,129,0.06) 0%, transparent 70%);
}
.bg-glow-bear {
    position:absolute; top:20%; right:15%;
    width:400px; height:400px; border-radius:50%;
    background:radial-gradient(circle, rgba(244,63,94,0.06) 0%, transparent 70%);
}

/* ── 토론 헤더 ── */
.debate-header { padding:16px 0 12px 0; }
.debate-title { font-size:22px; font-weight:700; color:#ffffff; margin-bottom:4px; }
.debate-subtitle { font-size:13px; color:#64748b; }
.score-card {
    display:inline-flex; align-items:center; gap:8px;
    border-radius:10px; padding:8px 14px;
}
.score-bull { background:rgba(16,185,129,0.1); border:1px solid rgba(16,185,129,0.2); }
.score-bear { background:rgba(244,63,94,0.1); border:1px solid rgba(244,63,94,0.2); }
.score-label { font-size:11px; color:#64748b; font-weight:500; }
.score-val-bull { font-size:18px; font-weight:700; color:#10b981; }
.score-val-bear { font-size:18px; font-weight:700; color:#f43f5e; }
.live-badge {
    display:inline-flex; align-items:center; gap:6px;
    background:rgba(16,185,129,0.1);
    border:1px solid rgba(16,185,129,0.2);
    border-radius:9999px; padding:5px 12px;
    font-size:12px; color:#10b981; font-weight:500;
}
.live-dot { width:6px; height:6px; border-radius:50%; background:#10b981; }

/* ── 채팅 메시지 ── */
.msg-bull-header {
    font-size:11px; font-weight:600; color:#10b981;
    letter-spacing:0.08em; text-transform:uppercase;
    margin-bottom:6px; display:flex; align-items:center; gap:8px;
}
.msg-bear-header {
    font-size:11px; font-weight:600; color:#f43f5e;
    letter-spacing:0.08em; text-transform:uppercase;
    margin-bottom:6px; display:flex; align-items:center; gap:8px;
    justify-content:flex-end;
}
.msg-time { color:#475569; font-weight:400; }
.bubble-bull {
    background:linear-gradient(135deg,rgba(16,185,129,0.15),rgba(16,185,129,0.08));
    border:1px solid rgba(16,185,129,0.2);
    border-radius:4px 16px 16px 16px;
    padding:14px 18px; max-width:70%;
    font-size:14px; line-height:1.65; color:#d1fae5;
    box-shadow:0 0 20px rgba(16,185,129,0.08);
}
.bubble-bear {
    background:linear-gradient(135deg,rgba(244,63,94,0.15),rgba(244,63,94,0.08));
    border:1px solid rgba(244,63,94,0.2);
    border-radius:16px 4px 16px 16px;
    padding:14px 18px; max-width:70%;
    margin-left:auto;
    font-size:14px; line-height:1.65; color:#ffe4e6;
    box-shadow:0 0 20px rgba(244,63,94,0.08);
}
.agent-icon-bull {
    width:36px; height:36px; border-radius:10px; flex-shrink:0;
    background:linear-gradient(135deg,#10b981,#059669);
    display:inline-flex; align-items:center; justify-content:center;
    font-size:16px;
    box-shadow:0 0 12px rgba(16,185,129,0.4);
}
.agent-icon-bear {
    width:36px; height:36px; border-radius:10px; flex-shrink:0;
    background:linear-gradient(135deg,#f43f5e,#e11d48);
    display:inline-flex; align-items:center; justify-content:center;
    font-size:16px;
    box-shadow:0 0 12px rgba(244,63,94,0.4);
}
.round-divider {
    text-align:center; font-size:11px; color:#334155;
    margin:16px 0 12px 0; letter-spacing:0.05em;
}
.tag-row { display:flex; flex-wrap:wrap; gap:5px; margin-top:10px; }
.tag-bull {
    background:rgba(16,185,129,0.1); border:1px solid rgba(16,185,129,0.2);
    border-radius:6px; padding:2px 8px; font-size:11px; color:#6ee7b7;
}
.tag-bear {
    background:rgba(244,63,94,0.1); border:1px solid rgba(244,63,94,0.2);
    border-radius:6px; padding:2px 8px; font-size:11px; color:#fda4af;
}

/* ── Moderator ── */
.moderator-wrap {
    background:rgba(255,255,255,0.03);
    border:1px solid rgba(255,255,255,0.08);
    border-radius:16px; padding:20px 24px; margin-top:24px;
}
.moderator-title {
    font-size:13px; font-weight:600; color:#64748b;
    text-transform:uppercase; letter-spacing:0.08em; margin-bottom:14px;
    display:flex; align-items:center; gap:8px;
}
.verdict-badge {
    display:inline-block; border-radius:9999px;
    padding:5px 16px; font-size:13px; font-weight:700; margin-top:10px;
}
.verdict-buy   { background:rgba(16,185,129,0.15); color:#10b981; border:1px solid rgba(16,185,129,0.3); }
.verdict-split { background:rgba(59,130,246,0.15); color:#3b82f6; border:1px solid rgba(59,130,246,0.3); }
.verdict-watch { background:rgba(234,179,8,0.15);  color:#eab308; border:1px solid rgba(234,179,8,0.3);  }
.verdict-sell  { background:rgba(244,63,94,0.15);  color:#f43f5e; border:1px solid rgba(244,63,94,0.3);  }

/* ── 소스 사이드바 ── */
.source-header {
    display:flex; align-items:center; gap:10px;
    padding-bottom:12px;
    border-bottom:1px solid rgba(255,255,255,0.06);
    margin-bottom:14px;
}
.source-icon {
    width:36px; height:36px; border-radius:10px;
    background:rgba(255,255,255,0.06);
    display:flex; align-items:center; justify-content:center; font-size:16px;
}
.source-title { font-size:15px; font-weight:600; color:#ffffff; }
.source-count { font-size:12px; color:#64748b; }
.article-card {
    background:rgba(255,255,255,0.03);
    border:1px solid rgba(255,255,255,0.07);
    border-radius:12px; padding:12px 14px; margin-bottom:10px;
    transition:all 0.2s;
}
.article-card:hover { background:rgba(255,255,255,0.06); }
.article-title {
    font-size:13px; font-weight:500; color:#e2e8f0;
    line-height:1.4; margin-bottom:6px;
}
.article-title a { color:#e2e8f0; text-decoration:none; }
.article-title a:hover { color:#ffffff; text-decoration:underline; }
.article-meta { font-size:11px; color:#475569; margin-bottom:8px; }
.agent-badge-bull {
    display:inline-block; background:rgba(16,185,129,0.1);
    border:1px solid rgba(16,185,129,0.2);
    border-radius:9999px; padding:2px 10px;
    font-size:11px; color:#10b981; font-weight:500;
}
.agent-badge-bear {
    display:inline-block; background:rgba(244,63,94,0.1);
    border:1px solid rgba(244,63,94,0.2);
    border-radius:9999px; padding:2px 10px;
    font-size:11px; color:#f43f5e; font-weight:500;
}
.agent-badge-shared {
    display:inline-block; background:rgba(59,130,246,0.1);
    border:1px solid rgba(59,130,246,0.2);
    border-radius:9999px; padding:2px 10px;
    font-size:11px; color:#3b82f6; font-weight:500;
}
.source-stats {
    display:grid; grid-template-columns:1fr 1fr 1fr;
    gap:8px; margin-top:16px;
    border-top:1px solid rgba(255,255,255,0.06); padding-top:14px;
}
.stat-box {
    background:rgba(255,255,255,0.03);
    border:1px solid rgba(255,255,255,0.07);
    border-radius:10px; padding:10px; text-align:center;
}
.stat-label { font-size:11px; color:#475569; margin-bottom:4px; }
.stat-val-bull { font-size:18px; font-weight:700; color:#10b981; }
.stat-val-shared { font-size:18px; font-weight:700; color:#3b82f6; }
.stat-val-bear { font-size:18px; font-weight:700; color:#f43f5e; }

/* ── 하단 푸터 닷 ── */
.footer-dots {
    display:flex; justify-content:center; align-items:center;
    gap:24px; margin-top:32px;
    font-size:13px; color:#475569;
}
.dot-green { width:7px; height:7px; border-radius:50%; background:#10b981; display:inline-block; margin-right:6px; }
.dot-blue  { width:7px; height:7px; border-radius:50%; background:#3b82f6; display:inline-block; margin-right:6px; }
.dot-amber { width:7px; height:7px; border-radius:50%; background:#eab308; display:inline-block; margin-right:6px; }

/* ── 구분선 ── */
.divider { border:none; border-top:1px solid rgba(255,255,255,0.06); margin:16px 0; }

/* ── 돌아가기 버튼 ── */
.btn-back > button {
    background:rgba(255,255,255,0.05) !important;
    border:1px solid rgba(255,255,255,0.1) !important;
    color:#94a3b8 !important;
    border-radius:10px !important;
    font-size:13px !important;
    padding:6px 14px !important;
}
.btn-back > button:hover {
    background:rgba(255,255,255,0.1) !important;
    color:#ffffff !important;
}
</style>
""", unsafe_allow_html=True)


# ── 세션 초기화 ───────────────────────────────────────────
if "page"       not in st.session_state: st.session_state.page       = "setup"
if "chip_topic" not in st.session_state: st.session_state.chip_topic = ""
if "history"    not in st.session_state: st.session_state.history    = []

ROUNDS = 3

POPULAR = [
    {"ticker": "삼성전자",      "name": "Samsung Electronics", "topic": "반도체 HBM 수혜 지속성"},
    {"ticker": "SK하이닉스",    "name": "SK Hynix",            "topic": "AI 메모리 수요 전망"},
    {"ticker": "현대차",        "name": "Hyundai Motor",       "topic": "전기차 전환 가속화"},
    {"ticker": "LG에너지솔루션","name": "LG Energy Solution",  "topic": "배터리 시장 성장"},
]

VERDICT_SCORES = {
    "매수 적극": (8.5, 4.2),
    "분할 매수": (7.2, 5.8),
    "관망":      (5.5, 5.5),
    "매도 고려": (4.0, 7.8),
}


# ── 헬퍼 함수들 ───────────────────────────────────────────
def _now_str():
    return datetime.datetime.now().strftime("오후 %I:%M")


def _verdict_html(verdict: str) -> str:
    mapping = {
        "매수 적극": ("verdict-buy",   "🚀 매수 적극"),
        "분할 매수": ("verdict-split",  "📈 분할 매수"),
        "관망":      ("verdict-watch",  "👀 관망"),
        "매도 고려": ("verdict-sell",   "📉 매도 고려"),
    }
    css, text = mapping.get(verdict, ("verdict-watch", verdict))
    return f"<span class='verdict-badge {css}'>{text}</span>"


def _render_messages(result: dict):
    """라운드별 Bull/Bear 메시지 출력"""
    label_map = {1: "ROUND 1 · 정성 (기사)", 2: "ROUND 2 · 정량 (재무)", 3: "ROUND 3 · 통합"}

    for r_data in result["rounds"]:
        r = r_data["round"]
        bull = r_data["bull"]
        bear = r_data["bear"]

        st.markdown(
            f"<div class='round-divider'>── {label_map.get(r, f'ROUND {r}')} ──</div>",
            unsafe_allow_html=True,
        )

        bull_tags = "".join(f"<span class='tag-bull'>{t}</span>" for t in bull.get("tags", []))
        bear_tags = "".join(f"<span class='tag-bear'>{t}</span>" for t in bear.get("tags", []))

        # Bull 메시지
        st.markdown(
            f"<div style='display:flex;gap:10px;align-items:flex-start;margin-bottom:16px;'>"
            f"<div class='agent-icon-bull'>📈</div>"
            f"<div style='flex:1;'>"
            f"<div class='msg-bull-header'>BULL ANALYSIS <span class='msg-time'>• {_now_str()}</span></div>"
            f"<div class='bubble-bull'>{bull.get('content','')}"
            f"<div class='tag-row'>{bull_tags}</div></div>"
            f"</div></div>",
            unsafe_allow_html=True,
        )

        # Bear 메시지
        st.markdown(
            f"<div style='display:flex;gap:10px;align-items:flex-start;margin-bottom:16px;flex-direction:row-reverse;'>"
            f"<div class='agent-icon-bear'>📉</div>"
            f"<div style='flex:1;'>"
            f"<div class='msg-bear-header'>BEAR ANALYSIS <span class='msg-time'>• {_now_str()}</span></div>"
            f"<div class='bubble-bear'>{bear.get('content','')}"
            f"<div class='tag-row' style='justify-content:flex-end;'>{bear_tags}</div></div>"
            f"</div></div>",
            unsafe_allow_html=True,
        )


def _render_moderator(mod: dict):
    verdict    = mod.get("verdict", "")
    bull_sum   = mod.get("bull_summary", "")
    bear_sum   = mod.get("bear_summary", "")
    conclusion = mod.get("conclusion", "")

    st.markdown(
        f"<div class='moderator-wrap'>"
        f"<div class='moderator-title'>⚖️ MODERATOR · 최종 결론</div>"
        f"<div style='font-size:13px;color:#94a3b8;margin-bottom:8px;'>"
        f"<span style='color:#10b981;font-weight:600;'>📈 Bull</span>&nbsp; {bull_sum}</div>"
        f"<div style='font-size:13px;color:#94a3b8;margin-bottom:8px;'>"
        f"<span style='color:#f43f5e;font-weight:600;'>📉 Bear</span>&nbsp; {bear_sum}</div>"
        f"<div style='font-size:13px;color:#cbd5e1;line-height:1.6;'>{conclusion}</div>"
        f"{_verdict_html(verdict)}"
        f"</div>",
        unsafe_allow_html=True,
    )


def _render_sources(articles: dict):
    """소스 사이드바 출력"""
    bull_list   = articles.get("bull", [])
    bear_list   = articles.get("bear", [])
    common_list = articles.get("common", [])

    all_articles = (
        [(a, "bull")   for a in bull_list] +
        [(a, "bear")   for a in bear_list] +
        [(a, "shared") for a in common_list]
    )

    total = len(all_articles)
    st.markdown(
        f"<div class='source-header'>"
        f"<div class='source-icon'>📊</div>"
        f"<div><div class='source-title'>Source Materials</div>"
        f"<div class='source-count'>{total} articles referenced</div></div>"
        f"</div>",
        unsafe_allow_html=True,
    )

    for a, kind in all_articles:
        title   = a.get("title", "")
        source  = a.get("source", "")
        pub     = (a.get("published_at") or "")[:10]
        url     = a.get("url") or ""
        score   = a.get("score", 0)

        title_html = (
            f"<a href='{url}' target='_blank'>{title}</a>"
            if url else title
        )
        badge = {
            "bull":   "<span class='agent-badge-bull'>Bull agent</span>",
            "bear":   "<span class='agent-badge-bear'>Bear agent</span>",
            "shared": "<span class='agent-badge-shared'>Shared</span>",
        }[kind]

        st.markdown(
            f"<div class='article-card'>"
            f"<div class='article-title'>{title_html}</div>"
            f"<div class='article-meta'>📅 {pub} · {source} · 유사도 {score:.2f}</div>"
            f"{badge}"
            f"</div>",
            unsafe_allow_html=True,
        )

    # 하단 통계
    st.markdown(
        f"<div class='source-stats'>"
        f"<div class='stat-box'><div class='stat-label'>Bull Sources</div>"
        f"<div class='stat-val-bull'>{len(bull_list)}</div></div>"
        f"<div class='stat-box'><div class='stat-label'>Shared</div>"
        f"<div class='stat-val-shared'>{len(common_list)}</div></div>"
        f"<div class='stat-box'><div class='stat-label'>Bear Sources</div>"
        f"<div class='stat-val-bear'>{len(bear_list)}</div></div>"
        f"</div>",
        unsafe_allow_html=True,
    )


# ════════════════════════════════════════════════════════
#  PAGE 1 — 검색 화면
# ════════════════════════════════════════════════════════
def page_setup():
    # 배경 글로우
    st.markdown(
        "<div class='bg-glow-wrap'>"
        "<div class='bg-glow-bull'></div>"
        "<div class='bg-glow-bear'></div>"
        "</div>",
        unsafe_allow_html=True,
    )

    # 중앙 컨테이너
    _, center, _ = st.columns([1, 2.5, 1])
    with center:
        # 상단 배지
        st.markdown(
            "<div style='text-align:center;margin-bottom:24px;'>"
            "<span class='badge-platform'>✨ AI-Powered Stock Analysis Platform</span>"
            "</div>",
            unsafe_allow_html=True,
        )

        # 히어로 타이틀
        st.markdown(
            "<div class='hero-title'>"
            "<div class='hero-icon-bull'>📈</div>"
            "<span class='hero-bull-text'>Bull</span>"
            "<span class='hero-divider'>|</span>"
            "<span class='hero-bear-text'>Bear</span>"
            "<div class='hero-icon-bear'>📉</div>"
            "</div>"
            "<div style='text-align:center;font-size:22px;font-weight:600;color:#e2e8f0;margin-bottom:10px;'>"
            "Dual-Perspective Investment Analysis</div>"
            "<div style='text-align:center;font-size:14px;color:#64748b;line-height:1.6;margin-bottom:32px;'>"
            "Advanced AI agents analyze both sides of your investment thesis,<br>"
            "providing comprehensive insights through structured debate and real-time market data"
            "</div>",
            unsafe_allow_html=True,
        )

        # 검색 입력 + Analyze 버튼
        input_col, btn_col = st.columns([5, 1])
        with input_col:
            topic = st.text_input(
                "",
                placeholder="종목명을 입력하세요  예) 삼성전자",
                key="topic_input",
                value=st.session_state.chip_topic,
            )
        with btn_col:
            st.markdown("<div class='btn-analyze'>", unsafe_allow_html=True)
            analyze_clicked = st.button("Analyze", key="start_btn", use_container_width=True)
            st.markdown("</div>", unsafe_allow_html=True)

        if analyze_clicked:
            if not topic.strip():
                st.error("종목명을 입력해주세요.")
            else:
                st.session_state.topic      = topic.strip()
                st.session_state.chip_topic = ""
                st.session_state.page       = "debate"
                st.session_state.pop("debate_result", None)
                st.rerun()

        # Popular Analyses
        st.markdown(
            "<div style='font-size:11px;font-weight:600;color:#475569;"
            "letter-spacing:0.1em;text-transform:uppercase;margin:28px 0 12px 0;'>"
            "POPULAR ANALYSES</div>",
            unsafe_allow_html=True,
        )

        col1, col2 = st.columns(2)
        for i, p in enumerate(POPULAR):
            col = col1 if i % 2 == 0 else col2
            with col:
                st.markdown(
                    f"<div class='popular-card'>"
                    f"<div class='popular-ticker'>{p['ticker']} <span class='popular-dot'></span></div>"
                    f"<div class='popular-name'>{p['name']}</div>"
                    f"<div class='popular-topic'>{p['topic']}</div>"
                    f"</div>",
                    unsafe_allow_html=True,
                )
                if st.button(p["ticker"], key=f"pop_{i}", use_container_width=True):
                    st.session_state.chip_topic = p["ticker"]
                    st.rerun()

        # 푸터
        st.markdown(
            "<div class='footer-dots'>"
            "<span><span class='dot-green'></span>Real-time Analysis</span>"
            "<span><span class='dot-blue'></span>Multi-source Data</span>"
            "<span><span class='dot-amber'></span>AI-Powered Insights</span>"
            "</div>",
            unsafe_allow_html=True,
        )

        # 이전 토론 히스토리
        if st.session_state.history:
            st.markdown("<hr class='divider'>", unsafe_allow_html=True)
            st.markdown(
                "<div style='font-size:11px;font-weight:600;color:#475569;"
                "letter-spacing:0.1em;text-transform:uppercase;margin-bottom:10px;'>"
                "RECENT ANALYSES</div>",
                unsafe_allow_html=True,
            )
            for h in st.session_state.history[:5]:
                st.markdown(
                    f"<div style='background:rgba(255,255,255,0.03);border:1px solid rgba(255,255,255,0.07);"
                    f"border-radius:10px;padding:10px 14px;margin-bottom:8px;font-size:13px;'>"
                    f"<span style='color:#e2e8f0;font-weight:500;'>💬 {h['topic']}</span>"
                    f"<span style='color:#475569;font-size:12px;margin-left:10px;'>{h['date']}</span>"
                    f"</div>",
                    unsafe_allow_html=True,
                )


# ════════════════════════════════════════════════════════
#  PAGE 2 — 토론 화면
# ════════════════════════════════════════════════════════
def page_debate():
    topic  = st.session_state.get("topic", "종목 분석")
    rounds = ROUNDS

    # ── 상단 헤더 ─────────────────────────────────────────
    h_col1, h_col2, h_col3 = st.columns([1, 5, 1.5])
    with h_col1:
        st.markdown("<div class='btn-back'>", unsafe_allow_html=True)
        if st.button("← Back to Search", key="back_btn"):
            st.session_state.page = "setup"
            st.rerun()
        st.markdown("</div>", unsafe_allow_html=True)

    with h_col3:
        st.markdown(
            "<div style='text-align:right;padding-top:4px;'>"
            "<span class='live-badge'><span class='live-dot'></span> Live Analysis</span>"
            "</div>",
            unsafe_allow_html=True,
        )

    # 제목
    st.markdown(
        f"<div class='debate-header'>"
        f"<div class='debate-title'>⚖️ {topic}</div>"
        f"<div class='debate-subtitle'>AI agents are conducting real-time debate analysis</div>"
        f"</div>",
        unsafe_allow_html=True,
    )

    st.markdown("<hr class='divider'>", unsafe_allow_html=True)

    # ── 토론 실행 / 결과 ──────────────────────────────────
    if "debate_result" not in st.session_state:
        with st.spinner(f"🤖 {topic} 토론 분석 중... (약 1~2분 소요)"):
            orchestrator = DebateOrchestrator()
            result = orchestrator.run(topic=topic, rounds=rounds)
        st.session_state.debate_result = result

        now = datetime.datetime.now().strftime("%m-%d %H:%M")
        entry = {"topic": topic, "date": now}
        if entry not in st.session_state.history:
            st.session_state.history.insert(0, entry)

    result  = st.session_state.debate_result
    verdict = result["moderator"].get("verdict", "관망")
    bull_score, bear_score = VERDICT_SCORES.get(verdict, (5.5, 5.5))

    # ── Bull/Bear 스코어 ──────────────────────────────────
    sc1, sc2, sc3 = st.columns([2, 1, 1])
    with sc2:
        st.markdown(
            f"<div class='score-card score-bull'>"
            f"<span style='font-size:18px;'>📈</span>"
            f"<div><div class='score-label'>Bull Score</div>"
            f"<div class='score-val-bull'>{bull_score}/10</div></div>"
            f"</div>",
            unsafe_allow_html=True,
        )
    with sc3:
        st.markdown(
            f"<div class='score-card score-bear'>"
            f"<span style='font-size:18px;'>📉</span>"
            f"<div><div class='score-label'>Bear Score</div>"
            f"<div class='score-val-bear'>{bear_score}/10</div></div>"
            f"</div>",
            unsafe_allow_html=True,
        )

    st.markdown("<br>", unsafe_allow_html=True)

    # ── 채팅 + 소스 2컬럼 ────────────────────────────────
    chat_col, source_col = st.columns([3, 1])

    with chat_col:
        _render_messages(result)
        _render_moderator(result["moderator"])

    with source_col:
        _render_sources(result["articles"])


# ── 라우터 ────────────────────────────────────────────────
if st.session_state.page == "setup":
    page_setup()
else:
    page_debate()
