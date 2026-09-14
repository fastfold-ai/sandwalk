"""Per-model token pricing and cumulative usage tracking."""

from __future__ import annotations

from dataclasses import dataclass, field

# Pricing per million tokens (USD) — updated Jul 2026
MODEL_PRICING = {
    # Anthropic (https://platform.claude.com/docs/en/about-claude/models/overview)
    "claude-opus-5": {"input": 5.00, "output": 25.00},
    "claude-sonnet-5": {"input": 3.00, "output": 15.00},
    "claude-fable-5-1": {"input": 10.00, "output": 50.00},
    "claude-fable-5": {"input": 10.00, "output": 50.00},
    "claude-sonnet-4-5-20250929": {"input": 3.00, "output": 15.00},
    "claude-haiku-4-5-20251001": {"input": 1.00, "output": 5.00},
    "claude-opus-4-8": {"input": 5.00, "output": 25.00},
    "claude-opus-4-6": {"input": 5.00, "output": 25.00},
    # OpenAI
    "gpt-4o": {"input": 2.50, "output": 10.00},
    "gpt-4o-mini": {"input": 0.15, "output": 0.60},
}


@dataclass
class UsageTracker:
    """Tracks cumulative token usage and cost across LLM calls."""
    calls: list = field(default_factory=list)

    @property
    def total_input_tokens(self) -> int:
        return sum(c.get("input", 0) for c in self.calls)

    @property
    def total_output_tokens(self) -> int:
        return sum(c.get("output", 0) for c in self.calls)

    @property
    def total_tokens(self) -> int:
        return self.total_input_tokens + self.total_output_tokens

    @property
    def total_cost(self) -> float:
        return sum(c.get("cost", 0.0) for c in self.calls)

    def record(self, model: str, usage: dict):
        """Record a single LLM call's usage."""
        if not usage:
            return
        cost = self._estimate_cost(model, usage)
        self.calls.append({
            "model": model,
            "input": usage.get("input", 0),
            "output": usage.get("output", 0),
            "cost": cost,
        })

    def _estimate_cost(self, model: str, usage: dict) -> float:
        pricing = MODEL_PRICING.get(model)
        if not pricing:
            return 0.0
        input_cost = (usage.get("input", 0) / 1_000_000) * pricing["input"]
        output_cost = (usage.get("output", 0) / 1_000_000) * pricing["output"]
        return input_cost + output_cost

    def summary(self) -> str:
        """Human-readable usage summary."""
        if not self.calls:
            return "No LLM calls made."
        models_used = {c["model"] for c in self.calls}
        return (
            f"{len(self.calls)} LLM calls | "
            f"{self.total_input_tokens:,} in + {self.total_output_tokens:,} out tokens | "
            f"${self.total_cost:.2f} | "
            f"models: {', '.join(models_used)}"
        )

    def reset(self):
        self.calls.clear()
