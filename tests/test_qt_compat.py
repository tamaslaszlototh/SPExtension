"""Qt calls that exist in the PySide6 of Painter 11.1 (6.5). Tests run on a newer PySide6,
where these calls work, so they are checked in the source instead."""

import ast
from pathlib import Path

UI = Path(__file__).parents[1] / "src" / "ShelfPlus" / "bundled" / "shelfplus_app"


def test_single_shot_is_never_given_a_context_object():
    """``QTimer.singleShot(ms, context, callable)`` raises TypeError on PySide6 6.5 (only
    ``(ms, callable)`` and ``(ms, receiver, b"slot()")`` exist): a drop in the Workflow
    editor was lost to it on Painter 11.1. Use a QTimer parented to the widget instead."""
    calls = []
    for path in sorted(UI.rglob("*.py")):
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            if (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Attribute)
                and node.func.attr == "singleShot"
                and len(node.args) != 2
            ):
                calls.append(f"{path.relative_to(UI)}:{node.lineno}")

    assert calls == []
