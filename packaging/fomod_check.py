"""Reads a packaged archive's installer the way a mod manager does and checks what each choice installs.
usage: python fomod_check.py <archive.zip> <staging folder>      (package.sh runs it after packaging)

For every choice the installer's groups allow (SelectExactlyOne: one option; SelectAny: any set; ...; here the Guild Hall page:
the dedicated hall, or none), it works out the installed files (destination path -> archive entry) from fomod/ModuleConfig.xml,
and checks:
  - info.xml and ModuleConfig.xml parse, with nothing left unfilled (@...@), and the elements in the order schema 5.0 requires;
  - every source folder or file the installer names is in the archive, and every archive entry outside fomod/ is installed by
    some choice (nothing packed for nobody);
  - no two entries install to the same path (paths compared without case, as Windows does);
  - the default choice is everything the installer marks Recommended or Required, and it equals the staging folder: core + hall
    + docs (to docs/Adventurers Guild/), byte for byte;
  - without the hall, both plugins' rule holds: the core plugin and DLL go in, nothing of the hall does (its plugin, its
    SKSE/Plugins/AdventurersGuild/Hall/ data, its scripts, meshes, textures and voices).
"""
import hashlib, itertools, os, re, sys, zipfile
import xml.etree.ElementTree as ET

CORE_MUST = ["AdventurersGuild.esp", "SKSE/Plugins/AdventurersGuild.dll"]
HALL_ESP = "AdventurersGuild - Guild Hall.esp"
ORDER = {  # schema 5.0 (ModConfig5.0.xsd): each element's children, in the order allowed
    "config": ["moduleName", "moduleImage", "moduleDependencies", "requiredInstallFiles", "installSteps", "conditionalFileInstalls"],
    "installStep": ["visible", "optionalFileGroups"],
    "plugin": ["description", "image", "files", "conditionFlags", "typeDescriptor"],
}

zpath, stage = sys.argv[1], sys.argv[2]
z = zipfile.ZipFile(zpath)
names = [n for n in z.namelist() if not n.endswith("/")]
bad = []


def order_ok(el):
    want = ORDER.get(el.tag)
    if want:
        seen = [want.index(c.tag) if c.tag in want else -1 for c in el]
        if -1 in seen or seen != sorted(seen):
            bad.append(f"ModuleConfig.xml: <{el.tag}> children out of the schema's order or unknown: {[c.tag for c in el]}")
    for c in el:
        order_ok(c)


for f in ("fomod/info.xml", "fomod/ModuleConfig.xml"):
    if f not in names:
        sys.exit(f"FAILED - {f} is not in the archive")
    t = z.read(f).decode("utf-8")
    if re.search(r"@[A-Z_]+@", t):
        bad.append(f"{f}: a placeholder was not filled in")
info = ET.fromstring(z.read("fomod/info.xml"))
cfg = ET.fromstring(z.read("fomod/ModuleConfig.xml"))
order_ok(cfg)
version = info.findtext("Version")


def expand(files_el):
    """<files>/<requiredInstallFiles>: [(destination, entry)]"""
    out = []
    for el in files_el:
        src = el.get("source").replace("\\", "/").strip("/")
        dst = (el.get("destination") or "").replace("\\", "/").strip("/")
        if el.tag == "folder":
            hit = [n for n in names if n.startswith(src + "/")]
            if not hit:
                bad.append(f"the installer names folder '{src}', which is not in the archive (or is empty)")
            out += [((dst + "/" if dst else "") + n[len(src) + 1:], n) for n in hit]
        elif el.tag == "file":
            if src not in names:
                bad.append(f"the installer names file '{src}', which is not in the archive")
            out.append((dst or os.path.basename(src), src))
    return out


rif = cfg.find("requiredInstallFiles")
required = expand(rif if rif is not None else [])
options = []  # (name, type, [(dst, entry)])
groups = []  # (group name, type, [option names])
for g in cfg.iter("group"):
    names_in = []
    for p in g.iter("plugin"):
        t = p.find("typeDescriptor/type")
        fl = p.find("files")
        if fl is None and p.find("conditionFlags") is None:
            bad.append(f"option '{p.get('name')}' has neither files nor conditionFlags (schema 5.0 needs one)")
        options.append((p.get("name"), t.get("name") if t is not None else "?", expand(fl if fl is not None else [])))
        names_in.append(p.get("name"))
    groups.append((g.get("name"), g.get("type"), names_in))
kind = {o[0]: o[1] for o in options}


def picks(gtype, opts):
    """the selections a group of this type allows"""
    subsets = [set(c) for r in range(len(opts) + 1) for c in itertools.combinations(opts, r)]
    rule = {"SelectExactlyOne": lambda s: len(s) == 1, "SelectAtMostOne": lambda s: len(s) <= 1,
            "SelectAtLeastOne": lambda s: len(s) >= 1, "SelectAll": lambda s: len(s) == len(opts), "SelectAny": lambda s: True}
    if gtype not in rule:
        bad.append(f"group type {gtype} is not one schema 5.0 knows")
        return [set()]
    return [s for s in subsets if rule[gtype](s)]


def install(chosen):
    m, lower = {}, {}
    for dst, entry in required + [x for o in options if o[0] in chosen for x in o[2]]:
        k = dst.lower()
        if k in lower and lower[k] != entry:
            bad.append(f"two archive entries install to {dst}: {lower[k]} and {entry} (choice: {sorted(chosen) or 'none'})")
        lower[k] = entry
        m[dst] = entry
    return m


everything = install({o[0] for o in options})
orphans = sorted(set(n for n in names if not n.startswith("fomod/")) - set(everything.values()))
bad += [f"packed but never installed: {n}" for n in orphans[:20]]
default = set()
for gname, gtype, opts in groups:
    pre = {o for o in opts if kind[o] in ("Recommended", "Required")}
    if pre not in picks(gtype, opts):
        bad.append(f"group '{gname}' ({gtype}): its preselected options {sorted(pre)} are not a choice the group allows")
    default |= pre
hall_opts = {o[0] for o in options if any(e.startswith("01 Guild Hall/") for _, e in o[2])}
combos = [set().union(*c) for c in itertools.product(*[picks(t, o) for _, t, o in groups])] if groups else [set()]
without = 0
for combo in combos:
    got = install(combo)
    keys = {k.lower() for k in got}
    for f in CORE_MUST:
        if f.lower() not in keys:
            bad.append(f"choice {sorted(combo) or 'none'}: the core's {f} is not installed")
    if not combo & hall_opts:
        without += 1
        hall_entries = [k for k, e in got.items() if e.startswith("01 Guild Hall/")]
        if HALL_ESP.lower() in keys or hall_entries or any(k.startswith("skse/plugins/adventurersguild/hall/") for k in keys):
            bad.append(f"choice {sorted(combo) or 'none'}: no hall chosen, but hall files are still installed ({len(hall_entries)})")
if not without:
    bad.append("no choice installs the core without the hall")
if not default & hall_opts:
    bad.append("the default choice does not install the hall")

# the default install against the staging folder, byte for byte
d = install(default)
want = {}
for top, dst in (("00 Core", ""), ("01 Guild Hall", ""), ("docs", "docs/Adventurers Guild")):
    root = os.path.join(stage, top)
    for dp, _, fs in os.walk(root):
        for f in fs:
            rel = os.path.relpath(os.path.join(dp, f), root).replace("\\", "/")
            want[(dst + "/" if dst else "") + rel] = os.path.join(dp, f)
if set(d) != set(want):
    bad.append(f"the default install differs from the staging folder: {len(set(d) - set(want))} extra, {len(set(want) - set(d))} missing")
else:
    for k, p in want.items():
        if hashlib.blake2b(z.read(d[k]), digest_size=16).digest() != hashlib.blake2b(open(p, "rb").read(), digest_size=16).digest():
            bad.append(f"the archive's {d[k]} differs from the staged file")

if bad:
    print("INSTALLER CHECK FAILED:", *bad[:40], sep="\n  ")
    sys.exit(1)
off = install(next(c for c in combos if not c & hall_opts))
print(f"installer check: version {version}; {len(combos)} possible choice(s); the default ({', '.join(sorted(default))}) installs {len(d)} files, "
      f"same as staged; without the hall ({', '.join(sorted(next(c for c in combos if not c & hall_opts))) or 'nothing'}) {len(off)} files, "
      f"none of the hall's; no conflicts, nothing orphaned")
