"""The crest's game colour, worked out from its bakes (numpy only: crest_game.py uses it inside Blender for its review
renders, crest_dds.py outside it for the game's texture).

The plain cast colour with the emblem's own key light (upper left, in front), fill (right) and a highlight on the
bronze worked in, LIT of the lit: an exterior shader adds the day's light on top, and the facade faces north-north-west,
where the game's light is mostly ambient and a plain colour reads flat. The relief this replaces wore the render's
lighting the same way and read well at a distance.

A thin plate hit from behind (the scales, the fins, the frills: open plates) bakes a normal pointing away from the
surface: its tangent-space z is below 0. Both normal maps are turned round there, or those texels light from behind."""
import numpy as np

LIT = 0.65
KEY = np.array([-7.0, 7.0, 9.0]) / np.linalg.norm([-7.0, 7.0, 9.0])
FILL = np.array([8.0, -3.0, 6.0]) / np.linalg.norm([8.0, -3.0, 6.0])
HALF = (KEY + np.array([0.0, 0.0, 1.0])) / np.linalg.norm(KEY + np.array([0.0, 0.0, 1.0]))

def inward(ntan):
    """ntan: tangent-space normals (-1..1): where they point into the surface"""
    return ntan[..., 2] < 0

def lit_colour(alb_srgb, nobj, spec, ntan):
    """alb_srgb: the plain cast colour (0..1, sRGB); nobj: object-space normals (-1..1); spec: the specular mask (0..1);
    ntan: tangent-space normals (-1..1). Returns the game's colour, sRGB 0..1."""
    nob = nobj / np.maximum(1e-6, np.linalg.norm(nobj, axis=-1, keepdims=True))
    nob = np.where(inward(ntan)[..., None], -nob, nob)
    alb = np.clip(alb_srgb, 0, 1) ** 2.2
    shade = 0.42 + 0.78 * np.clip(nob @ KEY, 0, 1)[..., None] + 0.22 * np.clip(nob @ FILL, 0, 1)[..., None]
    lit = alb * shade + np.array([1.0, 0.82, 0.55]) * 0.55 * spec[..., None] * np.clip(nob @ HALF, 0, 1)[..., None] ** 18
    return np.clip(alb * (1 - LIT) + lit * LIT, 0, 1) ** (1 / 2.2)
