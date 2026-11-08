"""Deterministic, per-post eligibility. Missing or ambiguous data returns needs_check, never a guess."""

from .engine import (
    Evaluation,
    Profile,
    Qualification,
    RuleResult,
    RuleSpec,
    age_on,
    countdown,
    evaluate,
)

__all__ = ["Evaluation", "Profile", "Qualification", "RuleResult", "RuleSpec", "age_on", "countdown", "evaluate"]
