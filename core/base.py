"""Common contract every asset mode (stocks, IPO, funds, ...) implements.

Pipeline: fetch() -> score() -> explain().  Every verdict must be explainable:
explain() returns the reasons behind the score, never just a label.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field


@dataclass
class Reason:
    """One rule that fired, in plain language."""
    rule: str
    passed: bool
    detail: str
    points: float = 0.0
    max_points: float = 0.0
    available: bool = True      # False when the data needed was missing


@dataclass
class Analysis:
    score: float                      # 0-100
    verdict: str                      # e.g. "Bullish", "Avoid"
    reasons: list[Reason] = field(default_factory=list)
    risks: list[str] = field(default_factory=list)
    data_as_of: str = ""
    source: str = ""


class AssetAnalyzer(ABC):
    """Base class for all modes. Subclasses must stay rule-based (no ML)."""

    @abstractmethod
    def fetch(self, identifier: str):
        """Load raw data for one asset."""

    @abstractmethod
    def score(self, data) -> float:
        """Return a 0-100 score from explicit rules."""

    @abstractmethod
    def explain(self, data) -> Analysis:
        """Return the full analysis, including the reasons for the score."""
