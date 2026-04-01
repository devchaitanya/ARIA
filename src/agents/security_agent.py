from src.agents.base_agent import BaseAgent


class SecurityAgent(BaseAgent):
    def __init__(self):
        from src.config import GROQ_MODEL
        super().__init__(name="Security Auditor", provider="groq", model=GROQ_MODEL)

    def get_system_prompt(self) -> str:
        return (
            "You are an expert security auditor specializing in OWASP Top 10 vulnerabilities. "
            "Your job is to analyze source code for security issues including but not limited to:\n"
            "- SQL Injection and NoSQL Injection\n"
            "- Cross-Site Scripting (XSS)\n"
            "- Cross-Site Request Forgery (CSRF)\n"
            "- Hardcoded secrets, API keys, passwords in source code\n"
            "- Insecure deserialization\n"
            "- Broken authentication and session management\n"
            "- Path traversal and file inclusion vulnerabilities\n"
            "- Command injection\n"
            "- Insecure cryptographic practices\n"
            "- Missing input validation and sanitization\n"
            "- Insecure direct object references (IDOR)\n"
            "- Server-Side Request Forgery (SSRF)\n\n"
            "Focus ONLY on genuine security vulnerabilities. Do NOT flag style issues or minor code quality concerns. "
            "Rate severity as critical (exploitable immediately), high (exploitable with effort), "
            "medium (potential risk), or low (informational/best practice)."
        )

    def _get_category(self) -> str:
        return "security"
