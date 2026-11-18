"""Builds the FOMOD archive from package.sh's staging folder (package.sh runs it; see there).

  1. The halls: build/hall (Riverwood's) copied to "01 Guild Hall" and build/hall-solitude to "02 Guild Hall Solitude", less the
     build-only files (BUILD_ONLY).
  2. "00 Core" + each hall must not share a file; given a deployed folder (--deployed/--deployed2, optional: a release is built
     fresh from its commit and has none), together they must equal it, byte for byte (its meta.ini and docs/ aside). Anything only in the deployed folder (a file an earlier build left there)
     or only in the package, or different, refuses: the archive would not be what was tested.
  3. Privacy: every compiled script's header (.pex) names where, by whom and on which computer it was compiled; each gets neutral
     names. Then every file but images, audio and fonts is searched for this machine's paths and the words in PRIVATE_WORDS
     (local.env); any hit refuses.
  4. docs/ and fomod/ (info.xml with the version filled in), then the zip.
"""
import argparse, hashlib, os, re, shutil, struct, sys, zipfile

BUILD_ONLY = re.compile(r"(\.esp\.unmerged$|(^|/)hall-owners\.json$)", re.I)
DOCS = [("docs/TRANSLATING.md", "TRANSLATING.md"), ("LICENSE", "LICENSE.txt"), ("EXCEPTIONS.md", "EXCEPTIONS.md"),
        ("CHANGELOG.md", "CHANGELOG.md"), ("docs/DOWNLOAD_README.txt", "README.txt"), ("ASSETS.md", "ASSETS.md"),
        ("THIRD_PARTY_NOTICES.md", "THIRD_PARTY_NOTICES.md")]
NOT_SCANNED = (".dds", ".png", ".jpg", ".jpeg", ".fuz", ".wav", ".xwm", ".lip", ".ttf", ".otf", ".woff", ".woff2")


def files(root):
    out = {}
    for dp, _, fs in os.walk(root):
        for f in fs:
            p = os.path.join(dp, f)
            out[os.path.relpath(p, root).replace("\\", "/")] = p
    return out


def digest(p):
    h = hashlib.blake2b(digest_size=16)
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.digest()


def scrub_pex(path):
    """A Skyrim .pex (big-endian): magic, version, game, compile time, then three strings of a 16-bit length (source, user,
    computer). They become the script's own file name, "author" and "build"."""
    d = open(path, "rb").read()
    if d[:4] != bytes.fromhex("fa57c0de"):
        sys.exit(f"{path}: not a Skyrim .pex")
    pos = 16
    for _ in range(3):
        (k,) = struct.unpack(">H", d[pos:pos + 2])
        pos += 2 + k
    name = os.path.basename(path)[:-4].encode() + b".psc"
    head = b"".join(struct.pack(">H", len(x)) + x for x in (name, b"author", b"build"))
    open(path, "wb").write(d[:16] + head + d[pos:])


def main():
    a = argparse.ArgumentParser()
    for k in ("stage", "hall", "hall2", "src", "fomod", "label", "version", "out"):
        a.add_argument("--" + k, required=True)
    for k in ("deployed", "deployed2"):                    # (optional: a test install's folder to compare with, byte for byte)
        a.add_argument("--" + k)
    a = a.parse_args()
    core_dir = os.path.join(a.stage, "00 Core")
    HALLS = [("01 Guild Hall", a.hall, a.deployed, "Riverwood"), ("02 Guild Hall Solitude", a.hall2, a.deployed2, "Solitude")]

    # 1. the halls
    core = files(core_dir)
    if not core:
        sys.exit("REFUSED - the core staged nothing")
    halls = {}
    for top, src, _, site in HALLS:
        skipped = 0
        for rel, p in files(src).items():
            if BUILD_ONLY.search(rel):
                skipped += 1
                continue
            dst = os.path.join(a.stage, top, rel)
            os.makedirs(os.path.dirname(dst), exist_ok=True)
            shutil.copy2(p, dst)
        halls[top] = files(os.path.join(a.stage, top))
        if not halls[top]:
            sys.exit(f"REFUSED - the {site} hall staged nothing")
        print(f"staged: the {site} hall {len(halls[top])} files ({skipped} build-only files left out)")
    print(f"staged: core {len(core)} files")

    # 2. against what was tested: the core with each hall, against that site's deployed folder
    bad = []
    for top, _, deployed, site in HALLS:
        hall = halls[top]
        shared = sorted(set(k.lower() for k in core) & set(k.lower() for k in hall))
        bad += [f"in both the core and the {site} hall: {k}" for k in shared]
        if not deployed: continue                          # (a release built fresh from its commit: nothing deployed to compare with)
        dep = {k: p for k, p in files(deployed).items() if k != "meta.ini" and not k.lower().startswith("docs/")}
        pkg_ = {**core, **hall}
        dl, pl = {k.lower(): k for k in dep}, {k.lower(): k for k in pkg_}
        bad += [f"{site}: deployed, not in the package (left by an earlier build?): {dl[k]}" for k in sorted(set(dl) - set(pl))]
        bad += [f"{site}: in the package, not deployed: {pl[k]}" for k in sorted(set(pl) - set(dl))]
        differ = [pl[k] for k in sorted(set(pl) & set(dl)) if digest(pkg_[pl[k]]) != digest(dep[dl[k]])]
        bad += [f"{site}: differs from the deployed file: {k}" for k in differ]
    pkg = {**core, **{f"{top}/{k}": p for top, h in halls.items() for k, p in h.items()}}
    if bad:
        report = os.path.join(a.stage, "mismatch.txt")
        open(report, "w", encoding="utf-8").write("\n".join(bad) + "\n")
        print(f"REFUSED - the package would not be what is deployed in {a.deployed} / {a.deployed2} ({len(bad)}; all in {report}):", *bad[:40], sep="\n  ")
        if len(bad) > 40:
            print(f"  ... and {len(bad) - 40} more")
        sys.exit(1)
    print(f"matches the deployed folders: the core with each hall, {len(pkg)} files, byte for byte" if a.deployed else
          f"the core and each hall share no file: {len(pkg)} files (built from the commit, compared with no deployed folder)")

    # 3. privacy
    pex = [p for k, p in pkg.items() if k.lower().endswith(".pex")]
    for p in pex:
        scrub_pex(p)
    words = [w.strip() for w in os.environ.get("PRIVATE_WORDS", "").split(",") if w.strip()]
    if not words:
        sys.exit("REFUSED - PRIVATE_WORDS is not set in local.env: the private-word search cannot run")
    # a drive path needs a folder and a name after it (X:\folder\...): the shorter X:\abc turns up by chance in meshes' vertex data
    leak = re.compile(rb"\b[A-Za-z]:[/\\][A-Za-z0-9_ .()-]{2,}[/\\][ -~]{2,}|/c/Users|FUS v5|Librum|"
                      + b"|".join(rb"\b" + re.escape(w.encode()) + rb"\b" for w in words), re.I)
    hits, scanned = [], 0
    for k, p in sorted(pkg.items()):
        if k.lower().endswith(NOT_SCANNED):
            continue
        scanned += 1
        m = leak.search(open(p, "rb").read())
        if m:
            hits.append(f"{k} (at byte {m.start()})")
    if hits:
        print(f"REFUSED - {len(hits)} file(s) name this machine or a private word:", *hits[:40], sep="\n  ")
        sys.exit(1)
    print(f"privacy: {len(pex)} compiled scripts given neutral headers; {scanned} files searched, nothing private")

    # 4. docs, the installer, the archive
    docs = os.path.join(a.stage, "docs")
    os.makedirs(docs, exist_ok=True)
    for src, name in DOCS:
        shutil.copy2(os.path.join(a.src, src), os.path.join(docs, name))
    fom = os.path.join(a.stage, "fomod")
    os.makedirs(fom, exist_ok=True)
    for f in ("info.xml", "ModuleConfig.xml"):
        t = open(os.path.join(a.fomod, f), encoding="utf-8").read()
        t = t.replace("@VERSION@", a.label).replace("@MACHINE_VERSION@", a.version)
        open(os.path.join(fom, f), "w", encoding="utf-8", newline="\r\n").write(t)
    if os.path.isdir(os.path.join(a.fomod, "images")):     # (the installer's preview images, one per choice: ModuleConfig.xml names them)
        shutil.copytree(os.path.join(a.fomod, "images"), os.path.join(fom, "images"), dirs_exist_ok=True)
    n = 0
    tmp = a.out + ".part"
    with zipfile.ZipFile(tmp, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as z:
        for top in ("fomod", "00 Core", "01 Guild Hall", "02 Guild Hall Solitude", "docs"):
            for k, p in sorted(files(os.path.join(a.stage, top)).items()):
                z.write(p, f"{top}/{k}")
                n += 1
    os.replace(tmp, a.out)
    print(f"{a.out}: {n} files, {os.path.getsize(a.out) / 1e6:.1f} MB")


if __name__ == "__main__":
    main()
