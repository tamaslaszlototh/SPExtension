"""The pen hover helper's timing (PRD R2.6): show a name after ~600 ms over one element, hide on leave."""

from shelfplus_app.core.hover import HIDE, SHOW, HoverTracker

TILE, PLUS = object(), object()


def test_the_name_shows_after_the_delay_over_the_same_element():
    hover = HoverTracker(delay_ms=600)

    assert hover.tick(0, TILE, "Save") is None
    assert hover.tick(500, TILE, "Save") is None
    assert hover.tick(600, TILE, "Save") == (SHOW, "Save")
    assert hover.tick(700, TILE, "Save") is None  # shown once, not every tick


def test_moving_to_another_element_hides_and_restarts_the_delay():
    hover = HoverTracker(delay_ms=600)
    hover.tick(0, TILE, "Save")
    hover.tick(600, TILE, "Save")

    assert hover.tick(700, PLUS, "Add a Button") == (HIDE,)
    assert hover.tick(1200, PLUS, "Add a Button") is None
    assert hover.tick(1300, PLUS, "Add a Button") == (SHOW, "Add a Button")


def test_leaving_the_panel_hides():
    hover = HoverTracker(delay_ms=600)
    hover.tick(0, TILE, "Save")
    hover.tick(600, TILE, "Save")

    assert hover.tick(700, None, "") == (HIDE,)
    assert hover.tick(2000, None, "") is None


def test_passing_over_an_element_quickly_shows_nothing_and_hides_nothing():
    hover = HoverTracker(delay_ms=600)

    assert hover.tick(0, TILE, "Save") is None
    assert hover.tick(300, PLUS, "Add a Button") is None
    assert hover.tick(400, None, "") is None


def test_an_element_without_a_name_shows_nothing():
    hover = HoverTracker(delay_ms=600)

    hover.tick(0, TILE, "")
    assert hover.tick(1000, TILE, "") is None


def test_a_changed_name_on_the_same_element_is_shown():
    hover = HoverTracker(delay_ms=600)
    hover.tick(0, TILE, "Save")
    hover.tick(600, TILE, "Save")

    assert hover.tick(700, TILE, "Quick save") == (SHOW, "Quick save")


def test_the_name_hides_when_the_element_loses_it():
    hover = HoverTracker(delay_ms=600)
    hover.tick(0, TILE, "Save")
    hover.tick(600, TILE, "Save")

    assert hover.tick(700, TILE, "") == (HIDE,)


def test_a_tip_qt_hid_by_itself_shows_again_after_the_delay():
    hover = HoverTracker(delay_ms=600)
    hover.tick(0, TILE, "Save")
    hover.tick(600, TILE, "Save")

    assert hover.tick(700, TILE, "Save", showing=False) is None
    assert hover.tick(1200, TILE, "Save", showing=False) is None
    assert hover.tick(1300, TILE, "Save", showing=False) == (SHOW, "Save")
