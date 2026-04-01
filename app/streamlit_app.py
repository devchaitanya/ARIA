import sys
import os
import time
import json
import logging
import tempfile
import streamlit as st

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.orchestrator.graph import run_ingest, run_analysis
from src.agents.base_agent import Finding

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

st.set_page_config(page_title="ARIA — Code Review", page_icon="🤖", layout="centered")

SEVERITY_ICONS = {"critical": "🔴", "high": "🟠", "medium": "🟡", "low": "🟢"}
CATEGORY_ICONS = {
    "security": "🛡️", "quality": "🔧", "architecture": "🏗️",
    "performance": "⚡", "ai_slop": "🧹",
}

AGENT_OPTIONS = {
    "security":     {"label": "Security",       "icon": "🛡️", "desc": "OWASP Top 10, injection, secrets, auth",    "color": "#ef4444"},
    "quality":      {"label": "Code Quality",   "icon": "🔧", "desc": "Complexity, dead code, error handling",     "color": "#3b82f6"},
    "architecture": {"label": "Architecture",   "icon": "🏗️", "desc": "SOLID, coupling, layering, dependencies",  "color": "#f59e0b"},
    "performance":  {"label": "Performance",    "icon": "⚡", "desc": "Algorithms, N+1, memory, caching",         "color": "#22c55e"},
    "ai_slop":      {"label": "AI-Slop Detect", "icon": "🧹", "desc": "Over-abstraction, cargo-cult patterns",    "color": "#a855f7"},
}

# ── CSS ─────────────────────────────────────────────────────────────────
CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');
.stApp { font-family: 'Inter', sans-serif; }

/* ─ Hero ─ */
.hero { text-align:center; padding:2rem 0 1rem; }
.hero h1 {
    font-size:2.4rem; font-weight:800; margin:0; letter-spacing:-1px;
    background:linear-gradient(135deg,#6366f1,#a855f7,#ec4899);
    -webkit-background-clip:text; -webkit-text-fill-color:transparent;
}
.hero .sub { font-size:0.9rem; color:#8b949e; margin:0.35rem 0 0; }
.hero .badge {
    display:inline-block; margin-top:0.6rem; padding:0.25rem 0.85rem;
    background:rgba(99,102,241,0.1); border:1px solid rgba(99,102,241,0.22);
    border-radius:20px; font-size:0.72rem; color:#818cf8; font-weight:500;
}

/* ─ Live log ─ */
.live-log {
    background:#0d1117; border:1px solid #21262d; border-radius:10px;
    padding:0.8rem 1rem; max-height:320px; overflow-y:auto;
    font-family:'JetBrains Mono','Fira Code',monospace; font-size:0.78rem;
}
.log-row { display:flex; gap:0.6rem; padding:0.22rem 0; border-bottom:1px solid #161b22; animation:fadeIn .25s; }
.log-row:last-child { border-bottom:none; }
.log-t { color:#484f58; min-width:42px; flex-shrink:0; font-size:0.7rem; padding-top:1px; }
.log-m { color:#c9d1d9; line-height:1.4; }
.log-m.ok  { color:#3fb950; }
.log-m.run { color:#58a6ff; }
.log-m.err { color:#f85149; }
@keyframes fadeIn { from{opacity:0;transform:translateY(3px)} to{opacity:1;transform:translateY(0)} }
.live-log::-webkit-scrollbar { width:5px; }
.live-log::-webkit-scrollbar-track { background:#0d1117; }
.live-log::-webkit-scrollbar-thumb { background:#30363d; border-radius:3px; }

/* ─ Metric cards ─ */
.m-row { display:flex; gap:0.7rem; justify-content:center; flex-wrap:wrap; margin:1rem 0; }
.m-card {
    background:linear-gradient(145deg,#161b22,#1c2333); border:1px solid #30363d;
    border-radius:14px; padding:1rem 1.2rem; text-align:center; min-width:110px; flex:1;
    transition:border-color 0.2s;
}
.m-card:hover { border-color:#58a6ff; }
.m-card .m-label { font-size:0.65rem; font-weight:600; text-transform:uppercase; letter-spacing:0.8px; color:#8b949e; }
.m-card .m-val   { font-size:1.6rem; font-weight:700; color:#f0f6fc; margin:0.15rem 0; }
.m-card .m-sub   { font-size:0.7rem; color:#484f58; }

/* ─ Severity pills ─ */
.sev-pill { display:inline-block; padding:0.15rem 0.6rem; border-radius:20px; font-size:0.7rem; font-weight:600; text-transform:uppercase; letter-spacing:0.5px; }
.sev-critical { background:#490202; color:#ff7b72; border:1px solid #6e1010; }
.sev-high     { background:#3d1300; color:#ffa657; border:1px solid #6e3a0a; }
.sev-medium   { background:#3b2300; color:#e3b341; border:1px solid #6e5400; }
.sev-low      { background:#04260d; color:#56d364; border:1px solid #0e4a1e; }

/* ─ Agent tag ─ */
.a-tag { display:inline-block; background:#161b22; border:1px solid #30363d; border-radius:6px; padding:0.18rem 0.55rem; font-size:0.7rem; color:#8b949e; margin-right:0.3rem; }

/* ─ Section headings ─ */
.sec {
    font-size:1.12rem; font-weight:700; color:#f0f6fc; margin:1.6rem 0 0.7rem;
    padding-bottom:0.4rem; border-bottom:2px solid rgba(99,102,241,0.3);
}

/* ─ Agent card header ─ */
.ag-hdr { text-align:center; padding:0.3rem 0 0.15rem; }
.ag-hdr .ag-icon { font-size:1.8rem; line-height:1; }
.ag-hdr .ag-bar  { width:36px; height:3px; border-radius:2px; margin:0.45rem auto 0.1rem; }
.ag-hdr .ag-desc { font-size:0.7rem; color:#8b949e; line-height:1.35; margin-top:0.25rem; }

/* ─ Hide default metrics ─ */
div[data-testid="stMetric"] { display:none; }
</style>
"""


def main():
    st.markdown(CSS, unsafe_allow_html=True)
    st.markdown(
        '<div class="hero">'
        '<h1>🤖 ARIA</h1>'
        '<p class="sub">Adaptive Review Intelligence Architecture</p>'
        '<span class="badge">Multi-LLM Debate Protocol · 5 Specialist Agents</span>'
        '</div>',
        unsafe_allow_html=True,
    )

    # ── Session state ───────────────────────────────────────────────────
    for key in ("ingest_state", "review_state"):
        if key not in st.session_state:
            st.session_state[key] = None

    # ── Input row ───────────────────────────────────────────────────────
    c1, c2 = st.columns([4, 1])
    with c1:
        repo_url = st.text_input("Repository", placeholder="https://github.com/user/repo", label_visibility="collapsed")
    with c2:
        branch = st.text_input("Branch", value="main", label_visibility="collapsed")

    # ── Phase 1 button ──────────────────────────────────────────────────
    if st.button("🔍  Analyze Repository", use_container_width=True, type="primary"):
        st.session_state.review_state = None
        st.session_state.ingest_state = None
        _phase_ingest(repo_url, branch)

    # ── Render persisted ingest results ─────────────────────────────────
    state = st.session_state.ingest_state
    if state is not None and state.status != "failed":
        gs = state.graph_stats
        st.markdown(
            f'<div class="m-row">'
            f'<div class="m-card"><div class="m-label">Files</div><div class="m-val">{gs.get("total_files",0)}</div></div>'
            f'<div class="m-card"><div class="m-label">Functions</div><div class="m-val">{gs.get("functions",0)}</div></div>'
            f'<div class="m-card"><div class="m-label">Classes</div><div class="m-val">{gs.get("classes",0)}</div></div>'
            f'<div class="m-card"><div class="m-label">Graph Edges</div><div class="m-val">{gs.get("total_edges",0)}</div></div>'
            f'</div>',
            unsafe_allow_html=True,
        )

        if state.knowledge_graph is not None:
            _render_graph(state.knowledge_graph)

        # ── Agent selection cards (3 + 2 grid) ─────────────────────────
        st.markdown('<div class="sec">🤖 Select Review Agents</div>', unsafe_allow_html=True)

        selected = []
        keys = list(AGENT_OPTIONS.keys())

        for row_keys in [keys[:3], keys[3:]]:
            cols = st.columns(3)
            for i, key in enumerate(row_keys):
                info = AGENT_OPTIONS[key]
                with cols[i]:
                    with st.container(border=True):
                        st.markdown(
                            f'<div class="ag-hdr">'
                            f'<div class="ag-icon">{info["icon"]}</div>'
                            f'<div class="ag-bar" style="background:{info["color"]};"></div>'
                            f'<div class="ag-desc">{info["desc"]}</div>'
                            f'</div>',
                            unsafe_allow_html=True,
                        )
                        if st.checkbox(info["label"], value=True, key=f"agent_{key}"):
                            selected.append(key)

        if selected:
            if st.button(
                f"🚀  Run {len(selected)} Agent{'s' if len(selected) > 1 else ''}",
                use_container_width=True, type="primary",
            ):
                _phase_analyze(state, selected)
        else:
            st.warning("Select at least one agent.")

    # ── Render persisted review results ─────────────────────────────────
    if st.session_state.review_state is not None:
        _render_report(st.session_state.review_state)


# ── Helpers ──────────────────────────────────────────────────────────────

def _make_logger():
    bar = st.progress(0, text="Starting…")
    placeholder = st.empty()
    entries: list[dict] = []
    t0 = time.time()

    def _render():
        rows = "".join(
            f'<div class="log-row"><span class="log-t">{e["ts"]}</span>'
            f'<span class="log-m {e["c"]}">{e["m"]}</span></div>'
            for e in entries
        )
        placeholder.markdown(f'<div class="live-log">{rows}</div>', unsafe_allow_html=True)

    def log(stage: str, msg: str, pct: float):
        elapsed = time.time() - t0
        mins, secs = divmod(int(elapsed), 60)
        ts = f"{mins}:{secs:02d}"
        cls = "ok" if stage.endswith("_done") or stage in ("ingested", "debate_done", "complete") else (
            "err" if "error" in stage or "fail" in stage else "run"
        )
        entries.append({"ts": ts, "m": msg, "c": cls})
        bar.progress(min(pct, 1.0), text=msg)
        _render()

    return log, bar, t0


def _phase_ingest(repo_url: str, branch: str):
    """Phase 1 — clone, parse, build knowledge graph. Saves to session state."""
    if not repo_url or "github.com" not in repo_url:
        st.error("Please enter a valid GitHub repository URL.")
        return

    log, bar, t0 = _make_logger()
    try:
        state = run_ingest(repo_url, branch, on_progress=log)
    except Exception as e:
        log("error", f"❌ Ingestion failed: {e}", 1.0)
        return

    if state.status == "failed":
        st.error(state.error)
        return

    elapsed = time.time() - t0
    log("ingested", f"✅ Repository indexed in {elapsed:.1f}s — {len(state.files)} files, "
        f"{state.graph_stats.get('total_nodes', 0)} nodes", 0.18)

    st.session_state.ingest_state = state


def _phase_analyze(state, selected_categories: list[str]):
    """Phase 2 — run agents, debate, generate report. Saves to session state."""
    log, bar, t0 = _make_logger()
    log("start", f"🚀 Launching {len(selected_categories)} agents: {', '.join(selected_categories)}", 0.18)

    try:
        state = run_analysis(state, on_progress=log, selected_categories=selected_categories)
    except Exception as e:
        log("error", f"❌ Analysis failed: {e}", 1.0)
        return

    elapsed = time.time() - t0
    log("complete", f"✅ Review complete in {elapsed:.1f}s", 1.0)
    bar.progress(1.0, text=f"Done — {elapsed:.1f}s")

    if state.status == "failed":
        st.error(state.error)
        return

    st.session_state.review_state = state


# ── Graph visualization ─────────────────────────────────────────────────

def _render_graph(G):
    try:
        from pyvis.network import Network
    except ImportError:
        return

    st.markdown('<div class="sec">🔗 Knowledge Graph</div>', unsafe_allow_html=True)

    node_count = G.number_of_nodes()
    max_n = min(node_count, 250)
    show = st.slider("Nodes to show", 15, max_n, min(80, max_n), key="graph_nodes")

    ranked = sorted(G.nodes(), key=lambda n: G.degree(n), reverse=True)[:show]
    sub = set(ranked)

    NCOL = {"file": "#6366f1", "function": "#22d3ee", "class": "#f59e0b", "struct": "#f59e0b"}
    ECOL = {"defines": "#4b5563", "imports": "#3b82f6", "calls": "#ef4444"}

    net = Network(height="420px", width="100%", bgcolor="#0d1117", font_color="#c9d1d9", directed=True)
    net.barnes_hut(gravity=-2500, central_gravity=0.3, spring_length=100, spring_strength=0.04, damping=0.09)

    for node in sub:
        d = G.nodes[node]
        nt = d.get("type", "file")
        label = node.split("::")[-1] if "::" in node else (node.split("/")[-1] if "/" in node else node)
        sz = 8 + min(G.degree(node) * 2, 25)
        sh = "dot" if nt == "file" else ("diamond" if nt in ("class", "struct") else "triangle")
        net.add_node(node, label=label, title=f"{node}\n{nt} · {G.degree(node)} connections",
                     color=NCOL.get(nt, "#8b949e"), size=sz, shape=sh)

    for u, v, ed in G.edges(data=True):
        if u in sub and v in sub:
            rel = ed.get("relation", "")
            net.add_edge(u, v, title=rel, color=ECOL.get(rel, "#484f58"),
                         width=1.5 if rel == "calls" else 1, arrows="to")

    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".html", mode="w")
    net.save_graph(tmp.name)
    tmp.close()
    with open(tmp.name) as f:
        html = f.read()
    os.unlink(tmp.name)

    st.markdown(
        '<div style="display:flex;gap:1.2rem;font-size:0.75rem;color:#8b949e;margin-bottom:0.5rem;">'
        '<span>● <span style="color:#6366f1">File</span></span>'
        '<span>▲ <span style="color:#22d3ee">Function</span></span>'
        '<span>◆ <span style="color:#f59e0b">Class</span></span>'
        '<span style="margin-left:auto">— <span style="color:#3b82f6">imports</span></span>'
        '<span>— <span style="color:#ef4444">calls</span></span>'
        '<span>— <span style="color:#4b5563">defines</span></span></div>',
        unsafe_allow_html=True,
    )
    st.html(html, height=440)
    st.caption(f"{min(show, node_count)}/{node_count} nodes · {G.number_of_edges()} edges · drag & zoom to explore")


# ── Report rendering ────────────────────────────────────────────────────

def _render_report(state):
    report = state.report
    findings = state.verified_findings

    st.markdown('<div class="sec">📋 Review Report</div>', unsafe_allow_html=True)

    health = report.get("health_score", 0)
    slop = report.get("slop_score", 0)
    total = report.get("total_findings", 0)
    files_n = report.get("graph_stats", {}).get("total_files", 0)
    h_e = "🟢" if health >= 70 else ("🟡" if health >= 40 else "🔴")
    s_e = "🟢" if slop < 15 else ("🟡" if slop < 35 else "🔴")

    st.markdown(
        f'<div class="m-row">'
        f'<div class="m-card"><div class="m-label">Health</div><div class="m-val">{h_e} {health}</div><div class="m-sub">/100</div></div>'
        f'<div class="m-card"><div class="m-label">Slop Risk</div><div class="m-val">{s_e} {slop}%</div><div class="m-sub">lower = better</div></div>'
        f'<div class="m-card"><div class="m-label">Findings</div><div class="m-val">{total}</div><div class="m-sub">verified</div></div>'
        f'<div class="m-card"><div class="m-label">Files</div><div class="m-val">{files_n}</div><div class="m-sub">analyzed</div></div>'
        f'</div>',
        unsafe_allow_html=True,
    )

    col_l, col_r = st.columns(2)
    with col_l:
        st.markdown("**By Severity**")
        for sev in ["critical", "high", "medium", "low"]:
            cnt = report.get("by_severity", {}).get(sev, 0)
            if cnt:
                st.markdown(f'<span class="sev-pill sev-{sev}">{sev}</span> **{cnt}**', unsafe_allow_html=True)
    with col_r:
        st.markdown("**Agent Stats**")
        for agent, cnt in report.get("agent_stats", {}).items():
            st.markdown(f'<span class="a-tag">{agent}</span> {cnt} raw', unsafe_allow_html=True)

    st.markdown('<div class="sec">🔍 Findings</div>', unsafe_allow_html=True)

    tabs_data = []
    for sev in ["critical", "high", "medium", "low"]:
        items = [f for f in findings if f.severity == sev]
        if items:
            tabs_data.append((f"{SEVERITY_ICONS[sev]} {sev.upper()} ({len(items)})", items))

    if tabs_data:
        tabs = st.tabs([t[0] for t in tabs_data])
        for tab, (_, items) in zip(tabs, tabs_data):
            with tab:
                for f in items:
                    _render_finding(f)
    else:
        st.success("No significant findings — codebase looks healthy. 🎉")

    c1, c2 = st.columns(2)
    with c1:
        html_content = report.get("html", "")
        if html_content:
            st.download_button("📄 HTML Report", html_content, "aria_report.html", "text/html", use_container_width=True)
    with c2:
        json_data = {k: v for k, v in report.items() if k != "html"}
        st.download_button("📊 JSON", json.dumps(json_data, indent=2, default=str),
                           "aria_report.json", "application/json", use_container_width=True)


def _render_finding(f):
    sev = f.severity
    cat_icon = CATEGORY_ICONS.get(f.category, "📌")
    sev_icon = SEVERITY_ICONS.get(sev, "⚪")
    loc = f":{f.line}" if f.line else ""

    with st.expander(f"{sev_icon} {cat_icon} {f.title}  —  `{f.file}{loc}`  ({f.confidence:.0%})"):
        st.markdown(
            f'<span class="sev-pill sev-{sev}">{sev}</span> '
            f'<span class="a-tag">{f.agent}</span> <span class="a-tag">{f.category}</span>',
            unsafe_allow_html=True,
        )
        st.markdown(f.description)
        if f.suggestion:
            st.info(f"💡 **Suggestion:** {f.suggestion}")


if __name__ == "__main__":
    main()
