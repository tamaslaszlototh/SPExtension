"""Pure layout decisions for the Panel (PRD R2.3): tall/flat, grid columns, drop position, edge scrolling."""

import pytest

from shelfplus_app.core.flow import drop_index, edge_scroll, grid_columns, orientation


class TestOrientation:
    @pytest.mark.parametrize(
        "width, height, expected",
        [
            (300, 900, "tall"),  # docked on the right
            (400, 400, "tall"),  # square floating window
            (1200, 90, "flat"),  # strip
            (800, 400, "flat"),  # exactly twice as wide as tall
            (790, 400, "tall"),
        ],
    )
    def test_from_scratch(self, width, height, expected):
        assert orientation(width, height) == expected

    def test_a_flat_panel_stays_flat_until_it_is_clearly_not_wide(self):
        assert orientation(700, 400, current="flat") == "flat"
        assert orientation(600, 400, current="flat") == "tall"

    def test_a_tall_panel_needs_twice_the_height_in_width_to_turn_flat(self):
        assert orientation(700, 400, current="tall") == "tall"

    def test_an_empty_size_is_tall(self):
        assert orientation(0, 0) == "tall"


class TestGridColumns:
    def test_as_many_tiles_as_fit_with_spacing_between(self):
        # 3 tiles of 48 with 4 between: 48*3 + 4*2 = 152
        assert grid_columns(152, 48, 4) == 3
        assert grid_columns(151, 48, 4) == 2

    def test_at_least_one_column(self):
        assert grid_columns(10, 48, 4) == 1


class TestEdgeScroll:
    """While a Button is dragged, holding it near an edge of the scroll area scrolls it."""

    def test_near_the_start_scrolls_back(self):
        assert edge_scroll(5, 300, edge=24, step=16) == -16

    def test_near_the_end_scrolls_forward(self):
        assert edge_scroll(290, 300, edge=24, step=16) == 16

    def test_in_the_middle_does_nothing(self):
        assert edge_scroll(150, 300, edge=24, step=16) == 0
        assert edge_scroll(24, 300, edge=24, step=16) == 0
        assert edge_scroll(275, 300, edge=24, step=16) == 0
        assert edge_scroll(276, 300, edge=24, step=16) == 16  # the last 24 px, like 0-23 at the start

    def test_outside_the_area_does_nothing(self):
        assert edge_scroll(-1, 300, edge=24, step=16) == 0
        assert edge_scroll(300, 300, edge=24, step=16) == 0

    def test_an_area_too_small_for_two_edges_does_nothing(self):
        assert edge_scroll(10, 40, edge=24, step=16) == 0


class TestDropIndex:
    # Two rows of tiles 40x40 with 4 px spacing: (0,0) (44,0) (88,0) / (0,44)
    RECTS = [(0, 0, 40, 40), (44, 0, 40, 40), (88, 0, 40, 40), (0, 44, 40, 40)]

    @pytest.mark.parametrize(
        "x, y, expected",
        [
            (5, 20, 0),  # left half of the first tile
            (30, 20, 1),  # right half of the first tile
            (70, 20, 2),
            (200, 20, 3),  # right of the first row: end of that row
            (5, 60, 3),
            (35, 60, 4),
            (100, 60, 4),
            (5, 200, 4),  # below everything: the end
        ],
    )
    def test_insert_position_from_the_cursor(self, x, y, expected):
        assert drop_index(self.RECTS, x, y) == expected

    def test_a_flat_row(self):
        rects = [(100, 0, 40, 40), (144, 0, 40, 40)]
        assert drop_index(rects, 50, 20) == 0
        assert drop_index(rects, 170, 20) == 2

    def test_no_tiles(self):
        assert drop_index([], 10, 10) == 0
