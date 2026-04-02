<div align="center">

# 🤖 ARIA

### Adaptive Review Intelligence Architecture

**Multi-LLM code review system with cross-model debate verification**

[![Python 3.11+](https://img.shields.io/badge/Python-3.11+-3776AB?logo=python&logoColor=white)](https://python.org)
[![Streamlit](https://img.shields.io/badge/Streamlit-UI-FF4B4B?logo=streamlit&logoColor=white)](https://streamlit.io)
[![FastAPI](https://img.shields.io/badge/FastAPI-Backend-009688?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

[Features](#features) · [Architecture](#architecture) · [Getting Started](#getting-started) · [Design Document](docs/design_document.tex)

---

*5 AI agents · 3 LLM families · 5 model variants · consensus-driven findings*

</div>

## Overview

ARIA takes a **GitHub repository URL**, builds a **knowledge graph** of the codebase, then deploys **5 specialized review agents** across **3 different LLM provider families** (Groq/Llama, Google Gemini, Mistral). Each agent independently analyzes the code from its area of expertise, then all findings go through a **cross-model debate protocol** where agents from *different* families verify or refute each other's findings.

Only consensus-backed findings survive — eliminating hallucinations, false positives, and single-model bias.

```
GitHub URL → Clone & Parse → Knowledge Graph → 5 Agent Review → Cross-Model Debate → Verified Report
               AST extraction   NetworkX graph   3 LLM families    Confirm/Refute      Scored findings
```

## Features

- **2-Phase Interactive UI** — Phase 1 indexes the repo and visualizes the knowledge graph; Phase 2 lets you select which agents to run
- **Interactive Knowledge Graph** — Pyvis-powered visualization with color-coded nodes (files, functions, classes), filterable by connection count
- **Agent Selection** — Choose which review dimensions to run (security, quality, architecture, performance, AI-slop)
- **Graph-Aware Analysis** — Agents receive rich structural context: hub files, import chains, call graphs, entry points, class hierarchies
- **Deep Line-Level Findings** — Each agent quotes exact file:line references and code snippets with concrete fix suggestions
- **Fast-Fail Rate Limiting** — Custom `RateLimitError` with exponential backoff + jitter; skips exhausted providers immediately
- **Cross-Provider Fallback** — Each agent tries primary model → alt model → different provider, ensuring maximum availability on free tiers
- **Health & Slop Scoring** — Weighted health score (0–100) and AI-slop percentage per codebase
- **Export** — Download findings as HTML report or JSON

## The Model Debate Protocol

Existing tools trust a single model's output. ARIA's debate protocol works differently:

1. **Independent Review** — Each agent reviews code with its specialized methodology
2. **Cross-Family Verification** — Every finding is sent to 2 agents from *different* LLM families
3. **Structured Argumentation** — Verifiers must CONFIRM (with evidence) or REFUTE (with reasoning)
4. **Consensus Filtering** — Only findings with consensus score ≥ 0.7 reach the final report
5. **Deduplication** — Jaccard similarity (≥ 0.85) merges overlapping findings

| Failure Mode | Single-Model Tool | ARIA Debate |
|---|---|---|
| Hallucinated finding | Shown to developer | Refuted by other models → filtered |
| Missed vulnerability | Never caught | Different model family catches it |
| False positive | Wastes developer time | Cross-verification rejects it |
| Model bias | Persists unchecked | Uncorrelated biases cancel out |

## Architecture

```
┌─────────────────────────────────────────────────────┐
│  Phase 1: Repository Ingestion                      │
│  Clone → AST Parsing → NetworkX Knowledge Graph     │
│  Hub files, import chains, call graph, entry points │
└──────────────────────┬──────────────────────────────┘
                       ▼
┌─────────────────────────────────────────────────────┐
│  Phase 2: Sequential Agent Swarm (user-selectable)  │
│                                                     │
│  🛡️  Security     🔧 Quality      🏗️  Architecture │
│  Groq/Llama 3.3   Groq/Llama 4    Gemini 2.5 Flash │
│                                                     │
│  ⚡ Performance    🧹 AI-Slop Detector              │
│  Mistral Small     Mistral Devstral                 │
└──────────────────────┬──────────────────────────────┘
                       ▼
┌─────────────────────────────────────────────────────┐
│  Phase 3: Cross-Model Debate & Consensus            │
│  Confirm/Refute → Score ≥ 0.7 → Dedup (Jaccard)    │
└──────────────────────┬──────────────────────────────┘
                       ▼
┌─────────────────────────────────────────────────────┐
│  Phase 4: Report Generation                         │
│  Health Score · Slop Score · Severity Buckets       │
│  Per-finding: file:line, code quotes, fix code      │
└─────────────────────────────────────────────────────┘
```

### Agents & Models

| Agent | Provider | Primary Model | Fallback Model | Focus Area |
|---|---|---|---|---|
| **🛡️ Security Auditor** | Groq | Llama 3.3 70B | Llama 4 Scout 17B | OWASP Top 10, injections, hardcoded secrets, auth flaws |
| **🔧 Code Quality** | Groq | Llama 4 Scout 17B | Llama 3.3 70B | Complexity, dead code, error handling, naming |
| **🏗️ Architecture** | Google | Gemini 2.5 Flash | Gemini 2.0 Flash | SOLID violations, coupling, layering, design patterns |
| **⚡ Performance** | Mistral | Mistral Small | Devstral Small | O(n²) algorithms, memory leaks, N+1 queries, caching |
| **🧹 AI-Slop Detector** | Mistral | Devstral Small | Mistral Small | Over-abstraction, cargo-cult patterns, brittle AI code |

Each agent also has **cross-provider fallback**: if all models from one provider are rate-limited, the agent falls back to a different provider entirely.

### Tech Stack

| Layer | Technology |
|---|---|
| **LLM Providers** | Groq (Llama 3.3 70B, Llama 4 Scout), Google Gemini (2.5 Flash, 2.0 Flash), Mistral (Small, Devstral) |
| **Orchestration** | LangGraph-style state machine with `run_ingest()` + `run_analysis()` split |
| **Code Analysis** | Regex-based multi-language AST parser + NetworkX knowledge graph |
| **Graph Viz** | Pyvis interactive network with Barnes-Hut physics |
| **Frontend** | Streamlit (2-phase UI with session state persistence) |
| **Backend** | FastAPI REST API |
| **Reporting** | Jinja2 HTML templates + JSON export |
| **Rate Limiting** | Custom `RateLimitError` with exponential backoff, jitter, fast-fail |

## Getting Started

### Prerequisites

- Python 3.11+
- Git
- Free API keys from:
  - [Groq Console](https://console.groq.com) — Llama models
  - [Google AI Studio](https://aistudio.google.com) — Gemini models
  - [Mistral Console](https://console.mistral.ai) — Mistral models

### Installation

```bash
git clone https://github.com/devchaitanya/ARIA.git
cd ARIA
pip install -r requirements.txt
```

### Configuration

Create a `.env` file in the project root:

```env
GROQ_API_KEY=your_groq_key
GEMINI_API_KEY=your_gemini_key
MISTRAL_API_KEY=your_mistral_key
```

All three APIs offer **free tiers** — no paid subscriptions required.

### Usage

**Streamlit UI** (recommended):

```bash
streamlit run app/streamlit_app.py
```

1. Enter a GitHub repository URL and branch
2. Click **Analyze Repository** — ARIA clones, parses, and builds the knowledge graph
3. Explore the interactive graph visualization, adjust node count with the slider
4. Select which agents to run via the agent cards
5. Click **Run Agents** — debate protocol runs, findings appear in categorized tabs
6. Download the HTML report or JSON data

**FastAPI** (programmatic access):

```bash
uvicorn src.main:app --reload
```

| Method | Endpoint | Description |
|---|---|---|
| `POST` | `/api/review` | Submit a GitHub URL for review |
| `GET` | `/api/review/{job_id}` | Get review status and results |
| `GET` | `/api/review/{job_id}/report` | Download the HTML report |
| `GET` | `/api/health` | System health check |

## Report Output

- **Health Score** (0–100) — `H = 100 − (10·critical + 5·high + 2·medium + 0.5·low)`
- **AI-Slop Score** — percentage of files with AI-generated debt patterns
- **Severity Buckets** — Critical / High / Medium / Low with consensus confidence scores
- **Per-Finding Detail** — file:line reference, code snippet, severity pill, agent tag, fix suggestion
- **Export** — HTML report with full styling or raw JSON

## Project Structure

```
ARIA/
├── app/
│   └── streamlit_app.py            # 2-phase Streamlit UI with session state
├── docs/
│   └── design_document.tex         # LaTeX design document
├── src/
│   ├── main.py                     # FastAPI entry point
│   ├── config.py                   # Models, keys, thresholds
│   ├── agents/
│   │   ├── base_agent.py           # Base agent: retry, backoff, fallback, RateLimitError
│   │   ├── security_agent.py       # OWASP/CVE security audit
│   │   ├── quality_agent.py        # Code quality & complexity
│   │   ├── architecture_agent.py   # SOLID & design pattern review
│   │   ├── performance_agent.py    # Algorithmic & runtime analysis
│   │   └── slop_detector.py        # AI-generated code detection
│   ├── debate/
│   │   ├── debate_manager.py       # Cross-model verification rounds
│   │   └── consensus.py            # Scoring, thresholds, deduplication
│   ├── ingestion/
│   │   ├── github_client.py        # Repo cloning & file collection
│   │   ├── ast_parser.py           # Multi-language regex AST extraction
│   │   ├── knowledge_graph.py      # NetworkX graph + rich summary
│   │   └── vector_store.py         # Code chunking for context
│   ├── orchestrator/
│   │   ├── graph.py                # Pipeline: run_ingest() + run_analysis()
│   │   └── states.py               # ReviewState dataclass
│   └── report/
│       ├── generator.py            # HTML report via Jinja2
│       ├── scoring.py              # Health & slop score math
│       └── templates/
│           └── report.html         # Report template
├── requirements.txt
└── .env                            # API keys (git-ignored)
```

## Supported Languages

Python, JavaScript, TypeScript, JSX, TSX, Java, Go, Rust, C, C++, Ruby, PHP, C#, Swift, Kotlin, Scala, Shell/Bash.

## Novel Contributions

1. **Model Debate Protocol** — Cross-model verification across 3 LLM families eliminates hallucinations and false positives
2. **AI-Slop Detector** — Dedicated agent targeting the #1 developer concern in 2026: over-abstracted AI-generated code
3. **Graph-Aware Agents** — Knowledge graph structural context (hubs, import chains, call graphs) fed directly into agent prompts
4. **Multi-Family Diversity** — 5 models across 3 architecturally different families reduce correlated bias
5. **Zero-Cost Deployment** — Fully functional on free-tier APIs with intelligent rate-limit handling

## License

MIT
