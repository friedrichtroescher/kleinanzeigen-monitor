from dataclasses import dataclass


@dataclass
class EvaluationResult:
    match: bool
    item: str
    reason: str
    error: bool = False
