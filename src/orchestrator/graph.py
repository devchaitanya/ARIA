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


def create_agents():
    return [
        SecurityAgent(),
        QualityAgent(),
        ArchitectureAgent(),
        PerformanceAgent(),
        SlopDetectorAgent(),
    ]


def node_ingest(state: ReviewState) -> ReviewState:
    """Stage 1: Clone repo, parse AST, build knowledge graph."""
    logger.info(f"[INGEST] Cloning {state.repo_url}")
    state.status = "ingesting"

    try:
        meta = clone_repo(state.repo_url, state.branch)
        state.repo_path = meta.local_path

        files = collect_files(meta.local_path, SUPPORTED_EXTENSIONS, MAX_FILE_SIZE, MAX_FILES)
        state.files = files
        logger.info(f"[INGEST] Collected {len(files)} files")

        kg = build_knowledge_graph(files)
        state.graph_summary = get_graph_summary(kg)
        state.graph_stats = kg["stats"]

        build_context_chunks(files)

        logger.info(f"[INGEST] Knowledge graph: {kg['stats']}")
    except Exception as e:
        state.error = f"Ingestion failed: {str(e)}"
        state.status = "failed"
        logger.error(f"[INGEST] Failed: {e}")

    return state


def node_review(state: ReviewState) -> ReviewState:
    """Stage 2: Run parallel specialized agent swarm."""
    if state.status == "failed":
        return state

    logger.info("[REVIEW] Starting parallel agent review")
    state.status = "reviewing"

    agents = create_agents()
    all_findings = []

    def run_agent(agent):
        try:
            logger.info(f"  Running {agent.name} ({agent.provider})...")
            findings = agent.review(state.files, state.graph_summary)
            logger.info(f"  {agent.name} found {len(findings)} issues")
            return agent.name, findings
        except Exception as e:
            logger.error(f"  {agent.name} failed: {e}")
            return agent.name, []

    with concurrent.futures.ThreadPoolExecutor(max_workers=3) as executor:
        futures = {executor.submit(run_agent, agent): agent for agent in agents}
        for future in concurrent.futures.as_completed(futures):
            name, findings = future.result()
            state.agent_findings[name] = findings
            all_findings.extend(findings)

    state.all_findings = all_findings
    logger.info(f"[REVIEW] Total findings across all agents: {len(all_findings)}")
    return state


def node_debate(state: ReviewState) -> ReviewState:
    """Stage 3: Cross-verify findings via Model Debate Protocol."""
    if state.status == "failed":
        return state

    logger.info("[DEBATE] Starting cross-verification")
    state.status = "debating"

    agents = create_agents()
    debate_mgr = DebateManager(agents, state.files)

    try:
        verified = debate_mgr.run_debate(state.all_findings)
        state.verified_findings = verified
        logger.info(f"[DEBATE] Verified findings: {len(verified)} / {len(state.all_findings)}")
    except Exception as e:
        logger.error(f"[DEBATE] Failed: {e}")
        state.verified_findings = state.all_findings
        for f in state.verified_findings:
            f.confidence = 0.5

    return state


def node_validate(state: ReviewState) -> ReviewState:
    """Stage 4: Validate results, check for obvious hallucinations."""
    if state.status == "failed":
        return state

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


def node_report(state: ReviewState) -> ReviewState:
    """Stage 5: Generate the final structured report."""
    if state.status == "failed":
        return state

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


def run_pipeline(repo_url: str, branch: str = "main") -> ReviewState:
    """Execute the full ARIA pipeline as a sequential state machine."""
    state = ReviewState(repo_url=repo_url, branch=branch)

    state = node_ingest(state)
    if state.status == "failed":
        return state

    for attempt in range(state.max_retries + 1):
        state = node_review(state)
        state = node_debate(state)
        state = node_validate(state)

        if state.status != "reviewing":
            break
        logger.info(f"[PIPELINE] Retry {attempt + 1}")

    state = node_report(state)
    return state
