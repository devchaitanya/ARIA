import logging
import time
from src.agents.base_agent import BaseAgent, Finding
from src.debate.consensus import compute_consensus, deduplicate_findings
from src.config import CONFIDENCE_THRESHOLD

logger = logging.getLogger(__name__)

PROVIDER_MAP = {
    "groq": "groq",
    "gemini": "gemini",
    "mistral": "mistral",
}


class DebateManager:
    def __init__(self, agents: list[BaseAgent], files: list[dict]):
        self.agents = agents
        self.files = files
        self._file_content_map = {f["path"]: f["content"] for f in files}

    def run_debate(self, all_findings: list[Finding]) -> list[Finding]:
        """Cross-verify findings across different model families."""
        logger.info(f"Starting debate on {len(all_findings)} findings")

        verified_findings = []

        for finding in all_findings:
            verifiers = self._get_cross_family_verifiers(finding.agent)
            if not verifiers:
                finding.confidence = 0.5
                verified_findings.append(finding)
                continue

            file_content = self._file_content_map.get(finding.file, "File content not available")

            votes = []
            for verifier in verifiers[:2]:
                try:
                    vote = verifier.verify_finding(finding, file_content)
                    votes.append(vote)
                    logger.info(
                        f"  {verifier.name} -> {vote.get('verdict', 'UNKNOWN')} on '{finding.title}'"
                    )
                    time.sleep(1.5)  # Rate limit spacing between verification calls
                except Exception as e:
                    logger.warning(f"  {verifier.name} failed to verify: {e}")
                    votes.append({"verdict": "ABSTAIN", "reasoning": str(e)})

            confidence = compute_consensus(finding, votes)
            finding.confidence = confidence

            additional = []
            for v in votes:
                if v.get("additional_evidence"):
                    additional.append(v["additional_evidence"])
            if additional:
                finding.description += "\n\nAdditional evidence from cross-verification:\n" + "\n".join(additional)

            if confidence >= CONFIDENCE_THRESHOLD:
                verified_findings.append(finding)
                logger.info(f"  PASSED: '{finding.title}' (confidence={confidence:.2f})")
            else:
                logger.info(f"  FILTERED: '{finding.title}' (confidence={confidence:.2f})")

        deduped = deduplicate_findings(verified_findings)
        logger.info(f"Debate complete: {len(all_findings)} -> {len(verified_findings)} verified -> {len(deduped)} after dedup")
        return deduped

    def _get_cross_family_verifiers(self, originator_name: str) -> list[BaseAgent]:
        originator_provider = None
        for agent in self.agents:
            if agent.name == originator_name:
                originator_provider = agent.provider
                break

        verifiers = []
        seen_providers = set()
        for agent in self.agents:
            if agent.name == originator_name:
                continue
            if agent.provider != originator_provider and agent.provider not in seen_providers:
                verifiers.append(agent)
                seen_providers.add(agent.provider)
        if len(verifiers) < 2:
            for agent in self.agents:
                if agent.name != originator_name and agent not in verifiers:
                    verifiers.append(agent)
                    if len(verifiers) >= 2:
                        break
        return verifiers[:2]
