"""Brush buttons without Painter (PRD R5): drop parsing, the icon sources, activating, missing presets."""

import base64

import pytest

from shelfplus_app.adapter.fake import FakeAdapter, FakeResource
from shelfplus_app.core.brush import (
    DONE,
    FAILED,
    MISSING,
    TIMED_OUT,
    WAITING,
    BrushActivation,
    brush_button,
    brush_icon_png,
    pick_brush_icon,
    png_from_preset_file,
    png_from_tooltip,
    resource_urls_from_drop,
    select_brush,
    versionless_url,
)

PNG = b"\x89PNG\r\n\x1a\n" + b"\x00\x00\x00\x0dIHDR" + b"data" + b"\x00\x00\x00\x00IEND\xaeB`\x82"
OTHER_PNG = PNG.replace(b"data", b"more")

ABR = "resource://starter_assets/Kyle Brush Presets/Archive Inker_24?version=0f3c.abr"


# -- drop parsing -------------------------------------------------------------


class TestDropParsing:
    def test_a_url_encoded_resource_becomes_a_version_less_url(self):
        text = "resource://starter_assets/Kyle%20Brush%20Presets/Archive%20Inker_24?version=0f3c.abr\r\n"

        assert resource_urls_from_drop(text) == ["resource://starter_assets/Kyle Brush Presets/Archive Inker_24"]

    def test_several_resources_keep_their_order_and_comments_and_other_urls_are_skipped(self):
        text = (
            "# a comment\r\n"
            "resource://starter_assets/Basic%20Hard?version=1.resource\r\n"
            "file:///C:/brush.png\r\n"
            "\r\n"
            "resource://your_assets/My%20Pen\r\n"
        )

        assert resource_urls_from_drop(text) == [
            "resource://starter_assets/Basic Hard",
            "resource://your_assets/My Pen",
        ]

    def test_the_same_resource_twice_is_added_once(self):
        text = "resource://a/B?version=1\nresource://a/B?version=2\n"

        assert resource_urls_from_drop(text) == ["resource://a/B"]

    @pytest.mark.parametrize("text", ["", "hello", "file:///C:/x.png", None])
    def test_nothing_usable(self, text):
        assert resource_urls_from_drop(text) == []

    @pytest.mark.parametrize(
        "url, expected",
        [
            (ABR, "resource://starter_assets/Kyle Brush Presets/Archive Inker_24"),
            ("resource://starter_assets/Basic Hard", "resource://starter_assets/Basic Hard"),
            ("resource://a/B?version=1&x=2", "resource://a/B?x=2"),
            ("resource://a/B%20C?version=1", "resource://a/B C"),
        ],
    )
    def test_versionless_url(self, url, expected):
        assert versionless_url(url) == expected

    def test_a_brush_button_stores_the_version_less_url_and_the_display_name(self):
        button = brush_button(FakeResource("resource://a/Basic Hard", "Basic Hard"))

        assert button == {"kind": "brush", "name": "Basic Hard", "resource": "resource://a/Basic Hard"}


# -- icon sources ---------------------------------------------------------------


def tooltip_with(png, kind="png"):
    return f'<p>Basic Hard</p><img src="data:image/{kind};base64,{base64.b64encode(png).decode()}" width=256>'


class TestIconSources:
    def test_the_tooltip_png_comes_first(self, tmp_path):
        preset = tmp_path / "Basic Hard.sppr"
        preset.write_bytes(b"head" + OTHER_PNG + b"tail")

        assert brush_icon_png(tooltip_with(PNG), OTHER_PNG, str(preset)) == PNG

    def test_without_a_tooltip_png_the_decoration_image_is_used(self, tmp_path):
        assert brush_icon_png("<p>Basic Hard</p>", OTHER_PNG, None) == OTHER_PNG
        assert brush_icon_png(None, OTHER_PNG, None) == OTHER_PNG

    def test_then_the_png_embedded_in_the_sppr_file(self, tmp_path):
        preset = tmp_path / "Basic Hard.SPPR"  # the extension in any case
        preset.write_bytes(b"head" + PNG + b"tail")

        assert brush_icon_png(None, None, str(preset)) == PNG

    def test_then_nothing_meaning_the_generic_icon(self, tmp_path):
        abr = tmp_path / "Archive Inker.abr"
        abr.write_bytes(PNG)  # only a .sppr is searched

        assert brush_icon_png(None, None, str(abr)) is None
        assert brush_icon_png(None, None, None) is None
        assert brush_icon_png(None, None, str(tmp_path / "gone.sppr")) is None

    def test_the_source_is_named_for_the_log(self, tmp_path):
        preset = tmp_path / "p.sppr"
        preset.write_bytes(PNG)

        assert pick_brush_icon(tooltip_with(PNG), None, None)[1] == "tooltip"
        assert pick_brush_icon(None, PNG, None)[1] == "tile image"
        assert pick_brush_icon(None, None, str(preset))[1] == "preset file"
        assert pick_brush_icon(None, None, None) == (None, "generic")

    def test_the_tooltip_png_is_decoded(self):
        assert png_from_tooltip(tooltip_with(PNG)) == PNG

    @pytest.mark.parametrize(
        "html",
        [
            "<p>no image</p>",
            '<img src="data:image/png;base64,!!!notbase64">',
            tooltip_with(b"GIF89a....", "png"),  # not a PNG after all
            None,
            42,
        ],
    )
    def test_a_tooltip_without_a_usable_png(self, html):
        assert png_from_tooltip(html) is None

    def test_a_preset_file_without_a_complete_png(self, tmp_path):
        cut = tmp_path / "cut.sppr"
        cut.write_bytes(b"head" + PNG[:-10])
        empty = tmp_path / "empty.sppr"
        empty.write_bytes(b"no image here")

        assert png_from_preset_file(str(cut)) is None
        assert png_from_preset_file(str(empty)) is None

    def test_the_preset_file_is_looked_up_only_when_needed(self, tmp_path):
        preset = tmp_path / "Basic Hard.sppr"
        preset.write_bytes(PNG)
        lookups = []

        def path():
            lookups.append(1)
            return str(preset)

        assert brush_icon_png(None, OTHER_PNG, path) == OTHER_PNG
        assert lookups == []
        assert brush_icon_png(None, None, path) == PNG
        assert lookups == [1]

    def test_an_empty_decoration_image_is_skipped(self):
        assert brush_icon_png(None, b"", None) is None


# -- activating -----------------------------------------------------------------


class Clock:
    def __init__(self):
        self.ms = 0

    def __call__(self):
        return self.ms


def resource():
    return FakeResource("resource://starter_assets/Basic Hard", "Basic Hard")


class TestActivationStateMachine:
    def test_opens_the_assets_window_then_shows_the_resource(self):
        adapter = FakeAdapter()
        adapter.add_resource(resource())
        activation = BrushActivation(adapter, resource(), Clock())

        assert activation.start() == WAITING
        assert adapter.assets_calls == ["open", "show_in_ui resource://starter_assets/Basic Hard"]

    def test_clicks_the_tile_once_it_stays_in_the_same_place(self):
        adapter = FakeAdapter()
        clock = Clock()
        activation = BrushActivation(adapter, resource(), clock)
        activation.start()

        adapter.tiles["Basic Hard"] = None  # not in the view yet
        clock.ms = 30
        assert activation.poll() == WAITING
        adapter.tiles["Basic Hard"] = (10, 10, 70, 70)
        clock.ms = 60
        assert activation.poll() == WAITING  # seen once: may still be moving
        assert adapter.clicks == []
        clock.ms = 90
        assert activation.poll() == DONE
        assert adapter.clicks == [(10, 10, 70, 70)]

    def test_a_tile_still_moving_is_not_clicked(self):
        adapter = FakeAdapter()
        clock = Clock()
        activation = BrushActivation(adapter, resource(), clock)
        activation.start()

        for ms, rect in ((30, (0, 0, 70, 70)), (60, (0, 40, 70, 70)), (90, (0, 80, 70, 70))):
            adapter.tiles["Basic Hard"] = rect
            clock.ms = ms
            assert activation.poll() == WAITING
        assert adapter.clicks == []

    def test_times_out_with_a_message(self):
        adapter = FakeAdapter()
        clock = Clock()
        activation = BrushActivation(adapter, resource(), clock, timeout_ms=4000)
        activation.start()

        clock.ms = 3999
        assert activation.poll() == WAITING
        clock.ms = 4001
        assert activation.poll() == TIMED_OUT
        assert activation.message == "“Basic Hard” did not appear in the Assets window within 4 seconds."
        assert adapter.clicks == []

    def test_after_the_end_polling_changes_nothing(self):
        adapter = FakeAdapter()
        clock = Clock()
        activation = BrushActivation(adapter, resource(), clock)
        activation.start()
        clock.ms = 10_000
        activation.poll()

        adapter.tiles["Basic Hard"] = (0, 0, 70, 70)
        assert activation.poll() == TIMED_OUT
        assert activation.poll() == TIMED_OUT
        assert adapter.clicks == []

    def test_no_assets_window_fails_at_once(self):
        adapter = FakeAdapter()
        adapter.assets_window = False
        activation = BrushActivation(adapter, resource(), Clock())

        assert activation.start() == FAILED
        assert activation.message == "The Assets window could not be found."

    def test_an_error_while_polling_is_retried_until_the_time_out(self):
        adapter = FakeAdapter()
        clock = Clock()
        activation = BrushActivation(adapter, resource(), clock)
        activation.start()

        adapter.tile_error = RuntimeError("Internal C++ object already deleted")
        clock.ms = 30
        assert activation.poll() == WAITING
        adapter.tile_error = None
        adapter.tiles["Basic Hard"] = (0, 0, 70, 70)
        activation.poll()
        assert activation.poll() == DONE

    def test_a_failing_click_fails(self):
        adapter = FakeAdapter()
        activation = BrushActivation(adapter, resource(), Clock())
        activation.start()
        adapter.tiles["Basic Hard"] = (0, 0, 70, 70)
        adapter.click_error = RuntimeError("gone")

        activation.poll()
        assert activation.poll() == FAILED
        assert activation.message == "“Basic Hard” could not be clicked in the Assets window."


class TestSelectBrushStep:
    """``select_brush`` is the Step a Brush button runs; the Workflow runner calls it too."""

    def test_a_preset_found_is_activated_by_polling_on_a_timer(self):
        adapter = FakeAdapter()
        adapter.add_resource(resource())
        results = []

        select_brush(adapter, {"type": "select_brush", "resource": "resource://starter_assets/Basic Hard"}, results.append)

        assert len(adapter.timers) == 1 and adapter.timers[0].active
        adapter.tiles["Basic Hard"] = (0, 0, 70, 70)
        adapter.fire_timers()
        assert results == []
        adapter.fire_timers()
        assert [(r.state, r.message) for r in results] == [(DONE, None)]
        assert not adapter.timers[0].active
        assert adapter.clicks == [(0, 0, 70, 70)]

    def test_a_missing_preset_only_reports_it(self):
        adapter = FakeAdapter()
        results = []

        handle = select_brush(adapter, {"type": "select_brush", "resource": "resource://a/Gone"}, results.append)

        assert handle is None
        assert [(r.state, r.message) for r in results] == [
            (MISSING, "This brush is not available on this machine: resource://a/Gone")
        ]
        assert adapter.assets_calls == [] and adapter.timers == []

    def test_the_time_out_is_reported_once_and_the_timer_stops(self):
        adapter = FakeAdapter()
        adapter.add_resource(resource())
        clock = Clock()
        results = []
        select_brush(adapter, {"type": "select_brush", "resource": resource().url}, results.append, now=clock)

        clock.ms = 5000
        adapter.fire_timers()
        adapter.fire_timers()

        assert [r.state for r in results] == [TIMED_OUT]
        assert not adapter.timers[0].active

    def test_cancelling_stops_the_timer_without_a_result(self):
        adapter = FakeAdapter()
        adapter.add_resource(resource())
        results = []
        handle = select_brush(adapter, {"type": "select_brush", "resource": resource().url}, results.append)

        handle.cancel()
        adapter.tiles["Basic Hard"] = (0, 0, 70, 70)
        adapter.fire_timers()

        assert results == [] and adapter.clicks == []
        assert not adapter.timers[0].active

    def test_a_resource_that_cannot_be_looked_up_counts_as_missing(self):
        adapter = FakeAdapter()
        adapter.resource_error = RuntimeError("no project")
        results = []

        select_brush(adapter, {"type": "select_brush", "resource": "resource://a/B"}, results.append)

        assert [r.state for r in results] == [MISSING]
