"""What a UI Step reports when it ends (``select_brush``, ``run_action``). Shared by the
Step modules and the App, so every Step has one error path."""

from dataclasses import dataclass

WAITING = "waiting"
DONE = "done"
TIMED_OUT = "timed out"
FAILED = "failed"
MISSING = "missing"  # what the Step needs is not on this machine / in this Painter version


@dataclass(frozen=True)
class StepResult:
    state: str  # DONE, TIMED_OUT, FAILED or MISSING
    message: str = None

    @property
    def ok(self):
        return self.state == DONE
