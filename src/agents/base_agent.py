import json
import time
import logging
import httpx
from abc import ABC, abstractmethod
from dataclasses import dataclass
from google import genai
from src.config import GROQ_API_KEY, GEMINI_API_KEY, MISTRAL_API_KEY, GROQ_MODEL, GEMINI_MODEL, MISTRAL_MODEL

logger = logging.getLogger(__name__)

# Initialize Gemini client once
_gemini_client = genai.Client(api_key=GEMINI_API_KEY) if GEMINI_API_KEY else None

MAX_RETRIES = 3
BASE_DELAY = 2  # seconds


@dataclass
class Finding:
    file: str
    line: int | None
    severity: str  # critical, high, medium, low
    category: str  # security, quality, architecture, performance, ai_slop
    title: str
    description: str
    suggestion: str
    agent: str
    confidence: float = 1.0


def _retry_with_backoff(func, max_retries=MAX_RETRIES, base_delay=BASE_DELAY):
    """Retry a function with exponential backoff on rate limit or server errors."""
    for attempt in range(max_retries):
        try:
            return func()
        except Exception as e:
            err_str = str(e).lower()
            is_retryable = "429" in err_str or "rate" in err_str or "quota" in err_str or "500" in err_str or "503" in err_str
            if is_retryable and attempt < max_retries - 1:
                delay = base_delay * (2 ** attempt)
                logger.warning(f"Rate limited (attempt {attempt+1}/{max_retries}), waiting {delay}s...")
                time.sleep(delay)
            else:
                raise


class BaseAgent(ABC):
    def __init__(self, name: str, provider: str, model: str):
        self.name = name
        self.provider = provider
        self.model = model

    @abstractmethod
    def get_system_prompt(self) -> str:
        pass

    def review(self, files: list[dict], graph_summary: str) -> list[Finding]:
        code_context = self._prepare_context(files)
        system_prompt = self.get_system_prompt()
        user_prompt = self._build_review_prompt(code_context, graph_summary)
        response = self._call_llm(system_prompt, user_prompt)
        return self._parse_findings(response)

    def verify_finding(self, finding: Finding, file_content: str) -> dict:
        system_prompt = (
            "You are a code review verifier. You will be given a finding from another AI reviewer. "
            "Your job is to CONFIRM or REFUTE the finding with clear reasoning. "
            "Respond in JSON: {\"verdict\": \"CONFIRM\" or \"REFUTE\", \"reasoning\": \"...\", \"additional_evidence\": \"...\"}"
        )
        user_prompt = (
            f"Finding to verify:\n"
            f"  File: {finding.file}\n"
            f"  Line: {finding.line}\n"
            f"  Severity: {finding.severity}\n"
            f"  Title: {finding.title}\n"
            f"  Description: {finding.description}\n\n"
            f"Source code of the file:\n```\n{file_content[:8000]}\n```\n\n"
            f"Respond with JSON only."
        )
        response = self._call_llm(system_prompt, user_prompt)
        try:
            clean = response.strip()
            if clean.startswith("```"):
                clean = clean.split("\n", 1)[1].rsplit("```", 1)[0]
            return json.loads(clean)
        except (json.JSONDecodeError, IndexError):
            if "CONFIRM" in response.upper():
                return {"verdict": "CONFIRM", "reasoning": response, "additional_evidence": ""}
            return {"verdict": "REFUTE", "reasoning": response, "additional_evidence": ""}

    def _prepare_context(self, files: list[dict]) -> str:
        parts = []
        total = 0
        for f in files:
            snippet = f["content"][:4000]
            entry = f"--- File: {f['path']} ---\n{snippet}\n"
            if total + len(entry) > 30000:
                break
            parts.append(entry)
            total += len(entry)
        return "\n".join(parts)

    def _build_review_prompt(self, code_context: str, graph_summary: str) -> str:
        return (
            f"Review the following codebase.\n\n"
            f"Repository structure:\n{graph_summary}\n\n"
            f"Source code:\n{code_context}\n\n"
            f"Provide your findings as a JSON array. Each finding must have:\n"
            f'{{"file": "path", "line": number_or_null, "severity": "critical|high|medium|low", '
            f'"category": "{self._get_category()}", "title": "short title", '
            f'"description": "detailed explanation", "suggestion": "how to fix"}}\n\n'
            f"Return ONLY a JSON array. No markdown, no explanation outside the JSON."
        )

    @abstractmethod
    def _get_category(self) -> str:
        pass

    def _parse_findings(self, response: str) -> list[Finding]:
        try:
            clean = response.strip()
            if clean.startswith("```"):
                clean = clean.split("\n", 1)[1].rsplit("```", 1)[0]
            start = clean.find("[")
            end = clean.rfind("]") + 1
            if start >= 0 and end > start:
                clean = clean[start:end]
            items = json.loads(clean)
            findings = []
            for item in items:
                findings.append(Finding(
                    file=item.get("file", "unknown"),
                    line=item.get("line"),
                    severity=item.get("severity", "medium"),
                    category=item.get("category", self._get_category()),
                    title=item.get("title", "Untitled"),
                    description=item.get("description", ""),
                    suggestion=item.get("suggestion", ""),
                    agent=self.name,
                ))
            return findings
        except (json.JSONDecodeError, KeyError, TypeError):
            return []

    # Provider fallback order: try primary, then alternatives
    _PROVIDER_FALLBACK = {
        "groq": ["mistral", "gemini"],
        "gemini": ["mistral", "groq"],
        "mistral": ["groq", "gemini"],
    }

    def _call_llm(self, system_prompt: str, user_prompt: str) -> str:
        providers_to_try = [self.provider] + self._PROVIDER_FALLBACK.get(self.provider, [])
        last_error = None
        for provider in providers_to_try:
            try:
                if provider == "groq" and GROQ_API_KEY:
                    return self._call_groq(system_prompt, user_prompt)
                elif provider == "gemini" and GEMINI_API_KEY:
                    return self._call_gemini(system_prompt, user_prompt)
                elif provider == "mistral" and MISTRAL_API_KEY:
                    return self._call_mistral(system_prompt, user_prompt)
            except Exception as e:
                last_error = e
                logger.warning(f"  {self.name}: {provider} failed ({e.__class__.__name__}), trying fallback...")
                continue
        raise last_error or ValueError(f"No available provider for {self.name}")

    def _call_groq(self, system_prompt: str, user_prompt: str) -> str:
        def _do():
            resp = httpx.post(
                "https://api.groq.com/openai/v1/chat/completions",
                headers={"Authorization": f"Bearer {GROQ_API_KEY}", "Content-Type": "application/json"},
                json={
                    "model": GROQ_MODEL,
                    "messages": [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt},
                    ],
                    "temperature": 0.3,
                    "max_tokens": 4096,
                },
                timeout=120,
            )
            resp.raise_for_status()
            return resp.json()["choices"][0]["message"]["content"]
        return _retry_with_backoff(_do)

    def _call_gemini(self, system_prompt: str, user_prompt: str) -> str:
        def _do():
            response = _gemini_client.models.generate_content(
                model=GEMINI_MODEL,
                contents=user_prompt,
                config=genai.types.GenerateContentConfig(
                    system_instruction=system_prompt,
                    temperature=0.3,
                    max_output_tokens=4096,
                ),
            )
            return response.text
        return _retry_with_backoff(_do)

    def _call_mistral(self, system_prompt: str, user_prompt: str) -> str:
        def _do():
            resp = httpx.post(
                "https://api.mistral.ai/v1/chat/completions",
                headers={"Authorization": f"Bearer {MISTRAL_API_KEY}", "Content-Type": "application/json"},
                json={
                    "model": MISTRAL_MODEL,
                    "messages": [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt},
                    ],
                    "temperature": 0.3,
                    "max_tokens": 4096,
                },
                timeout=120,
            )
            resp.raise_for_status()
            return resp.json()["choices"][0]["message"]["content"]
        return _retry_with_backoff(_do)
