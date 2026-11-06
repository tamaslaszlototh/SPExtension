"""Copy diagnostics (PRD R10.2): versions plus the end of the log, as plain text."""

from collections import deque
from pathlib import Path

LOG_LINES = 200


def tail_log(log_path, count=LOG_LINES):
    """The last ``count`` lines of the log, reaching into the rotated ``.1`` file if needed."""
    log_path = Path(log_path)
    lines = deque(maxlen=count)
    for path in (log_path.with_name(log_path.name + ".1"), log_path):
        try:
            with open(path, encoding="utf-8", errors="replace") as f:
                for line in f:
                    lines.append(line.rstrip("\r\n"))
        except OSError:
            continue
    return list(lines)


def build_diagnostics(versions, log_lines):
    out = ["Shelf+ diagnostics"]
    out += [f"{name}: {value}" for name, value in versions.items()]
    out += ["", f"Last {len(log_lines)} log lines:"]
    out += list(log_lines)
    return "\n".join(out) + "\n"
