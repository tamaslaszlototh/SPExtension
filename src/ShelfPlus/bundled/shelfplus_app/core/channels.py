"""Texture set channels as a new layer's settings use them: which ones are offered, which
take a colour, and the range and starting value of the others' uniform value.

The ranges follow Painter's Fill layer properties. They are not readable through
Painter's Python API, so they live here; a channel missing from the table takes 0 to 1.
"""

# The channels offered for a new layer when Painter cannot list the texture set's own.
DEFAULT_CHANNELS = ["BaseColor", "Height", "Roughness", "Metallic", "Normal", "Emissive", "Opacity", "Specular"]

# Channels whose uniform value is a colour, and the colour they start with.
COLOUR_CHANNELS = {
    "BaseColor": "#808080",
    "Diffuse": "#808080",
    "Specular": "#383838",  # Painter's 0.04 reflectance
    "SpecularEdgeColor": "#ffffff",
    "Emissive": "#000000",
    "Normal": "#8080ff",  # a flat normal: (0.5, 0.5, 1)
    "ScatterColor": "#ffffff",
    "SheenColor": "#ffffff",
    "CoatColor": "#ffffff",
    "Transmissive": "#000000",
    "Reflection": "#ffffff",
}

# The other channels: (lowest, highest, starting value).
VALUE_CHANNELS = {
    "Height": (-1, 1, 0),
    "Displacement": (-1, 1, 0),
    "Roughness": (0, 1, 0.3),
    "Metallic": (0, 1, 0),
    "Opacity": (0, 1, 1),
    "AO": (0, 1, 1),
    "Glossiness": (0, 1, 0.7),
    "Specularlevel": (0, 1, 0.5),
    "Ior": (1, 3, 1.5),
    "AnisotropyLevel": (0, 1, 0),
    "AnisotropyAngle": (0, 1, 0),
    "Translucency": (0, 1, 0),
    "Scattering": (0, 1, 0),
    "SheenOpacity": (0, 1, 0),
    "SheenRoughness": (0, 1, 0.3),
    "CoatOpacity": (0, 1, 0),
    "CoatRoughness": (0, 1, 0),
    "CoatSpecularLevel": (0, 1, 0.5),
    "BlendingMask": (0, 1, 1),
}
DEFAULT_VALUE = (0, 1, 0.5)


def is_colour(channel):
    return channel in COLOUR_CHANNELS


def value_range(channel):
    """``(lowest, highest)`` of a channel's uniform value."""
    low, high, _ = VALUE_CHANNELS.get(channel, DEFAULT_VALUE)
    return low, high


def default_source(channel):
    """What a Fill layer channel starts with when set "Per channel"."""
    if is_colour(channel):
        return {"color": COLOUR_CHANNELS[channel]}
    return {"value": VALUE_CHANNELS.get(channel, DEFAULT_VALUE)[2]}
