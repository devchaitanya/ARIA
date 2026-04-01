import logging
import concurrent.futures
from src.orchestrator.states import ReviewState
from src.ingestion.github_client import clone_repo, collect_files
from src.ingestion.knowledge_graph import build_knowledge_graph, get_graph_summary
from src.ingestion.vector_store import build_context_chunks
from src.agents.security_agent import SecurityAgent
from src.agents.quality_agent import QualityAgent
from src.agents.architecture_agent import ArchitectureAgent
from src.agents.performance_agent import PerformanceAgent
from src.agents.slop_detector import SlopDetectorAgent
from src.debate.debate_manager import DebateManager
from src.report.generator import generate_report
from src.report.scoring import compute_health_score, compute_slop_score
from src.config import SUPPORTED_EXTENSIONS, MAX_FILE_SIZE, MAX_FILES

logger = logging.getLogger(__name__)


def create_agents(selected_categories: list[str] | None = None):
    all_agents = [
        SecurityAgent(),
        QualityAgent(),
        ArchitectureAgent(),
        PerformanceAgent(),
        SlopDetectorAgent(),
    ]
    if selected_categories is None:
        return all_agents
    category_map = {
        "security": SecurityAgent,
        "quality": QualityAgent,
        "architecture": ArchitectureAgent,
        "performance": PerformanceAgent,
        "ai_slop": SlopDetectorAgent,
    }
    return [category_map[cat]() for cat in selected_categories if cat in category_map]


def node_ingest(state: ReviewState, on_progress=None) -> ReviewState:
    """Stage 1: Clone repo, parse AST, build knowledge graph."""
    if on_progress:
        on_progress("cloning", "🔍 Cloning repository...", 0.05)
    logger.info(f"[INGEST] Cloning {state.repo_url}")
    state.status = "ingesting"

    try:
        meta = clone_repo(state.repo_url, state.branch)
        state.repo_path = meta.local_path

        if on_progress:
            on_progress("parsing", "📂 Parsing source files...", 0.10)

        files = collect_files(meta.local_path, SUPPORTED_EXTENSIONS, MAX_FILE_SIZE, MAX_FILES)
        state.files = files
        logger.info(f"[INGEST] Collected {len(files)} files")

        if on_progress:
            on_progress("graph", f"🔗 Building knowledge graph ({len(files)} files)...", 0.13)

        kg = build_knowledge_graph(files)
        state.graph_summary = get_graph_summary(kg)
        state.graph_stats = kg["stats"]
        state.knowledge_graph = kg["graph"]

        build_context_chunks(files)

        if on_progress:
            on_progress("ingested", f"✅ Ingested {len(files)} files, {kg['stats']['total_nodes']} nodes", 0.15)
        logger.info(f"[INGEST] Knowledge graph: {kg['stats']}")
    except Exception as e:
        state.error = f"Ingestion failed: {str(e)}"
        state.status = "failed"
        logger.error(f"[INGEST] Failed: {e}")

    return state


def node_review(state: ReviewState, on_progress=None, selected_categories=None) -> ReviewState:
    """Stage 2: Run specialized agent swarm sequentially."""
    if state.status == "failed":
        return state

    logger.info("[REVIEW] Starting parallel agent review")
    state.status = "reviewing"

    agents = create_agents(selected_categories)
    all_findings = []
    total_agents = len(agents)

    def run_agent(agent):
        try:
            logger.info(f"  Running {agent.name} ({agent.provider})...")
            findings = agent.review(state.files, state.graph_summary)
            logger.info(f"  {agent.name} found {len(findings)} issues")
            return agent.name, findings
        except Exception as e:
            logger.error(f"  {agent.name} failed: {e}")
            return agent.name, []

    # Agent descriptions for user-friendly progress
    _AGENT_TIPS = {
        "Security Auditor": "Tracing user inputs through SQL, shell, and file operations…",
        "Code Quality Analyst": "Scanning for complexity, dead code, and resource leaks…",
        "Architecture Reviewer": "Analyzing dependency chains and SOLID violations…",
        "Performance Profiler": "Checking algorithms, N+1 queries, and memory patterns…",
        "AI-Slop Detector": "Looking for over-abstraction and cargo-cult patterns…",
    }

    # Run agents sequentially with delay to respect rate limits across providers
    import time
    for i, agent in enumerate(agents):
        if on_progress:
            pct = 0.18 + (i / total_agents) * 0.37
            model_short = agent.model.split("/")[-1]
            on_progress("agent", f"🧠 [{i+1}/{total_agents}] {agent.name} ({agent.provider} · {model_short})", pct)
            tip = _AGENT_TIPS.get(agent.name, "Analyzing code…")
            on_progress("agent_tip", f"   ↳ {tip}", pct)
        name, findings = run_agent(agent)
        state.agent_findings[name] = findings
        all_findings.extend(findings)
        if on_progress:
            pct = 0.18 + ((i + 1) / total_agents) * 0.37
            on_progress("agent_done", f"   ✓ {name} → {len(findings)} findings", pct)
        time.sleep(3)  # Rate-limit spacing between agents

    state.all_findings = all_findings
    if on_progress:
        on_progress("review_done", f"🧠 All agents complete: {len(all_findings)} total findings", 0.55)
    logger.info(f"[REVIEW] Total findings across all agents: {len(all_findings)}")
    return state


def node_debate(state: ReviewState, on_progress=None, selected_categories=None) -> ReviewState:
    """Stage 3: Cross-verify findings via Model Debate Protocol."""
    if state.status == "failed":
        return state

    if on_progress:
        on_progress("debate", f"⚔️ Model Debate — cross-verifying {len(state.all_findings)} findings...", 0.58)
    logger.info("[DEBATE] Starting cross-verification")
    state.status = "debating"

    agents = create_agents(selected_categories)
    debate_mgr = DebateManager(agents, state.files)

    try:
        verified = debate_mgr.run_debate(state.all_findings, on_progress=on_progress)
        state.verified_findings = verified
        if on_progress:
            on_progress("debate_done", f"⚔️ Debate complete: {len(verified)}/{len(state.all_findings)} findings verified", 0.82)
        logger.info(f"[DEBATE] Verified findings: {len(verified)} / {len(state.all_findings)}")
    except Exception as e:
        logger.error(f"[DEBATE] Failed: {e}")
        state.verified_findings = state.all_findings
        for f in state.verified_findings:
            f.confidence = 0.5

    return state


def node_validate(state: ReviewState, on_progress=None) -> ReviewState:
    """Stage 4: Validate results, check for obvious hallucinations."""
    if state.status == "failed":
        return state

    if on_progress:
        on_progress("validate", "✅ Validating findings...", 0.85)
    logger.info("[VALIDATE] Checking findings quality")

    valid_findings = []
    for f in state.verified_findings:
        file_exists = any(ff["path"] == f.file for ff in state.files)
        if not file_exists and f.file != "unknown":
            logger.warning(f"  Hallucinated file reference: {f.file}")
            continue
        if len(f.description) < 10:
            logger.warning(f"  Empty finding filtered: {f.title}")
            continue
        valid_findings.append(f)

    if len(valid_findings) == 0 and len(state.all_findings) > 5 and state.retry_count < state.max_retries:
        logger.warning("[VALIDATE] All findings filtered — triggering retry")
        state.retry_count += 1
        state.status = "reviewing"
        return state

    state.verified_findings = valid_findings
    return state


def node_report(state: ReviewState, on_progress=None) -> ReviewState:
    """Stage 5: Generate the final structured report."""
    if state.status == "failed":
        return state

    if on_progress:
        on_progress("report", "📋 Generating report...", 0.90)
    logger.info("[REPORT] Generating report")
    state.status = "generating"

    health_score = compute_health_score(state.verified_findings)
    slop_score = compute_slop_score(state.verified_findings, len(state.files))
    state.report = generate_report(
        repo_url=state.repo_url,
        findings=state.verified_findings,
        health_score=health_score,
        slop_score=slop_score,
        graph_stats=state.graph_stats,
        agent_findings=state.agent_findings,
    )
    state.status = "completed"
    logger.info(f"[REPORT] Done. Health: {health_score}/100, AI-Slop: {slop_score:.1f}%")
    return state


def run_pipeline(repo_url: str, branch: str = "main", on_progress=None, selected_categories=None) -> ReviewState:
    """Execute the full ARIA pipeline as a sequential state machine."""
    state = ReviewState(repo_url=repo_url, branch=branch)

    state = node_ingest(state, on_progress)
    if state.status == "failed":
        return state

    for attempt in range(state.max_retries + 1):
        state = node_review(state, on_progress, selected_categories)
        state = node_debate(state, on_progress, selected_categories)
        state = node_validate(state, on_progress)

        if state.status != "reviewing":
            break
        logger.info(f"[PIPELINE] Retry {attempt + 1}")

    state = node_report(state, on_progress)
    return state


def run_ingest(repo_url: str, branch: str = "main", on_progress=None) -> ReviewState:
    """Phase 1: Clone + parse only. Returns state with graph ready for visualization."""
    state = ReviewState(repo_url=repo_url, branch=branch)
    state = node_ingest(state, on_progress)
    return state


def run_analysis(state: ReviewState, on_progress=None, selected_categories=None) -> ReviewState:
    """Phase 2: Run agents, debate, validate, report on an already-ingested state."""
    if state.status == "failed":
        return state

    for attempt in range(state.max_retries + 1):
        state = node_review(state, on_progress, selected_categories)
        state = node_debate(state, on_progress, selected_categories)
        state = node_validate(state, on_progress)

        if state.status != "reviewing":
            break
        logger.info(f"[PIPELINE] Retry {attempt + 1}")

    state = node_report(state, on_progress)
    return state
