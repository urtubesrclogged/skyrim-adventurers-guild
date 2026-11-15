"""The hall's package laid over each install's folder (the deploy was too slow: 155 seconds to copy one file: the package built in a temp folder, then one
process per file per install to compare it). The same confidence, one pass: each source file hashed once, each installed file hashed against it, byte for byte, only a file that differs backed up,
copied and hashed again. Later layers win; names compare without case, as Windows does.
(2026-11-14, package.sh's check: 46 files no build makes any more sat in FUS's folder, the hall's old meshes, voices and AGHall2.pex) --manifest <dir>
keeps <dir>/<target name>.tsv, every file this deploy put in that install and its hash; the next deploy removes (after a backup) each listed file the
package no longer has, if it is still the file it put there (one another deploy has replaced since stays).
    python deploy_sync.py <backup root> <stamp> --layer <dir> [--layer <dir> ...] --file <source> <published path> [...] --drop <published path> [...] [--manifest <dir>] --target <name> <dir> [...]
Exit 1 if a file differs after its copy. The refusal to touch a running game stays in deploy_hall.sh."""
import concurrent.futures as cf, hashlib, os, shutil, sys, time
a = sys.argv[1:]; backups, stamp = a[0], a[1]; a = a[2:]; layers, files, drops, targets, manifests = [], [], set(), [], None
while a:
    k = a.pop(0)
    if k == "--layer": layers.append(a.pop(0))
    elif k == "--file": files.append((a.pop(0), a.pop(0)))
    elif k == "--drop": drops.add(a.pop(0).replace("\\", "/").lower())
    elif k == "--target": targets.append((a.pop(0), a.pop(0)))
    elif k == "--manifest": manifests = a.pop(0)
    else: sys.exit(f"unknown argument {k}")
def digest(p):
    h = hashlib.blake2b(digest_size=20)
    with open(p, "rb", buffering=0) as f:
        b = bytearray(1 << 20); v = memoryview(b)
        while (n := f.readinto(b)): h.update(v[:n])
    return h.digest()
pkg = {}                                       # lower-case path -> (published spelling, source)
for root in layers:
    for d, _, fs in os.walk(root):
        for f in fs:
            s = os.path.join(d, f); r = os.path.relpath(s, root).replace("\\", "/")
            pkg[r.lower()] = (pkg.get(r.lower(), (r,))[0], s)
for s, r in files: pkg[r.lower()] = (pkg.get(r.lower(), (r,))[0], s)
for k in list(pkg):
    if k in drops or k.endswith(".unmerged"): del pkg[k]
if not pkg: sys.exit("the package is empty")
t0 = time.time()
with cf.ThreadPoolExecutor(8) as ex: want = dict(zip(pkg, ex.map(lambda k: digest(pkg[k][1]), pkg)))
print(f"package: {len(pkg)} files, {sum(os.path.getsize(v[1]) for v in pkg.values()) >> 20} MB, hashed in {time.time() - t0:.1f}s", flush=True)
def one(t):
    name, dest = t; t0 = time.time(); copied = bad = 0
    def same(k):
        p = os.path.join(dest, pkg[k][0])
        try: return k, os.path.getsize(p) == os.path.getsize(pkg[k][1]) and digest(p) == want[k]
        except OSError: return k, False
    with cf.ThreadPoolExecutor(6) as ex: res = list(ex.map(same, pkg))
    for k, ok in res:
        if ok: continue
        r, src = pkg[k]; p = os.path.join(dest, r)
        if os.path.exists(p):
            b = os.path.join(backups, f"{name}-{stamp}", r); os.makedirs(os.path.dirname(b), exist_ok=True); shutil.copy2(p, b)
        os.makedirs(os.path.dirname(p), exist_ok=True); shutil.copyfile(src, p); copied += 1
        if digest(p) != want[k]: print(f"  {name}: {r} differs after copy", flush=True); bad += 1
    removed = 0
    if manifests:
        mf = os.path.join(manifests, f"{name}.tsv")
        old = dict(l.rstrip("\n").split("\t") for l in open(mf, encoding="utf-8")) if os.path.exists(mf) else {}
        for r, h in old.items():
            p = os.path.join(dest, r)
            if r.lower() in pkg or not os.path.isfile(p) or digest(p).hex() != h: continue
            b = os.path.join(backups, f"{name}-{stamp}", r); os.makedirs(os.path.dirname(b), exist_ok=True); shutil.copy2(p, b)
            os.remove(p); removed += 1
            d = os.path.dirname(p)
            while os.path.normcase(d) != os.path.normcase(dest) and not os.listdir(d): os.rmdir(d); d = os.path.dirname(d)
        if not bad:
            os.makedirs(manifests, exist_ok=True)
            with open(mf + ".part", "w", encoding="utf-8") as f: f.writelines(f"{pkg[k][0]}\t{want[k].hex()}\n" for k in sorted(pkg))
            os.replace(mf + ".part", mf)
    print(f"{name}: {len(pkg)} files compared, {copied} copied, {removed} no longer built removed{'' if bad else ', every file checked'}, {time.time() - t0:.1f}s", flush=True)
    return bad
with cf.ThreadPoolExecutor(len(targets) or 1) as ex: bad = sum(ex.map(one, targets))
sys.exit(1 if bad else 0)
