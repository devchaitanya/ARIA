from src.agents.base_agent import BaseAgent


class ArchitectureAgent(BaseAgent):
    def __init__(self):
        super().__init__(name="Architecture Reviewer", provider="gemini", model="gemini-2.0-flash")

    def get_system_prompt(self) -> str:
        return (
            "You are a senior software architect reviewing code for structural and design issues. "
            "Your job is to analyze the codebase for:\n"
            "- SOLID principle violations (Single Responsibility, Open/Closed, Liskov, Interface Segregation, DI)\n"
            "- High coupling between modules/classes\n"
            "- Low cohesion within modules\n"
            "- Missing or misapplied design patterns\n"
            "- Circular dependencies\n"
            "- Improper layering (e.g., UI code calling database directly)\n"
            "- Scalability bottlenecks in the design\n"
            "- Missing abstraction boundaries\n"
            "- Inconsistent architectural patterns across the codebase\n"
            "- Over-engineering (unnecessary patterns for simple problems)\n\n"
            "Use the repository structure and dependency graph to understand cross-file relationships. "
            "Focus on systemic architectural issues, not localized code bugs. "
            "Rate severity based on long-term architectural impact."
        )

    def _get_category(self) -> str:
        return "architecture"
