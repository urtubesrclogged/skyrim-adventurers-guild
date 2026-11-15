"""A gate's log, kept and reused only when nothing it reads has changed (the build was very slow, and the gates
were half of it, every one run again whatever changed). gates_all.sh runs each gate through it. By content, never by date, as
mesh_cache.py: the key covers the command line, every file it names (its bytes), every folder it names (each file's path and bytes),
and all of the gates' own code (every .py and .json here, and gates_all.sh), so a change to any helper re-runs them all. A log that
shows the gate fell over (a traceback, an error) is never kept, so the next build runs it again.
    python gate_cache.py prepare <fingerprints.json> <cache dir> <folder> ...   the named folders' prints, once per run (they are big)
    python gate_cache.py key <fingerprints.json> <command and arguments ...>     prints the key
    python gate_cache.py put <log> <cache file>                                   keeps the log, unless the gate fell over"""
import hashlib, json, os, re, shutil, sys

HERE = os.path.dirname(os.path.abspath(__file__))


def norm(p): return os.path.normcase(os.path.abspath(p))


def file_hash(p):
    h = hashlib.blake2b(digest_size=16)
    with open(p, "rb") as f:
        while (b := f.read(1 << 20)): h.update(b)
    return h.hexdigest()


def folder_fp(d, stats=None):
    """by content: each file's path and its bytes' hash (the build rewrites files with the same bytes and a new time, which a print by
    time took for a change every build); stats, {path: [size, mtime, hash]}, spares re-hashing a file whose size and time are unchanged"""
    h = hashlib.blake2b(digest_size=16)
    for root, dirs, files in os.walk(d):
        dirs[:] = sorted(x for x in dirs if x != "gates")          # (an export's own gates/ folder: the logs being written now)
        for f in sorted(files):
            p = os.path.join(root, f); s = os.stat(p); k = norm(p)
            c = stats.get(k) if stats is not None else None
            if not c or c[0] != s.st_size or c[1] != s.st_mtime: c = [s.st_size, s.st_mtime, file_hash(p)]
            if stats is not None: stats[k] = c
            h.update(f"{os.path.relpath(p, d)}|{c[2]}".encode() + b"\n")
    return h.hexdigest()


def code_fp():
    h = hashlib.blake2b(digest_size=16)
    files = sorted(f for f in os.listdir(HERE) if f.endswith((".py", ".json"))) + [os.path.join("..", "gates_all.sh")]
    for f in files:
        p = os.path.join(HERE, f)
        if os.path.isfile(p): h.update(f.encode()); h.update(open(p, "rb").read())
    return h.hexdigest()


def main():
    mode = sys.argv[1]
    if mode == "prepare":
        sp = os.path.join(sys.argv[3], "stats.json"); os.makedirs(sys.argv[3], exist_ok=True)
        stats = json.load(open(sp)) if os.path.exists(sp) else {}
        out = {norm(d): folder_fp(d, stats) for d in sys.argv[4:] if os.path.isdir(d)}
        json.dump(stats, open(sp + ".tmp", "w")); os.replace(sp + ".tmp", sp)
        json.dump(out, open(sys.argv[2], "w")); return
    if mode == "fp":   # fp <cache dir> <folder>: one folder's print by content (build_hall.sh: the meshes' textures)
        sp = os.path.join(sys.argv[2], "stats.json"); os.makedirs(sys.argv[2], exist_ok=True)
        stats = json.load(open(sp)) if os.path.exists(sp) else {}
        print(folder_fp(sys.argv[3], stats)); json.dump(stats, open(sp + ".tmp", "w")); os.replace(sp + ".tmp", sp); return
    if mode == "put":
        log, dst = sys.argv[2], sys.argv[3]
        text = open(log, encoding="utf-8", errors="replace").read()
        if re.search(r"^Traceback|Error: |Error.*No such file|MemoryError", text, re.M): return
        os.makedirs(os.path.dirname(dst), exist_ok=True); shutil.copyfile(log, dst + ".tmp"); os.replace(dst + ".tmp", dst); return
    if mode == "key":
        fps = json.load(open(sys.argv[2])) if os.path.exists(sys.argv[2]) else {}
        h = hashlib.blake2b(digest_size=20); h.update(code_fp().encode())
        ex_ = norm(os.environ["GATE_EXPORT"]) if os.environ.get("GATE_EXPORT") else None
        for a in sys.argv[3:]:
            # (2026-11-05) a path in the export named from the export, so a gate run on another folder's identical export (place_check.sh's)
            # has the build's key and the build reuses its log
            na_ = norm(a)
            h.update(b"\0" + (("<export>" + na_[len(ex_):].replace("\\", "/")) if ex_ and na_.startswith(ex_) else a).encode())
            if a.lower().endswith(".exe"): continue                 # (a program: its name is enough)
            if os.path.isfile(a):
                h.update(file_hash(a).encode())
            elif os.path.isdir(a):
                h.update((fps.get(norm(a)) or folder_fp(a)).encode())
        print(h.hexdigest())


if __name__ == "__main__":
    main()
