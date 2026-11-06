"""Diagnostics (PRD R10): the text put on the clipboard by Copy diagnostics."""

from shelfplus_app.core.diagnostics import build_diagnostics, tail_log


def test_build_lists_versions_then_log_lines():
    text = build_diagnostics(
        {
            "Shelf+ version": "0.1.0",
            "Loader version": "1",
            "Painter version": "11.1.0",
            "Python version": "3.11.6",
            "Qt version": "6.5.8",
        },
        ["line one", "line two"],
    )

    assert text.splitlines() == [
        "Shelf+ diagnostics",
        "Shelf+ version: 0.1.0",
        "Loader version: 1",
        "Painter version: 11.1.0",
        "Python version: 3.11.6",
        "Qt version: 6.5.8",
        "",
        "Last 2 log lines:",
        "line one",
        "line two",
    ]


def test_tail_returns_the_last_lines(tmp_path):
    log = tmp_path / "shelfplus.log"
    log.write_text("".join(f"line {i}\n" for i in range(500)), encoding="utf-8")

    lines = tail_log(log, 200)

    assert len(lines) == 200
    assert lines[0] == "line 300"
    assert lines[-1] == "line 499"


def test_tail_reaches_into_the_rotated_file(tmp_path):
    log = tmp_path / "shelfplus.log"
    (tmp_path / "shelfplus.log.1").write_text("old 1\nold 2\nold 3\n", encoding="utf-8")
    log.write_text("new 1\n", encoding="utf-8")

    assert tail_log(log, 3) == ["old 2", "old 3", "new 1"]


def test_tail_of_a_missing_log_is_empty(tmp_path):
    assert tail_log(tmp_path / "nothing.log", 200) == []


def test_tail_survives_bad_bytes(tmp_path):
    log = tmp_path / "shelfplus.log"
    log.write_bytes(b"ok\n\xff\xfe broken\n")

    assert tail_log(log, 10)[0] == "ok"
