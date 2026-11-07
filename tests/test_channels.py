"""A Fill layer channel's uniform value: each channel's own range and starting value, as
Painter's Fill layer properties offer them."""

import pytest

from shelfplus_app.core.channels import default_source, value_range
from shelfplus_app.core.layout import step_problem


def fill_with(channel, value):
    return {"type": "add_layer", "layer": "fill", "sources": {channel: {"value": value}}}


@pytest.mark.parametrize(
    "channel, low, high",
    [
        ("Height", -1, 1),
        ("Displacement", -1, 1),
        ("Roughness", 0, 1),
        ("Metallic", 0, 1),
        ("Opacity", 0, 1),
        ("User0", 0, 1),  # a channel not in the table: 0 to 1
    ],
)
def test_each_channel_has_its_own_range(channel, low, high):
    assert value_range(channel) == (low, high)


def test_a_value_inside_its_channels_range_is_valid_and_outside_is_not():
    assert step_problem(fill_with("Height", -0.4)) is None
    assert step_problem(fill_with("Height", -1.5)) == "Step 'add_layer' has an invalid 'sources'"
    assert step_problem(fill_with("Roughness", -0.1)) == "Step 'add_layer' has an invalid 'sources'"
    low, high = value_range("Ior")
    assert step_problem(fill_with("Ior", high)) is None and step_problem(fill_with("Ior", high + 1)) is not None


def test_a_normal_starts_flat_and_greys_start_where_painter_starts_them():
    assert default_source("Normal") == {"color": "#8080ff"}
    assert default_source("BaseColor") == {"color": "#808080"}
    assert default_source("Height") == {"value": 0}
    assert default_source("Metallic") == {"value": 0}
    low, high = value_range("Ior")
    assert low <= default_source("Ior")["value"] <= high
