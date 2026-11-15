"""The build and deploy status page: updated by the build and deploy scripts themselves, so the status across sessions
shows without having to ask.

Every shared build and deploy script records what it does here, and the page is drawn again each time:
    python tools/HallGen/status/status.py event <what> start|ok|fail [detail]   a step began, passed or failed (who: $AG_SESSION)
    python tools/HallGen/status/status.py deployed <install> <commit> <ag|hall|ag+hall>   build.sh's stamp after a checked deploy
    python tools/HallGen/status/status.py ask <question>                       a decision a session needs answered
    python tools/HallGen/status/status.py resolve <id>                         ... answered
    python tools/HallGen/status/status.py render                               draw the page again
The log, the state (each install's stamps, the questions) and the page live in build/status of the working checkout (HALL_STATUS_DIR
overrides it: build.sh builds in a snapshot of the commit and points it back here). The page reloads itself every 20 seconds."""
import datetime, hashlib, html, json, os, re, subprocess, sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, ".."))
from hallenv import AG_ROOT as AG, HALL_BUILD, installs, cfg
OUT = os.environ.get("HALL_STATUS_DIR") or os.path.join(AG, "build", "status")
LIVE = os.path.normpath(os.path.join(OUT, "..", ".."))           # the working checkout the page belongs to
LOG = os.path.join(OUT, "events.jsonl"); STATE = os.path.join(OUT, "state.json"); LOCK = os.path.join(LIVE, "build", "build.lock")
INSTALLS = [(n, f"{n} ({'VR' if 'vr' in x.lower() else 'SE'})", d, x) for n, d, x in installs()]   # (HALL_INSTALLS in local.env)


def load_state():
    try: return json.load(open(STATE, encoding="utf-8"))
    except Exception: return {"installs": {}, "asks": [], "built": {}}


def save_state(s):
    os.makedirs(OUT, exist_ok=True); tmp = STATE + ".tmp"
    json.dump(s, open(tmp, "w", encoding="utf-8"), indent=1); os.replace(tmp, STATE)


def files(state):
    """what each install is compared on: the deployed file against the one a deploy would copy (AG's from the snapshot build.sh built)"""
    src = state.get("built", {}).get("root") or LIVE
    hb = os.path.join(LIVE, "build", "hall") if os.path.isdir(os.path.join(LIVE, "build", "hall")) else HALL_BUILD
    return [("Guild Hall plugin", "AdventurersGuild - Guild Hall.esp", os.path.join(hb, "AdventurersGuild - Guild Hall.esp")),
            ("Hall site mesh", "meshes/AdventurersGuild/Hall2/AGHall2Site1.nif", os.path.join(hb, "meshes/AdventurersGuild/Hall2/AGHall2Site1.nif")),
            ("AG plugin", "AdventurersGuild.esp", os.path.join(src, "build", "esp", "AdventurersGuild.esp")),
            ("AG DLL", "SKSE/Plugins/AdventurersGuild.dll", os.path.join(src, "src", "plugin", "build", "AdventurersGuild.dll")),
            ("AG_Native.pex", "Scripts/AG_Native.pex", os.path.join(src, "build", "papyrus", "AG_Native.pex"))]


def who():
    s = os.environ.get("AG_SESSION")
    if s: return s
    cwd = os.getcwd().replace("\\", "/")
    for part in reversed(cwd.split("/")):          # a session's scratchpad: .../<session id>/scratchpad/...
        if len(part) == 36 and part.count("-") == 4: return "session " + part[:8]
    return os.path.basename(cwd) or cwd


def now(): return datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def md5(p):
    m = hashlib.md5()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""): m.update(b)
    return m.hexdigest()


def mtime(p): return datetime.datetime.fromtimestamp(os.path.getmtime(p)).strftime("%m-%d %H:%M")


def running():
    try: out = subprocess.run(["tasklist"], capture_output=True, text=True, timeout=20).stdout.lower()
    except Exception: return set()
    return {e for e in ("skyrimse.exe", "skyrimvr.exe") if e in out}


def git(*a):
    try: return subprocess.run(["git", "-C", LIVE] + list(a), capture_output=True, text=True, timeout=20).stdout.strip()
    except Exception: return ""


def events():
    if not os.path.exists(LOG): return []
    ev = []
    for l in open(LOG, encoding="utf-8"):
        try: ev.append(json.loads(l))
        except Exception: pass
    return ev


def to_test(prev, cur):
    """the commits an install got since its last deploy, each with its 'Test:' lines (what to check in game) when it has them"""
    if not cur: return []
    rng = f"{prev}..{cur}" if prev else f"{cur}~1..{cur}"
    out = []
    for block in git("log", "--format=%h%x1f%s%x1f%b%x1e", rng).split("\x1e"):
        if not block.strip(): continue
        h, s, b = (block.strip("\n").split("\x1f") + ["", ""])[:3]
        tests = [l.split(":", 1)[1].strip() for l in b.splitlines() if l.lower().startswith("test:")]
        out.append((h, s, tests))
    return out


def render():
    os.makedirs(OUT, exist_ok=True)
    st = load_state(); ev = events(); E = html.escape; FILES = files(st)
    last = {}
    for e in ev: last[(e["who"], e["what"])] = e
    flight = sorted((e for e in last.values() if e["state"] == "start"), key=lambda e: e["t"], reverse=True)
    lock = ""
    try:
        o = json.load(open(os.path.join(LOCK, "owner.json"), encoding="utf-8"))
        q = [json.loads(l) for l in open(os.path.join(LIVE, "build", "build.queue"), encoding="utf-8") if l.strip()] if os.path.exists(os.path.join(LIVE, "build", "build.queue")) else []
        lock = f'<p><b>build.sh is held by {E(o.get("who", "?"))}</b> since {E(o.get("t", "?"))} ({E(o.get("what", ""))})' + \
               (f'; waiting: {E(", ".join(x.get("who", "?") for x in q))}' if q else "") + "</p>"
    except Exception: pass
    games = running(); cache = {}
    def h(p):
        if p not in cache: cache[p] = md5(p) if os.path.exists(p) else None
        return cache[p]
    rows = []
    for key, name, d, exe in INSTALLS:
        cells = []
        for label, rel, src in FILES:
            p = os.path.join(d, rel)
            if not os.path.exists(p): cells.append('<td class="miss">missing</td>'); continue
            if not os.path.exists(src): cells.append(f'<td>{mtime(p)}</td>'); continue
            same = h(p) == h(src)
            cells.append(f'<td class="{"ok" if same else "old"}">{"matches the build" if same else "differs from the build"}<br><small>{mtime(p)}</small></td>')
        g = '<span class="run">game running</span>' if exe.lower() in games else "closed"
        s = st["installs"].get(key, {})
        stamp = f'<br><small>{E(s.get("commit", "")[:7])} ({E(s.get("parts", ""))}), {E(s.get("t", ""))}, {E(s.get("who", ""))}</small>' if s else ""
        rows.append(f"<tr><th>{E(name)}<br><small>{g}</small>{stamp}</th>{''.join(cells)}</tr>")
    builds = "".join(f'<td>{mtime(src) if os.path.exists(src) else "not built"}</td>' for _, _, src in FILES)
    head = git("log", "-1", "--format=%h %ad %s", "--date=format:%m-%d %H:%M")
    dirty = len([l for l in git("status", "--short", "--untracked-files=no").splitlines() if l.strip()])
    built = st.get("built", {})
    repos = (f"<tr><th>working checkout</th><td>{E(head[:120])}</td><td>{dirty} changed file{'s' if dirty != 1 else ''} not committed (build.sh builds commits only)</td></tr>"
             f"<tr><th>last good build</th><td>AG {E(built.get('ag', '-')[:7])}, hall {E(built.get('hall', '-')[:7])}</td><td>{E(built.get('t', ''))}</td></tr>")
    # ready to test: per install, what its last deploy brought
    rt = []
    for key, name, d, exe in INSTALLS:
        s = st["installs"].get(key)
        if not s: continue
        items = to_test(s.get("prev"), s.get("commit"))
        li = "".join(f'<li><code>{E(c)}</code> {E(sub)}' + ("<ul>" + "".join(f"<li>{E(t)}</li>" for t in tests) + "</ul>" if tests else "") + "</li>" for c, sub, tests in items) or "<li>nothing new</li>"
        rt.append(f"<tr><th>{E(name)}</th><td><ul>{li}</ul></td></tr>")
    asks = [a for a in st.get("asks", []) if a.get("open")]
    ask_rows = "".join(f'<tr><td>{a["id"]}</td><td>{E(a["t"])}</td><td>{E(a["who"])}</td><td>{E(a["text"])}</td></tr>' for a in asks) \
        or '<tr><td colspan="4">nothing waiting on you</td></tr>'
    fl = "".join(f'<tr><td>{E(e["t"])}</td><td>{E(e["who"])}</td><td>{E(e["what"])}</td><td>{E(e.get("detail", ""))}</td></tr>' for e in flight) \
        or '<tr><td colspan="4">nothing running</td></tr>'
    recent = "".join(f'<tr class="{E(e["state"])}"><td>{E(e["t"])}</td><td>{E(e["who"])}</td><td>{E(e["what"])}</td>'
                     f'<td>{E(e["state"])}</td><td>{E(e.get("detail", ""))}</td></tr>' for e in reversed(ev[-60:]))
    page = f"""<!doctype html><html><head><meta charset="utf-8"><meta http-equiv="refresh" content="20">
<title>AG build status</title><style>
body{{font:14px/1.45 system-ui,Segoe UI,sans-serif;margin:24px;background:#f6f4ef;color:#222}} h1{{font-size:20px;margin:0 0 4px}} h2{{font-size:16px;margin:24px 0 8px}}
table{{border-collapse:collapse;background:#fff;width:100%;max-width:1200px}} td,th{{border:1px solid #ddd;padding:6px 8px;text-align:left;vertical-align:top}}
th{{background:#efece4}} small{{color:#666}} .ok{{background:#e5f3e2}} .old{{background:#fbecd0}} .miss{{background:#f6d9d6}} .fail{{background:#f6d9d6}}
.start{{background:#e3ecf7}} .run{{color:#a33;font-weight:600}} .note{{color:#555;max-width:1200px}} ul{{margin:0;padding-left:18px}}
</style></head><body><h1>Adventurers Guild 2.0: build and deploy status</h1>
<div class="note">Drawn {E(now())} by the last build or deploy step; reloads every 20 s. Each install is read afresh whenever a step runs.</div>
{lock}
<h2>Waiting on you</h2><table><tr><th>#</th><th>since</th><th>who</th><th>question</th></tr>{ask_rows}</table>
<h2>Ready to test</h2><table>{''.join(rt) or '<tr><td>no deploys recorded yet</td></tr>'}</table>
<h2>Running now</h2><table><tr><th>since</th><th>who</th><th>step</th><th>detail</th></tr>{fl}</table>
<h2>The installs against the current build</h2><table><tr><th></th>{''.join(f'<th>{E(l)}</th>' for l, _, _ in FILES)}</tr>{''.join(rows)}
<tr><th>current build</th>{builds}</tr></table>
<h2>Repository</h2><table>{repos}</table>
<h2>Recent steps</h2><table><tr><th>time</th><th>who</th><th>step</th><th>result</th><th>detail</th></tr>{recent}</table></body></html>"""
    tmp = os.path.join(OUT, "index.html.tmp")
    with open(tmp, "w", encoding="utf-8") as f: f.write(page)
    os.replace(tmp, os.path.join(OUT, "index.html"))


def main():
    a = sys.argv[1:]
    os.makedirs(OUT, exist_ok=True)
    if a and a[0] == "event":
        if len(a) < 3 or a[2] not in ("start", "ok", "fail"): sys.exit("usage: status.py event <what> start|ok|fail [detail]")
        with open(LOG, "a", encoding="utf-8") as f:
            f.write(json.dumps({"t": now(), "who": who(), "what": a[1], "state": a[2], "detail": " ".join(a[3:])[:300]}) + "\n")
    elif a and a[0] == "deployed":
        if len(a) < 4: sys.exit("usage: status.py deployed <install> <commit> <parts>")
        st = load_state(); old = st["installs"].get(a[1], {})
        st["installs"][a[1]] = {"commit": a[2], "prev": old.get("commit") if old.get("commit") != a[2] else old.get("prev"), "parts": a[3], "t": now(), "who": who()}
        save_state(st)
    elif a and a[0] == "built":   # build.sh: the last good build, by part, and the snapshot it is in
        st = load_state(); st.setdefault("built", {}).update({k: v for k, v in (x.split("=", 1) for x in a[1:])}); st["built"]["t"] = now(); save_state(st)
    elif a and a[0] == "ask":
        st = load_state(); i = 1 + max([q["id"] for q in st.get("asks", [])] or [0])
        st.setdefault("asks", []).append({"id": i, "t": now(), "who": who(), "text": " ".join(a[1:])[:500], "open": True}); save_state(st); print(i)
    elif a and a[0] == "resolve":
        st = load_state()
        for q in st.get("asks", []):
            if str(q["id"]) in a[1:]: q["open"] = False
        save_state(st)
    try: render()
    except Exception as e: print("status page not drawn:", e, file=sys.stderr)   # (a status page never stops a build)


if __name__ == "__main__":
    main()
