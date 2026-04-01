from src.agents.base_agent import Finding


def compute_health_score(findings: list[Finding]) -> int:
    n_crit = sum(1 for f in findings if f.severity == "critical")
    n_high = sum(1 for f in findings if f.severity == "high")
    n_med = sum(1 for f in findings if f.severity == "medium")
    n_low = sum(1 for f in findings if f.severity == "low")

    score = 100 - (10 * n_crit + 5 * n_high + 2 * n_med + 0.5 * n_low)
    return max(0, min(100, int(score)))


def compute_slop_score(findings: list[Finding], total_files: int) -> float:
    if total_files == 0:
        return 0.0
    slop_files = set()
    for f in findings:
        if f.category == "ai_slop":
            slop_files.add(f.file)
    return (len(slop_files) / total_files) * 100
