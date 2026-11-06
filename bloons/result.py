"""ActionResult: what every harness action and guard returns (PLAN "Harness API"). Portable."""
from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class ActionResult:
    ok: bool
    reason: str = ""
    cost: Optional[int] = None      # $ the action would cost (negative = refund, e.g. a sale)

    def __bool__(self):
        return self.ok
