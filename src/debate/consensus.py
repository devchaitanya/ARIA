from src.agents.base_agent import Finding
from src.config import SIMILARITY_THRESHOLD


def compute_consensus(finding: Finding, votes: list[dict]) -> float:
    confirms = sum(1 for v in votes if v.get("verdict", "").upper() == "CONFIRM")
    total = len(votes) if votes else 1
    return confirms / total


def deduplicate_findings(findings: list[Finding], threshold: float = SIMILARITY_THRESHOLD) -> list[Finding]:
    """Deduplicate findings based on textual similarity of title + description."""
    if not findings:
        return []

    unique = []
    for f in findings:
        is_dup = False
        f_text = f"{f.title} {f.description} {f.file}".lower()
        for u in unique:
            u_text = f"{u.title} {u.description} {u.file}".lower()
            sim = _jaccard_similarity(f_text, u_text)
            if sim >= threshold:
                if _severity_rank(f.severity) > _severity_rank(u.severity):
                    unique.remove(u)
                    unique.append(f)
                is_dup = True
                break
        if not is_dup:
            unique.append(f)
    return unique


def _jaccard_similarity(text1: str, text2: str) -> float:
    words1 = set(text1.split())
    words2 = set(text2.split())
    if not words1 or not words2:
        return 0.0
    intersection = words1 & words2
    union = words1 | words2
    return len(intersection) / len(union)


def _severity_rank(severity: str) -> int:
    return {"critical": 4, "high": 3, "medium": 2, "low": 1}.get(severity.lower(), 0)
