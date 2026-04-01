from src.agents.base_agent import BaseAgent


class QualityAgent(BaseAgent):
    def __init__(self):
        from src.config import GROQ_MODEL_ALT
        super().__init__(name="Code Quality Analyst", provider="groq", model=GROQ_MODEL_ALT)

    def get_system_prompt(self) -> str:
        return (
            "You are an expert code quality analyst. Your job is to analyze source code for "
            "maintainability and quality issues including:\n"
            "- High cyclomatic complexity (deeply nested conditionals, excessive branching)\n"
            "- Code duplication and DRY violations\n"
            "- Dead code and unused variables/imports\n"
            "- Missing or inadequate error handling\n"
            "- Overly long functions or classes (God objects)\n"
            "- Poor naming conventions\n"
            "- Missing type hints or type safety issues\n"
            "- Inconsistent coding patterns within the same file\n"
            "- Magic numbers and hardcoded values that should be constants\n"
            "- Resource leaks (unclosed files, connections, streams)\n\n"
            "Focus on issues that genuinely impact maintainability and long-term code health. "
            "Do NOT flag minor stylistic preferences. Focus on high-impact quality issues. "
            "Rate severity based on impact on maintainability."
        )

    def _get_category(self) -> str:
        return "quality"
