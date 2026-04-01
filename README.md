<div align="center">

# ARIA

### Adaptive Review Intelligence Architecture

**Multi-LLM code review with cross-model debate verification**

[![Python 3.11+](https://img.shields.io/badge/Python-3.11+-3776AB?logo=python&logoColor=white)](https://python.org)
[![Streamlit](https://img.shields.io/badge/Streamlit-UI-FF4B4B?logo=streamlit&logoColor=white)](https://streamlit.io)
[![FastAPI](https://img.shields.io/badge/FastAPI-Backend-009688?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

[Getting Started](#getting-started) · [Architecture](#architecture) · [Design Document](docs/design_document.tex)

</div>

---

## What is ARIA?

ARIA is an intelligent automatic code review system that takes a **GitHub repository URL** and generates a comprehensive review report. It deploys **5 specialized agents** across **3 different LLM families** (Llama, Gemini, Mistral) that independently analyze code, then **cross-verify each other's findings** through a structured debate protocol.

Only consensus-backed findings appear in the final report — eliminating hallucinations, false positives, and single-model bias.

```
GitHub URL → Clone & Parse → 5 Agent Review → Cross-Model Debate → Verified Report
               (AST + Graph)   (3 LLM families)   (Confirm/Refute)    (Scored findings)
```

## Key Innovation: Model Debate Protocol

Existing tools trust a single model's output. ARIA's **Model Debate Protocol** works differently:

1. **Independent Review** — Each agent reviews the codebase with its specialized focus
2. **Cross-Family Verification** — Every finding is sent to 2 agents from *different* model families
3. **Structured Argumentation** — Verifiers must CONFIRM (with evidence) or REFUTE (with reasoning)
4. **Consensus Filtering** — Only findings with score ≥ 0.7 reach the final report
5. **Deduplication** — Jaccard similarity merges overlapping findings

| Failure Mode | Single-Model Tool | ARIA Debate |
|---|---|---|
| Hallucinated finding | Shown to developer | Refuted by other models → filtered |
| Missed vulnerability | Never caught | Different model family catches it |
| False positive | Wastes developer time | Cross-verification rejects it |
| Model bias | Persists | Uncorrelated biases cancel out |

## Architecture

```
┌──────────────────────────────────────────────┐
│  Stage 1: Repository Ingestion               │
│  Clone → AST Parsing → Knowledge Graph       │
└───────────────────┬──────────────────────────┘
                    ▼
┌──────────────────────────────────────────────┐
│  Stage 2: Parallel Agent Swarm               │
│                                              │
│  Security    Quality    Arch    Perf   Slop  │
│  (Groq)     (Groq)    (Gem)   (Mis)  (Mis)  │
└───────────────────┬──────────────────────────┘
                    ▼
┌──────────────────────────────────────────────┐
│  Stage 3: Model Debate & Cross-Verification  │
│  Confirm/Refute → Consensus → Deduplication  │
└───────────────────┬──────────────────────────┘
                    ▼
┌──────────────────────────────────────────────┐
│  Stage 4: Orchestration & Validation         │
│  State Machine with Retry Loop               │
└───────────────────┬──────────────────────────┘
                    ▼
┌──────────────────────────────────────────────┐
│  Stage 5: Report Generation                  │
│  Health Score + Severity Buckets + Fixes     │
└──────────────────────────────────────────────┘
```

### Agents

| Agent | Provider / Model | Focus |
|---|---|---|
| **Security Auditor** | Groq (Llama 3.3 70B) | OWASP Top 10, CVEs, hardcoded secrets, injections |
| **Code Quality** | Groq (Llama 3.3 70B) | Complexity, dead code, duplication, error handling |
| **Architecture** | Google Gemini 2.0 Flash | SOLID violations, coupling, design patterns |
| **Performance** | Mistral Small | O(n²) algorithms, memory leaks, N+1 queries |
| **AI-Slop Detector** | Mistral Small | Over-abstraction, brittle AI-generated patterns |

### Tech Stack

| Layer | Technology |
|---|---|
| **LLMs** | Groq (Llama 3.3 70B), Google Gemini 2.0 Flash, Mistral Small |
| **Orchestration** | LangGraph state machine with retry |
| **Code Analysis** | Regex-based multi-language AST parser, NetworkX knowledge graph |
| **Backend** | FastAPI REST API |
| **Frontend** | Streamlit web UI |
| **Reporting** | Jinja2 HTML templates |

## Getting Started

### Prerequisites

- Python 3.11+
- Git
- Free API keys from [Groq](https://console.groq.com), [Google AI Studio](https://aistudio.google.com), and [Mistral](https://console.mistral.ai)

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

All APIs are **free tier** — no paid subscriptions required.

### Usage

**Streamlit UI** (recommended):

```bash
streamlit run app/streamlit_app.py
```

**FastAPI** (programmatic access):

```bash
uvicorn src.main:app --reload

# Submit a review
curl -X POST http://localhost:8000/api/review \
  -H "Content-Type: application/json" \
  -d '{"repo_url": "https://github.com/user/repo"}'
```

### API Endpoints

| Method | Endpoint | Description |
|---|---|---|
| `POST` | `/api/review` | Submit a GitHub URL for review |
| `GET` | `/api/review/{job_id}` | Get review status and results |
| `GET` | `/api/review/{job_id}/report` | Download the report |
| `GET` | `/api/health` | System health check |

## Report Output

The generated report includes:

- **Health Score** (0–100) — weighted by severity: `H = 100 - (10·critical + 5·high + 2·medium + 0.5·low)`
- **AI-Slop Score** — percentage of files with AI-generated debt patterns
- **Severity Buckets** — Critical / High / Medium / Low with consensus scores
- **Per-File Annotations** — line-level references with code context
- **Fix Suggestions** — actionable recommendations per finding

## Project Structure

```
ARIA/
├── app/
│   └── streamlit_app.py            # Streamlit web UI
├── docs/
│   └── design_document.tex         # LaTeX design document
├── src/
│   ├── main.py                     # FastAPI entry point
│   ├── config.py                   # Configuration & env loading
│   ├── ingestion/
│   │   ├── github_client.py        # Repo cloning & file collection
│   │   ├── ast_parser.py           # Multi-language AST extraction
│   │   ├── knowledge_graph.py      # NetworkX dependency graph
│   │   └── vector_store.py         # Context chunking
│   ├── agents/
│   │   ├── base_agent.py           # Base agent with retry & rate limiting
│   │   ├── security_agent.py       # OWASP/CVE security review
│   │   ├── quality_agent.py        # Code quality analysis
│   │   ├── architecture_agent.py   # Architecture review
│   │   ├── performance_agent.py    # Performance analysis
│   │   └── slop_detector.py        # AI-Slop detection
│   ├── debate/
│   │   ├── debate_manager.py       # Cross-model verification
│   │   └── consensus.py            # Scoring & deduplication
│   ├── orchestrator/
│   │   ├── graph.py                # Pipeline state machine
│   │   └── states.py               # State definitions
│   └── report/
│       ├── generator.py            # HTML report generation
│       ├── scoring.py              # Health & slop score math
│       └── templates/
│           └── report.html         # Jinja2 report template
├── requirements.txt
└── .env                            # API keys (git-ignored)
```

## Novel Contributions

1. **Model Debate Protocol** — Cross-model verification eliminates hallucinations and false positives
2. **AI-Slop Detector** — Dedicated agent for the #1 developer concern in 2026
3. **Multi-Family Diversity** — 3 architecturally different LLM families reduce correlated bias
4. **Consensus Scoring** — Mathematical confidence thresholds replace subjective filtering
5. **Zero-Cost Deployment** — Fully functional on free-tier APIs

## License

This project is licensed under the MIT License.
