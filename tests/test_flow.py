"""Pure layout decisions for the Panel (PRD R2.3): tall/flat, grid columns, overflow, drop position."""

import pytest

from shelfplus_app.core.flow import drop_index, fit_flat_row, grid_columns, orientation


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


class TestFitFlatRow:
    # Row: [header][tiles...] [gap] [header][tiles...] ... [»]
    # A Group is header + count * (spacing + tile). Groups are separated by `gap`.

    def test_everything_fits_so_nothing_overflows(self):
        groups = [(60, 3), (50, 2)]
        width = (60 + 3 * 44) + 10 + (50 + 2 * 44)
        assert fit_flat_row(width, groups, tile=40, spacing=4, gap=10, overflow_width=24) == [3, 2]

    def test_buttons_that_do_not_fit_leave_room_for_the_overflow_button(self):
        groups = [(60, 3), (50, 2)]
        width = (60 + 3 * 44) + 10 + (50 + 2 * 44) - 1
        # all of it is 340. Without the last tile 296 is used, and the » needs 4 + 24 more: 324 <= 339.
        assert fit_flat_row(width, groups, tile=40, spacing=4, gap=10, overflow_width=24) == [3, 1]

    def test_the_overflow_button_can_push_out_more_than_one_tile(self):
        groups = [(60, 4)]
        # all four: 60 + 176 = 236. Width 230: three tiles = 192, plus » (28) = 220 fits.
        assert fit_flat_row(230, groups, tile=40, spacing=4, gap=10, overflow_width=24) == [3]
        # width 215: three tiles + » = 220 is too much, two tiles + » = 176 fits.
        assert fit_flat_row(215, groups, tile=40, spacing=4, gap=10, overflow_width=24) == [2]

    def test_a_group_whose_header_does_not_fit_is_hidden_with_all_later_groups(self):
        groups = [(60, 1), (50, 2), (50, 0)]
        # first group 104, gap 10, second header 50 -> 164; plus » 28 = 192
        assert fit_flat_row(150, groups, tile=40, spacing=4, gap=10, overflow_width=24) == [1, None, None]

    def test_a_header_that_fits_with_no_tiles_shows_zero(self):
        groups = [(60, 1), (50, 2)]
        # 104 + 10 + 50 = 164, + » 28 = 192
        assert fit_flat_row(192, groups, tile=40, spacing=4, gap=10, overflow_width=24) == [1, 0]

    def test_after_a_cut_group_later_groups_are_hidden_even_if_their_header_would_fit(self):
        groups = [(60, 3), (10, 0)]
        # all: 192 + 10 + 10 = 212. Width 200: budget 172 -> two tiles (148); a 10 px header would fit.
        assert fit_flat_row(200, groups, tile=40, spacing=4, gap=10, overflow_width=24) == [2, None]

    def test_collapsed_groups_count_as_zero_tiles(self):
        assert fit_flat_row(100, [(60, 0), (30, 0)], tile=40, spacing=4, gap=10, overflow_width=24) == [0, 0]

    def test_no_groups(self):
        assert fit_flat_row(100, [], tile=40, spacing=4, gap=10, overflow_width=24) == []


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
