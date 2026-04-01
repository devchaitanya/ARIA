from src.agents.base_agent import BaseAgent


class PerformanceAgent(BaseAgent):
    def __init__(self):
        super().__init__(name="Performance Profiler", provider="mistral", model="mistral-small")

    def get_system_prompt(self) -> str:
        return (
            "You are an expert performance engineer. Your job is to analyze source code for "
            "performance issues including:\n"
            "- O(n²) or worse algorithms where O(n) or O(n log n) solutions exist\n"
            "- N+1 query patterns in database access\n"
            "- Memory leaks and excessive memory allocation\n"
            "- Blocking operations in async contexts\n"
            "- Missing caching for expensive computations\n"
            "- Inefficient string concatenation in loops\n"
            "- Unnecessary object creation in hot paths\n"
            "- Missing connection pooling for database/HTTP clients\n"
            "- Synchronous I/O in performance-critical paths\n"
            "- Large payload serialization without pagination\n\n"
            "Focus on performance issues that would manifest at scale. "
            "Do NOT flag micro-optimizations that are premature. "
            "Rate severity based on likely production performance impact."
        )

    def _get_category(self) -> str:
        return "performance"
