import sys
import os
import time
import json
import logging
import tempfile
import streamlit as st
import streamlit.components.v1 as components

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.orchestrator.graph import run_pipeline
from src.agents.base_agent import Finding

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

st.set_page_config(page_title="ARIA — Code Review", page_icon="🤖", layout="wide")

SEVERITY_COLORS = {"critical": "#DC2626", "high": "#EA580C", "medium": "#CA8A04", "low": "#16A34A"}
SEVERITY_ICONS = {"critical": "🔴", "high": "🟠", "medium": "🟡", "low": "🟢"}
CATEGORY_ICONS = {
    "security": "🛡️", "quality": "🔧", "architecture": "🏗️",
    "performance": "⚡", "ai_slop": "🧹",
}

# ── Custom CSS ──────────────────────────────────────────────────────────
CUSTOM_CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');

/* Global */
.stApp { font-family: 'Inter', sans-serif; }

/* Header */
.aria-hero {
    background: linear-gradient(135deg, #0f0c29 0%, #302b63 50%, #24243e 100%);
    border-radius: 16px;
    padding: 2.5rem 2rem;
    margin-bottom: 1.5rem;
    text-align: center;
    color: white;
}
.aria-hero h1 {
    font-size: 2.4rem;
    font-weight: 700;
    margin: 0 0 0.4rem 0;
    letter-spacing: -0.5px;
}
.aria-hero p {
    font-size: 1.05rem;
    opacity: 0.85;
    margin: 0;
}

/* Metric cards */
.metric-card {
    background: linear-gradient(135deg, #1e1e2e, #2a2a40);
    border: 1px solid #3a3a5c;
    border-radius: 14px;
    padding: 1.3rem 1.2rem;
    text-align: center;
    transition: transform 0.2s;
}
.metric-card:hover { transform: translateY(-2px); }
.metric-card .label {
    font-size: 0.78rem;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.8px;
    color: #9ca3af;
    margin-bottom: 0.3rem;
}
.metric-card .value {
    font-size: 1.9rem;
    font-weight: 700;
    color: #f9fafb;
}
.metric-card .sub { font-size: 0.8rem; color: #6b7280; margin-top: 0.15rem; }

/* Progress timeline */
.timeline-container {
    background: #111827;
    border: 1px solid #1f2937;
    border-radius: 12px;
    padding: 1rem 1.2rem;
    max-height: 420px;
    overflow-y: auto;
    font-family: 'JetBrains Mono', 'Fira Code', monospace;
    font-size: 0.82rem;
}
.timeline-entry {
    display: flex;
    align-items: flex-start;
    gap: 0.6rem;
    padding: 0.35rem 0;
    border-bottom: 1px solid #1f2937;
    animation: fadeIn 0.3s ease-in;
}
.timeline-entry:last-child { border-bottom: none; }
.tl-time {
    color: #6b7280;
    font-size: 0.72rem;
    min-width: 48px;
    padding-top: 2px;
    flex-shrink: 0;
}
.tl-msg { color: #d1d5db; line-height: 1.45; }
.tl-msg.done { color: #34d399; }
.tl-msg.active { color: #60a5fa; }
.tl-msg.error { color: #f87171; }

@keyframes fadeIn { from { opacity: 0; transform: translateY(4px); } to { opacity: 1; transform: translateY(0); } }

/* Finding card */
.finding-card {
    background: #1e1e2e;
    border: 1px solid #2d2d44;
    border-radius: 12px;
    padding: 1rem 1.2rem;
    margin-bottom: 0.8rem;
}
.finding-header {
    display: flex;
    align-items: center;
    gap: 0.5rem;
    font-weight: 600;
    margin-bottom: 0.5rem;
}

/* Severity pills */
.sev-pill {
    display: inline-block;
    padding: 0.15rem 0.65rem;
    border-radius: 20px;
    font-size: 0.72rem;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.5px;
}
.sev-critical { background: #450a0a; color: #fca5a5; border: 1px solid #7f1d1d; }
.sev-high     { background: #431407; color: #fdba74; border: 1px solid #7c2d12; }
.sev-medium   { background: #422006; color: #fcd34d; border: 1px solid #78350f; }
.sev-low      { background: #052e16; color: #86efac; border: 1px solid #14532d; }

/* Section header */
.section-hdr {
    font-size: 1.25rem;
    font-weight: 700;
    padding-bottom: 0.5rem;
    margin-top: 1.5rem;
    margin-bottom: 1rem;
    border-bottom: 2px solid #302b63;
    color: #e5e7eb;
}

/* Agent tag */
.agent-tag {
    display: inline-block;
    background: #1e293b;
    border: 1px solid #334155;
    border-radius: 8px;
    padding: 0.2rem 0.6rem;
    font-size: 0.75rem;
    color: #94a3b8;
    margin-right: 0.4rem;
}

/* Hide default Streamlit metric styling for our custom cards */
div[data-testid="stMetric"] { display: none; }

/* Smooth scrollbar for timeline */
.timeline-container::-webkit-scrollbar { width: 6px; }
.timeline-container::-webkit-scrollbar-track { background: #111827; }
.timeline-container::-webkit-scrollbar-thumb { background: #374151; border-radius: 3px; }
</style>
"""


def inject_css():
    st.markdown(CUSTOM_CSS, unsafe_allow_html=True)


def render_metric_card(label: str, value: str, sub: str = ""):
    sub_html = f'<div class="sub">{sub}</div>' if sub else ""
    st.markdown(
        f'<div class="metric-card">'
        f'<div class="label">{label}</div>'
        f'<div class="value">{value}</div>'
        f'{sub_html}</div>',
        unsafe_allow_html=True,
    )


def main():
    inject_css()

    # ── Hero banner ─────────────────────────────────────────────────────
    st.markdown(
        '<div class="aria-hero">'
        '<h1>🤖 ARIA</h1>'
        '<p>Adaptive Review Intelligence Architecture — Multi-LLM Code Review with Model Debate Protocol</p>'
        '</div>',
        unsafe_allow_html=True,
    )

    # ── Input area ──────────────────────────────────────────────────────
    with st.container():
        col1, col2, col3 = st.columns([5, 1.5, 1.5])
        with col1:
            repo_url = st.text_input(
                "Repository URL",
                placeholder="https://github.com/user/repo",
                label_visibility="collapsed",
            )
        with col2:
            branch = st.text_input("Branch", value="main", label_visibility="collapsed")
        with col3:
            run_btn = st.button("🚀 Start Review", type="primary", use_container_width=True)

    if run_btn:
        if not repo_url or "github.com" not in repo_url:
            st.error("Please enter a valid GitHub repository URL.")
            return
        run_review(repo_url, branch)


def run_review(repo_url: str, branch: str):
    """Execute the full review pipeline with a live progress timeline."""

    # ── progress state ──────────────────────────────────────────────────
    progress_bar = st.progress(0, text="Initializing…")
    timeline_placeholder = st.empty()
    log_entries: list[dict] = []
    start_time = time.time()

    def _render_timeline():
        """Re-render the full timeline HTML from log_entries."""
        rows = ""
        for entry in log_entries:
            css_class = entry.get("cls", "")
            rows += (
                f'<div class="timeline-entry">'
                f'<span class="tl-time">{entry["ts"]}</span>'
                f'<span class="tl-msg {css_class}">{entry["msg"]}</span>'
                f'</div>'
            )
        timeline_placeholder.markdown(
            f'<div class="timeline-container">{rows}</div>',
            unsafe_allow_html=True,
        )

    def on_progress(stage: str, message: str, pct: float):
        elapsed = time.time() - start_time
        mins, secs = divmod(int(elapsed), 60)
        ts = f"{mins}:{secs:02d}"

        css_cls = "active"
        if stage.endswith("_done") or stage in ("ingested", "debate_done"):
            css_cls = "done"
        elif "fail" in stage.lower() or "error" in stage.lower():
            css_cls = "error"

        log_entries.append({"ts": ts, "msg": message, "cls": css_cls})
        progress_bar.progress(min(pct, 1.0), text=message)
        _render_timeline()

    try:
        state = run_pipeline(repo_url, branch, on_progress=on_progress)
    except Exception as e:
        on_progress("error", f"❌ Pipeline error: {e}", 1.0)
        st.error(f"Pipeline failed: {str(e)}")
        return

    elapsed = time.time() - start_time
    on_progress("complete", f"✅ Review complete in {elapsed:.1f}s", 1.0)
    progress_bar.progress(1.0, text=f"Done — {elapsed:.1f}s")

    if state.status == "failed":
        st.error(f"Review failed: {state.error}")
        return

    render_report(state)


# ── Report rendering ────────────────────────────────────────────────────
def render_report(state):
    report = state.report
    findings = state.verified_findings

    st.markdown('<div class="section-hdr">📋 Review Report</div>', unsafe_allow_html=True)

    # ── Metric cards ────────────────────────────────────────────────────
    health = report.get("health_score", 0)
    slop = report.get("slop_score", 0)
    total = report.get("total_findings", 0)
    files_count = report.get("graph_stats", {}).get("total_files", 0)

    c1, c2, c3, c4 = st.columns(4)
    with c1:
        h_emoji = "🟢" if health >= 70 else ("🟡" if health >= 40 else "🔴")
        render_metric_card("Health Score", f"{h_emoji} {health}", "/100")
    with c2:
        s_emoji = "🟢" if slop < 15 else ("🟡" if slop < 35 else "🔴")
        render_metric_card("Slop Risk", f"{s_emoji} {slop}%", "lower is better")
    with c3:
        render_metric_card("Findings", str(total), "verified issues")
    with c4:
        render_metric_card("Files", str(files_count), "analyzed")

    # ── Knowledge Graph Visualization ─────────────────────────────────
    if state.knowledge_graph is not None:
        render_knowledge_graph(state.knowledge_graph)

    # ── Severity summary + Agent contributions ──────────────────────────
    st.markdown('<div class="section-hdr">📊 Breakdown</div>', unsafe_allow_html=True)

    col_l, col_r = st.columns(2)
    with col_l:
        st.markdown("**Findings by Severity**")
        for sev in ["critical", "high", "medium", "low"]:
            count = report.get("by_severity", {}).get(sev, 0)
            if count > 0:
                st.markdown(
                    f'<span class="sev-pill sev-{sev}">{sev}</span> &nbsp;**{count}**',
                    unsafe_allow_html=True,
                )
    with col_r:
        st.markdown("**Agent Contributions**")
        for agent, count in report.get("agent_stats", {}).items():
            icon = CATEGORY_ICONS.get(agent.split("Agent")[0].lower().replace(" ", "_"), "🤖")
            st.markdown(f'{icon} <span class="agent-tag">{agent}</span> {count} raw findings', unsafe_allow_html=True)

    # ── Detailed findings ───────────────────────────────────────────────
    st.markdown('<div class="section-hdr">🔍 Detailed Findings</div>', unsafe_allow_html=True)

    tab_labels = []
    tab_findings = []
    for sev in ["critical", "high", "medium", "low"]:
        items = [f for f in findings if f.severity == sev]
        if items:
            tab_labels.append(f"{SEVERITY_ICONS[sev]} {sev.upper()} ({len(items)})")
            tab_findings.append(items)

    if tab_labels:
        tabs = st.tabs(tab_labels)
        for tab, items in zip(tabs, tab_findings):
            with tab:
                for f in items:
                    render_finding(f)
    else:
        st.success("No significant findings — the codebase looks healthy. 🎉")

    # ── Export ──────────────────────────────────────────────────────────
    st.markdown('<div class="section-hdr">📥 Export</div>', unsafe_allow_html=True)
    c1, c2 = st.columns(2)
    with c1:
        html_content = report.get("html", "")
        if html_content:
            st.download_button("📄 HTML Report", html_content, "aria_report.html", "text/html", use_container_width=True)
    with c2:
        json_data = {k: v for k, v in report.items() if k != "html"}
        st.download_button(
            "📊 JSON Data",
            json.dumps(json_data, indent=2, default=str),
            "aria_report.json",
            "application/json",
            use_container_width=True,
        )


def render_knowledge_graph(G):
    """Render an interactive knowledge graph using pyvis."""
    try:
        from pyvis.network import Network
    except ImportError:
        st.warning("Install `pyvis` to see the interactive graph: `pip install pyvis`")
        return

    st.markdown('<div class="section-hdr">🔗 Knowledge Graph</div>', unsafe_allow_html=True)

    # ── Controls ────────────────────────────────────────────────────────
    node_count = G.number_of_nodes()
    max_nodes = min(node_count, 300)

    col1, col2 = st.columns([1, 1])
    with col1:
        show_limit = st.slider(
            "Max nodes to display", 20, max_nodes, min(100, max_nodes),
            help="Large graphs are capped for performance",
        )
    with col2:
        edge_filter = st.multiselect(
            "Edge types",
            ["defines", "imports", "calls"],
            default=["defines", "imports", "calls"],
        )

    # ── Build subgraph with limit ───────────────────────────────────────
    # Prioritize high-degree nodes for a meaningful view
    ranked = sorted(G.nodes(), key=lambda n: G.degree(n), reverse=True)[:show_limit]
    sub_nodes = set(ranked)

    # ── Color palette ───────────────────────────────────────────────────
    NODE_COLORS = {
        "file": "#6366f1",       # indigo
        "function": "#22d3ee",   # cyan
        "class": "#f59e0b",      # amber
        "struct": "#f59e0b",
    }
    EDGE_COLORS = {
        "defines": "#4b5563",
        "imports": "#3b82f6",
        "calls": "#ef4444",
    }

    # ── Build pyvis network ─────────────────────────────────────────────
    net = Network(
        height="520px",
        width="100%",
        bgcolor="#0f172a",
        font_color="#e2e8f0",
        directed=True,
    )
    net.barnes_hut(
        gravity=-3000,
        central_gravity=0.3,
        spring_length=120,
        spring_strength=0.04,
        damping=0.09,
    )

    for node in sub_nodes:
        data = G.nodes[node]
        ntype = data.get("type", "file")
        color = NODE_COLORS.get(ntype, "#9ca3af")

        # Shorten label for readability
        if "::" in node:
            label = node.split("::")[-1]
        else:
            label = node.split("/")[-1] if "/" in node else node

        size = 10 + min(G.degree(node) * 2, 30)
        shape = "dot" if ntype == "file" else ("diamond" if ntype in ("class", "struct") else "triangle")

        net.add_node(
            node,
            label=label,
            title=f"{node}\nType: {ntype}\nConnections: {G.degree(node)}",
            color=color,
            size=size,
            shape=shape,
        )

    for u, v, data in G.edges(data=True):
        if u in sub_nodes and v in sub_nodes:
            rel = data.get("relation", "unknown")
            if rel not in edge_filter:
                continue
            net.add_edge(
                u, v,
                title=rel,
                color=EDGE_COLORS.get(rel, "#6b7280"),
                width=1.5 if rel == "calls" else 1,
                arrows="to",
            )

    # ── Render to HTML and embed ────────────────────────────────────────
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".html", mode="w")
    net.save_graph(tmp.name)
    tmp.close()

    with open(tmp.name, "r") as f:
        html = f.read()
    os.unlink(tmp.name)

    # Legend row
    st.markdown(
        '<div style="display:flex;gap:1.2rem;margin-bottom:0.6rem;font-size:0.8rem;color:#9ca3af;">'
        '<span>● <span style="color:#6366f1">File</span></span>'
        '<span>▲ <span style="color:#22d3ee">Function</span></span>'
        '<span>◆ <span style="color:#f59e0b">Class</span></span>'
        '<span>— <span style="color:#3b82f6">imports</span></span>'
        '<span>— <span style="color:#ef4444">calls</span></span>'
        '<span>— <span style="color:#4b5563">defines</span></span>'
        '</div>',
        unsafe_allow_html=True,
    )

    components.html(html, height=540, scrolling=False)

    st.caption(
        f"Showing {min(show_limit, node_count)} of {node_count} nodes · "
        f"{G.number_of_edges()} edges · Interactive — drag, zoom, hover for details"
    )


def render_finding(f):
    sev = f.severity
    cat_icon = CATEGORY_ICONS.get(f.category, "📌")
    sev_icon = SEVERITY_ICONS.get(sev, "⚪")
    loc = f":{f.line}" if f.line else ""

    with st.expander(f"{sev_icon} {cat_icon} {f.title}  —  `{f.file}{loc}`  ({f.confidence:.0%})"):
        st.markdown(
            f'<span class="sev-pill sev-{sev}">{sev}</span> '
            f'<span class="agent-tag">{f.agent}</span> '
            f'<span class="agent-tag">{f.category}</span>',
            unsafe_allow_html=True,
        )
        st.markdown(f"\n{f.description}")
        if f.suggestion:
            st.info(f"💡 **Suggestion:** {f.suggestion}")


if __name__ == "__main__":
    main()
