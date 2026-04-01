import sys
import os
import time
import json
import logging
import streamlit as st

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


def main():
    st.title("🤖 ARIA — Adaptive Review Intelligence Architecture")
    st.markdown(
        "**Multi-LLM code review with Model Debate Protocol.** "
        "Enter a GitHub repository URL to generate a comprehensive review report."
    )

    col1, col2 = st.columns([3, 1])
    with col1:
        repo_url = st.text_input("GitHub Repository URL", placeholder="https://github.com/user/repo")
    with col2:
        branch = st.text_input("Branch", value="main")

    if st.button("🚀 Start Review", type="primary", use_container_width=True):
        if not repo_url or "github.com" not in repo_url:
            st.error("Please enter a valid GitHub repository URL.")
            return

        run_review(repo_url, branch)


def run_review(repo_url: str, branch: str):
    progress = st.progress(0)
    status_text = st.empty()

    stages = [
        ("🔍 Cloning repository and parsing AST...", 15),
        ("🧠 Running specialized agent swarm (5 agents across 3 LLM families)...", 40),
        ("⚔️ Model Debate — cross-verifying findings...", 70),
        ("✅ Validating results...", 85),
        ("📋 Generating report...", 95),
    ]

    for msg, pct in stages[:1]:
        status_text.markdown(f"**{msg}**")
        progress.progress(pct / 100)

    start_time = time.time()

    try:
        state = run_pipeline(repo_url, branch)
    except Exception as e:
        st.error(f"Pipeline failed: {str(e)}")
        return

    elapsed = time.time() - start_time
    progress.progress(1.0)
    status_text.markdown(f"**✅ Review complete in {elapsed:.1f}s**")

    if state.status == "failed":
        st.error(f"Review failed: {state.error}")
        return

    render_report(state)


def render_report(state):
    report = state.report
    findings = state.verified_findings

    st.markdown("---")
    st.header("📋 Review Report")

    col1, col2, col3, col4 = st.columns(4)
    health = report.get("health_score", 0)
    slop = report.get("slop_score", 0)
    total = report.get("total_findings", 0)

    with col1:
        color = "🟢" if health >= 70 else ("🟡" if health >= 40 else "🔴")
        st.metric("Health Score", f"{color} {health}/100")
    with col2:
        color = "🟢" if slop < 15 else ("🟡" if slop < 35 else "🔴")
        st.metric("AI-Slop Risk", f"{color} {slop}%")
    with col3:
        st.metric("Total Findings", total)
    with col4:
        st.metric("Files Analyzed", report.get("graph_stats", {}).get("total_files", 0))

    st.markdown("---")

    col1, col2 = st.columns(2)
    with col1:
        st.subheader("📊 Findings by Severity")
        for sev in ["critical", "high", "medium", "low"]:
            count = report.get("by_severity", {}).get(sev, 0)
            if count > 0:
                st.markdown(f"{SEVERITY_ICONS[sev]} **{sev.upper()}**: {count}")

    with col2:
        st.subheader("🤖 Agent Contributions")
        for agent, count in report.get("agent_stats", {}).items():
            st.markdown(f"- **{agent}**: {count} raw findings")

    st.markdown("---")
    st.subheader("🔍 Detailed Findings")

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
        st.success("No significant findings! The codebase looks healthy. 🎉")

    st.markdown("---")
    st.subheader("📥 Export Report")
    col1, col2 = st.columns(2)
    with col1:
        html_content = report.get("html", "")
        if html_content:
            st.download_button("📄 Download HTML Report", html_content, "aria_report.html", "text/html")
    with col2:
        json_data = {k: v for k, v in report.items() if k != "html"}
        st.download_button(
            "📊 Download JSON Data",
            json.dumps(json_data, indent=2, default=str),
            "aria_report.json",
            "application/json",
        )


def render_finding(f):
    cat_icon = CATEGORY_ICONS.get(f.category, "📌")
    sev_icon = SEVERITY_ICONS.get(f.severity, "⚪")

    with st.expander(f"{sev_icon} {cat_icon} **{f.title}** — `{f.file}`{':' + str(f.line) if f.line else ''} (confidence: {f.confidence:.0%})"):
        st.markdown(f"**Agent:** {f.agent} | **Category:** {f.category} | **Severity:** {f.severity}")
        st.markdown(f"**Description:**\n{f.description}")
        if f.suggestion:
            st.markdown(f"**💡 Suggestion:**\n{f.suggestion}")


if __name__ == "__main__":
    main()
