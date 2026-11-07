"""The real adapter setting a Fill layer channel's source, against a stand-in Painter whose
``set_source`` accepts what Painter 11.1's does: only ``resource.ResourceID``,
``colormanagement.Color`` or an anchor point. (v0.7.4 gave it a plain number for a grey
channel; Painter raised "Unknown parameter type".)"""

import sys
import types

import pytest


class Color:
    def __init__(self, r, g, b):
        self.rgb = (r, g, b)

    @classmethod
    def from_srgb(cls, r, g, b):
        colour = cls(r, g, b)
        colour.from_srgb_input = True
        return colour


class ResourceID:
    def __init__(self, url):
        self.url = url


class FillNode:
    def __init__(self):
        self.sources = {}

    def set_source(self, channel, source):
        if not isinstance(source, (ResourceID, Color)):
            raise ValueError(
                "Unknown parameter type. Only `resource.ResourceID`, `colormanagement.Color` or "
                "`layerstack.AnchorPointEffectNode` are supported"
            )
        self.sources[channel] = source


@pytest.fixture
def adapter(monkeypatch):
    cm = types.ModuleType("substance_painter.colormanagement")
    cm.Color = Color
    ts = types.ModuleType("substance_painter.textureset")
    ts.ChannelType = types.SimpleNamespace(BaseColor="BaseColor", Height="Height", Roughness="Roughness")
    package = types.ModuleType("substance_painter")
    for name, module in (
        ("colormanagement", cm),
        ("textureset", ts),
        ("application", types.ModuleType("a")),
        ("ui", types.ModuleType("u")),
    ):
        setattr(package, name, module)
        monkeypatch.setitem(sys.modules, f"substance_painter.{name}", module)
    monkeypatch.setitem(sys.modules, "substance_painter", package)
    monkeypatch.delitem(sys.modules, "shelfplus_app.adapter.painter", raising=False)
    from shelfplus_app.adapter.painter import PainterAdapter

    adapter = PainterAdapter.__new__(PainterAdapter)
    adapter._resource_id = lambda url: ResourceID(url)
    return adapter


def test_a_grey_value_is_given_as_a_grey_colour_on_the_channels_own_scale(adapter):
    node = FillNode()

    adapter.set_channel_source(node, "Roughness", {"value": 0.7})
    adapter.set_channel_source(node, "Height", {"value": -0.4})

    assert node.sources["Roughness"].rgb == (0.7, 0.7, 0.7)
    assert node.sources["Height"].rgb == (-0.4, -0.4, -0.4)
    # a value is not a colour someone picked: never converted from sRGB
    assert not hasattr(node.sources["Roughness"], "from_srgb_input")


def test_a_colour_is_converted_from_what_the_colour_picker_shows(adapter):
    node = FillNode()

    adapter.set_channel_source(node, "BaseColor", {"color": "#ff0000"})

    assert node.sources["BaseColor"].rgb == (1.0, 0.0, 0.0)
    assert node.sources["BaseColor"].from_srgb_input


def test_a_resource_is_given_by_its_resource_id(adapter):
    node = FillNode()

    adapter.set_channel_source(node, "Height", {"resource": "resource://a/Clouds"})

    assert node.sources["Height"].url == "resource://a/Clouds"


def test_a_masks_fill_gets_its_grey_value_with_no_channel(adapter):
    node = FillNode()

    adapter.set_channel_source(node, None, {"value": 0.3})

    assert node.sources[None].rgb == (0.3, 0.3, 0.3)
