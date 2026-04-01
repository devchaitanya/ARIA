from dataclasses import dataclass, field
from src.agents.base_agent import Finding


@dataclass
class ReviewState:
    repo_url: str = ""
    branch: str = "main"
    status: str = "pending"  # pending, ingesting, reviewing, debating, generating, completed, failed
    error: str = ""
    repo_path: str = ""
    files: list = field(default_factory=list)
    graph_summary: str = ""
    graph_stats: dict = field(default_factory=dict)
    agent_findings: dict = field(default_factory=dict)  # agent_name -> list[Finding]
    all_findings: list = field(default_factory=list)
    verified_findings: list = field(default_factory=list)
    report: dict = field(default_factory=dict)
    retry_count: int = 0
    max_retries: int = 2
