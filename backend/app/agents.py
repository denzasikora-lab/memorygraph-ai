from __future__ import annotations

AGENTS = ("orchestrator", "planner", "researcher", "reviewer", "summarizer")


def mock_result(agent: str, prompt: str, prior_memory_count: int) -> str:
    templates = {
        "orchestrator": "Task accepted. Route a durable plan before executing specialist work.",
        "planner": "Plan: define deliverables, dependencies, and a checkpoint that can resume safely.",
        "researcher": "Research note: collect evidence relevant to the requested outcome and retain source assumptions.",
        "reviewer": "Review: verify completeness, flag unverified claims, and preserve the decision trail.",
        "summarizer": "Summary: consolidate completed work and name the next action for a future resume.",
    }
    return f"{templates[agent]} Prompt: {prompt}. Earlier memories available: {prior_memory_count}."
