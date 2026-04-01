import os
import json
from datetime import datetime
from jinja2 import Template
from src.agents.base_agent import Finding


def generate_report(
    repo_url: str,
    findings: list[Finding],
    health_score: int,
    slop_score: float,
    graph_stats: dict,
    agent_findings: dict,
) -> dict:
    by_severity = {
        "critical": [f for f in findings if f.severity == "critical"],
        "high": [f for f in findings if f.severity == "high"],
        "medium": [f for f in findings if f.severity == "medium"],
        "low": [f for f in findings if f.severity == "low"],
    }

    by_category = {}
    for f in findings:
        by_category.setdefault(f.category, []).append(f)

    agent_stats = {}
    for name, flist in agent_findings.items():
        agent_stats[name] = len(flist)

    report_data = {
        "repo_url": repo_url,
        "generated_at": datetime.now().isoformat(),
        "health_score": health_score,
        "slop_score": round(slop_score, 1),
        "total_findings": len(findings),
        "by_severity": {k: len(v) for k, v in by_severity.items()},
        "by_category": {k: len(v) for k, v in by_category.items()},
        "agent_stats": agent_stats,
        "graph_stats": graph_stats,
        "findings": [_finding_to_dict(f) for f in findings],
    }

    report_data["html"] = _render_html(report_data, by_severity)
    return report_data


def _finding_to_dict(f: Finding) -> dict:
    return {
        "file": f.file,
        "line": f.line,
        "severity": f.severity,
        "category": f.category,
        "title": f.title,
        "description": f.description,
        "suggestion": f.suggestion,
        "agent": f.agent,
        "confidence": round(f.confidence, 2),
    }


def _render_html(data: dict, by_severity: dict) -> str:
    template_path = os.path.join(os.path.dirname(__file__), "templates", "report.html")
    try:
        with open(template_path, "r") as f:
            tmpl = Template(f.read())
        return tmpl.render(data=data, by_severity=by_severity)
    except FileNotFoundError:
        return _fallback_html(data, by_severity)


def _fallback_html(data: dict, by_severity: dict) -> str:
    severity_colors = {"critical": "#DC2626", "high": "#EA580C", "medium": "#CA8A04", "low": "#16A34A"}
    severity_icons = {"critical": "🔴", "high": "🟠", "medium": "🟡", "low": "🟢"}

    findings_html = ""
    for sev in ["critical", "high", "medium", "low"]:
        items = by_severity.get(sev, [])
        if not items:
            continue
        findings_html += f'<h3 style="color:{severity_colors[sev]}">{severity_icons[sev]} {sev.upper()} ({len(items)})</h3>\n'
        for f in items:
            findings_html += f"""
            <div style="border-left:4px solid {severity_colors[sev]}; padding:12px; margin:8px 0; background:#F8FAFC; border-radius:4px;">
                <strong>{f.title}</strong> <span style="color:#666">({f.agent} | {f.category} | confidence: {f.confidence:.0%})</span><br>
                <code>{f.file}{(':' + str(f.line)) if f.line else ''}</code><br>
                <p>{f.description}</p>
                <p style="color:#16A34A"><strong>Fix:</strong> {f.suggestion}</p>
            </div>
            """

    slop_color = "#16A34A" if data["slop_score"] < 15 else ("#EA580C" if data["slop_score"] < 35 else "#DC2626")

    return f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>ARIA Code Review Report</title>
    <style>
        body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; max-width: 900px; margin: 0 auto; padding: 20px; color: #1E293B; }}
        h1 {{ color: #2563EB; border-bottom: 2px solid #2563EB; padding-bottom: 10px; }}
        .score-card {{ display: flex; gap: 20px; margin: 20px 0; }}
        .score {{ background: #F1F5F9; padding: 20px; border-radius: 8px; text-align: center; flex: 1; }}
        .score .number {{ font-size: 2.5em; font-weight: bold; }}
        table {{ width: 100%; border-collapse: collapse; margin: 15px 0; }}
        th, td {{ padding: 8px 12px; text-align: left; border-bottom: 1px solid #E2E8F0; }}
        th {{ background: #F1F5F9; }}
    </style>
</head>
<body>
    <h1>📋 ARIA Code Review Report</h1>
    <p><strong>Repository:</strong> <a href="{data['repo_url']}">{data['repo_url']}</a></p>
    <p><strong>Generated:</strong> {data['generated_at']}</p>

    <div class="score-card">
        <div class="score">
            <div class="number" style="color:{'#16A34A' if data['health_score'] >= 70 else ('#EA580C' if data['health_score'] >= 40 else '#DC2626')}">{data['health_score']}</div>
            <div>Health Score (0-100)</div>
        </div>
        <div class="score">
            <div class="number" style="color:{slop_color}">{data['slop_score']}%</div>
            <div>AI-Slop Risk</div>
        </div>
        <div class="score">
            <div class="number">{data['total_findings']}</div>
            <div>Total Findings</div>
        </div>
    </div>

    <h2>📊 Summary</h2>
    <table>
        <tr><th>Severity</th><th>Count</th></tr>
        <tr><td>🔴 Critical</td><td>{data['by_severity'].get('critical', 0)}</td></tr>
        <tr><td>🟠 High</td><td>{data['by_severity'].get('high', 0)}</td></tr>
        <tr><td>🟡 Medium</td><td>{data['by_severity'].get('medium', 0)}</td></tr>
        <tr><td>🟢 Low</td><td>{data['by_severity'].get('low', 0)}</td></tr>
    </table>

    <h2>🤖 Agent Contributions</h2>
    <table>
        <tr><th>Agent</th><th>Findings</th></tr>
        {''.join(f"<tr><td>{k}</td><td>{v}</td></tr>" for k, v in data['agent_stats'].items())}
    </table>

    <h2>🔍 Detailed Findings</h2>
    {findings_html}

    <hr>
    <p style="color:#94A3B8; text-align:center;">Generated by ARIA — Adaptive Review Intelligence Architecture</p>
</body>
</html>"""
