"""The hall's settings for its Python tools, as env.sh gives them to its scripts: AG's local.env (the environment wins), the test
installs (HALL_INSTALLS: name|mod folder|game exe;...) and the hall's folders.
    from hallenv import cfg, installs, AG_ROOT, HALL_PRIVATE, HALL_WORK, HALL_BUILD"""
import os

AG_ROOT = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))


def _load():
    v = {}
    p = os.path.join(AG_ROOT, "local.env")
    if os.path.exists(p):
        for l in open(p, encoding="utf-8"):
            l = l.rstrip("\r\n")
            if l and not l.startswith("#") and "=" in l: k, x = l.split("=", 1); v[k] = x
    v.update({k: x for k, x in os.environ.items() if k in v or k.startswith(("HALL_", "SKYRIM_", "BLENDER", "TEXCONV"))})
    return v


_CFG = _load()


def cfg(key, default=None):
    """a setting from local.env (or the environment)"""
    return _CFG.get(key, default)


def installs(optional=False):
    """[(name, mod folder, game exe)] of the test installs, the optional ones too if asked"""
    out = []
    for key in ("HALL_INSTALLS",) + (("HALL_INSTALLS_OPTIONAL",) if optional else ()):
        for e in (cfg(key) or "").split(";"):
            if e.strip(): n, d, x = (e.split("|") + ["", "", ""])[:3]; out.append((n, d, x))
    return out


HALL_PRIVATE = cfg("HALL_PRIVATE") or os.path.join(AG_ROOT, "tools", "hall-private")
HALL_WORK = cfg("HALL_WORK") or os.path.join(AG_ROOT, "build", "hall-work")
HALL_BUILD = cfg("HALL_BUILD") or os.path.join(AG_ROOT, "build", "hall")
TEXCONV = cfg("TEXCONV") or "texconv"
