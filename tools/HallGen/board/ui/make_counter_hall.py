"""The hall counter's Quests tab, as a patch on AG's counter.html (config/PrismaUI/views/AdventurersGuild): writes
ui/counter_hall.html, the counter with the patch applied, for the mockup renders. Once it is approved, the same
patch goes into counter.html itself (shared with the 1.6 line).

What the patch does:
- data.hall (the clerks at the Guild Hall): Missives and Bounties list every hold's postings, a hold button opens a grid
  of the holds over the list (one tap to any), and each row names its hold.
- Every counter, the inns' too: a filter row under the sections, the rank filter (only ranks posted there) and the sort
  (highest or lowest rank first); the rows go to the counter's tight height (as the Party tab's) so five still fit.
    python make_counter_hall.py [counter.html] [out.html]"""
import os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
AG = os.path.normpath(os.path.join(HERE, "..", "..", "..", ".."))
SRC = sys.argv[1] if len(sys.argv) > 1 else os.path.join(AG, "config", "PrismaUI", "views", "AdventurersGuild", "counter.html")
OUT = sys.argv[2] if len(sys.argv) > 2 else os.path.join(HERE, "counter_hall.html")
s = open(SRC, encoding="utf-8", newline="").read()   # line endings as they are (the repository keeps LF)

def rep(old, new, count=1):
    global s
    n = s.count(old)
    if n != count: sys.exit(f"patch: expected {count} of {old[:70]!r}, found {n}")
    s = s.replace(old, new)

# ---- CSS: the filter row and the hold grid
rep("  .notebox { display: flex; gap: 24px; height: 470px; }",
    """  /* the filter row under a list's sections: the hold (the hall), the ranks posted there, the sort */
  .qfilter { display: flex; align-items: center; gap: 10px; height: 52px; margin-bottom: 8px; }
  .qfilter .qsec button.r { padding: 0; width: 52px; font-variant: normal; font-size: 21px; }
  .qfilter .qhold { min-width: 0; max-width: 300px; overflow: hidden; text-overflow: ellipsis; }
  .qfilter .qhold .v { color: var(--bronze); }
  /* the hall's hold picker: every hold at once, over the list, one tap to any */
  .qfilter .qhold.open { border-color: var(--bronze); color: #fff6df; background: linear-gradient(#4d4436, #2c2823); }
  /* the hold picker: a panel hanging from the Hold button (its caret points at it), every hold at once, one tap to any */
  .holdpop { position: relative; border: 1px solid var(--bronze); background: rgba(20, 17, 14, 0.97); padding: 12px 16px 16px;
             box-shadow: 0 10px 24px rgba(0, 0, 0, 0.8); }
  .holdpop::before { content: ""; position: absolute; top: -9px; left: 60px; width: 16px; height: 16px; transform: rotate(45deg);
                     background: rgba(20, 17, 14, 0.97); border-left: 1px solid var(--bronze); border-top: 1px solid var(--bronze); }
  .holdpop .h { font-size: 16px; color: var(--muted); font-style: italic; margin-bottom: 10px; }
  .holdgrid { display: grid; grid-template-columns: repeat(4, 1fr); gap: 12px; }
  .holdgrid .btn { height: 62px; font-size: 21px; display: flex; align-items: center; justify-content: space-between; padding: 0 20px; }
  .holdgrid .btn .n { font-size: 17px; color: var(--muted); font-variant: normal; letter-spacing: 0; }
  .holdgrid .btn.on { border-color: var(--bronze); color: #fff6df; background: linear-gradient(#4d4436, #2c2823); }
  .holdgrid .btn.none { color: var(--dim); }
  .notebox { display: flex; gap: 24px; height: 470px; }""")

# ---- state
rep('let tab = "card", section = null, qsec = null, note = null, isec = "dungeon";',
    'let tab = "card", section = null, qsec = null, note = null, isec = "dungeon";\n'
    'let qhold = "@all", qrank = "", qsort = "high", holdPick = false;   /* the Quests lists\' filters (the hold: the hall only) */')

# ---- helpers, before renderQuests
rep("function renderQuests() {", r'''/* A list's filters. The hall lists every hold: a hold button opens the grid of holds. Every counter: the ranks posted in
   what is listed (all at or below the player's: the rank gate keeps the rest off) and the sort, a Jarl's bounty first. */
const RANKS = "EDCBAS";
function holdName(k) { const h = (data.holds || []).find((x) => x.key === k); return h ? h.name : t("$AG_UI_AllSkyrim", "All Skyrim"); }
function qfiltered(list, byHold) {
  let out = byHold && qhold !== "@all" ? list.filter((x) => x.hold === qhold) : list;
  const have = RANKS.split("").filter((r) => out.some((x) => x.tier === r));
  if (qrank && !have.includes(qrank)) qrank = "";
  out = out.filter((x) => !qrank || x.tier === qrank);
  const rk = (x) => RANKS.indexOf(x.tier || "E");
  return { list: out.slice().sort((a, b) => qsort === "high" ? rk(b) - rk(a) : rk(a) - rk(b)), have };
}
function qfilterRow(have, byHold) {
  return `<div class="qfilter">` +
    (byHold ? `<button class="btn qhold ${holdPick ? "open" : ""}" data-qpick="1">${esc(t("$AG_UI_HoldPick", "Hold:"))} <span class="v">${esc(holdName(qhold))}</span> ${holdPick ? "&#x25B4;" : "&#x25BE;"}</button>` : "") +
    `<div class="qsec"><button data-qrank="" class="${qrank ? "" : "on"}">${esc(t("$AG_UI_AllRanks", "All ranks"))}</button>` +
    have.map((r) => `<button class="r ${qrank === r ? "on" : ""}" data-qrank="${r}">${r}</button>`).join("") + `</div>` +
    `<div class="qsec"><button data-qsort="1">${esc(qsort === "high" ? t("$AG_UI_SortHigh", "Highest rank first") : t("$AG_UI_SortLow", "Lowest rank first"))}</button></div></div>`;
}
function holdGrid(list) {
  const n = (k) => k === "@all" ? list.length : list.filter((x) => x.hold === k).length;
  const all = [{ key: "@all", name: t("$AG_UI_AllSkyrim", "All Skyrim") }, ...(data.holds || [])];
  return `<div class="holdpop"><div class="h">${esc(t("$AG_UI_ChooseHold", "Choose a hold to see only its postings."))}</div><div class="holdgrid">${all.map((h) => `<button class="btn ${h.key === qhold ? "on" : ""} ${n(h.key) ? "" : "none"}" data-qhold="${esc(h.key)}"><span>${esc(h.name)}</span><span class="n">${n(h.key)}</span></button>`).join("")}</div></div>`;
}

function renderQuests() {''')

# ---- the hall's bounties: every hold's, as rows (an inn keeps its one bounty and its lines)
rep("  if (isBounties) {",
    r'''  if (isBounties && data.hall) {
    const all = (data.bounties || []).filter((x) => x.state === "offer");
    const { list, have } = qfiltered(all, true);
    const top = `<div class="bar-top">${tabs}<span class="sum caps"><b>${list.length}</b> ${esc(t("$AG_UI_Posted", "posted"))}</span></div>${qfilterRow(have, true)}`;
    if (holdPick) return top + holdGrid(all);
    if (!list.length) return top + `<div class="empty">${esc(t("$AG_UI_HallBountyEmpty", "No Jarl has a bounty posted for {0} right now.", holdName(qhold)))}</div>`;
    const { items, pages } = paged("bounties", list, ROWS);
    return top + items.map((x) => `<div class="row tight"><span class="tier">${esc(x.tier)}</span><div class="body"><div class="title">${esc(x.title)}</div>
        <div class="detail">${esc(t("$AG_UI_HallBountyDetail", "Jarl's Bounty · Rank {0} · {1}", x.tier, x.holdName))}</div></div>
        <button class="btn" data-note="${esc(x.id)}">${esc(t("$AG_UI_Details", "Details"))}</button><button class="btn" data-action="accept:${esc(x.id)}">${esc(t("$AG_UI_Take", "Take"))}</button></div>`).join("") +
      pager("bounties", pages);
  }
  if (isBounties) {''')

# the bounties' reader at the hall: the bounty read is one of the hall's list
rep("    const n = note, still = isBounties ? !!(offered && bounty.id === n.id) : (isNotices ? notices : posts).some((x) => x.id === n.id);",
    "    const n = note, still = isBounties ? (data.hall ? (data.bounties || []).some((x) => x.id === n.id && x.state === \"offer\") : !!(offered && bounty.id === n.id))\n"
    "      : (isNotices ? notices : posts).some((x) => x.id === n.id);")

# the reader at the hall names the posting's own town (a missive) or hold (a bounty), not a branch
rep("""    const meta = isBounties ? t("$AG_UI_BountyMeta", "Jarl's Bounty · Rank {0} · posted for {1}", n.tier || "?", where)""",
    """    const hp = data.hall ? [...posts, ...(data.bounties || [])].find((x) => x.id === n.id) : null;
    const meta = isBounties ? t("$AG_UI_BountyMeta", "Jarl's Bounty · Rank {0} · posted for {1}", n.tier || "?", hp ? hp.holdName : where)""")
rep("""      : t("$AG_UI_NoteMeta", "Guild Missive · Rank {0} · {1} board", n.tier || "?", where) + (n.tag ? ` · [${n.tag}]` : "");""",
    """      : t("$AG_UI_NoteMeta", "Guild Missive · Rank {0} · {1} board", n.tier || "?", hp ? hp.city : where) + (n.tag ? ` · [${n.tag}]` : "");""")

# ---- Missives: the hall names it plain "Missives"; both get the filter row and tight rows
rep('${tabBtn("board", t("$AG_UI_LocalMissives", "Local Missives"), posts.length)}',
    '${tabBtn("board", data.hall ? t("$AG_UI_Missives", "Missives") : t("$AG_UI_LocalMissives", "Local Missives"), posts.length)}')
rep('${tabBtn("bounties", t("$AG_UI_Bounties", "Bounties"), offered ? 1 : 0)}',
    '${tabBtn("bounties", t("$AG_UI_Bounties", "Bounties"), data.hall ? (data.bounties || []).filter((x) => x.state === "offer").length : offered ? 1 : 0)}')
rep('''    const { items, pages } = paged("board", posts, ROWS);
    return `<div class="bar-top">${tabs}<span class="sum caps"><b>${posts.length}</b> ${esc(t("$AG_UI_Posted", "posted"))}</span></div>` +
      items.map((x) => `<div class="row"><span class="tier">${esc(x.tier)}</span><div class="body"><div class="title">${esc(x.title)}${x.tag ? ` <span class="srctag">[${esc(x.tag)}]</span>` : ""}</div>
        <div class="detail">${esc(t("$AG_UI_PostDetail", "Guild Missive · Rank {0} · posted on the {1} board", x.tier, where))}</div></div>''',
    '''    const { list, have } = qfiltered(posts, !!data.hall);
    const { items, pages } = paged("board", list, ROWS);
    const top = `<div class="bar-top">${tabs}<span class="sum caps"><b>${list.length}</b> ${esc(t("$AG_UI_Posted", "posted"))}</span></div>${qfilterRow(have, !!data.hall)}`;
    if (data.hall && holdPick) return top + holdGrid(posts);
    return top +
      (list.length ? "" : `<div class="empty">${esc(t("$AG_UI_HallBoardEmpty", "Nothing is posted in {0} for your rank right now.", holdName(qhold)))}</div>`) +
      items.map((x) => `<div class="row tight"><span class="tier">${esc(x.tier)}</span><div class="body"><div class="title">${esc(x.title)}${x.tag ? ` <span class="srctag">[${esc(x.tag)}]</span>` : ""}</div>
        <div class="detail">${esc(data.hall ? t("$AG_UI_HallPostDetail", "Guild Missive · Rank {0} · {1} · posted on the {2} board", x.tier, x.holdName, x.city)
                                           : t("$AG_UI_PostDetail", "Guild Missive · Rank {0} · posted on the {1} board", x.tier, where))}</div></div>''')
# the board's refresh hint is one town's: at the hall it would name no town
rep("    const bs = data.boardStatus || null;", "    const bs = data.hall ? null : data.boardStatus || null;")

# ---- Notices: rank filter and sort too (one province-wide board: no hold)
rep('''    const { items, pages } = paged("notices", notices, ROWS);
    return `<div class="bar-top">${tabs}<span class="sum caps"><b>${notices.length}</b> ${esc(t("$AG_UI_Posted", "posted"))}</span></div>` +
      items.map((x) => `<div class="row"><span class="tier">''',
    '''    const { list, have } = qfiltered(notices, false);
    const { items, pages } = paged("notices", list, ROWS);
    return `<div class="bar-top">${tabs}<span class="sum caps"><b>${list.length}</b> ${esc(t("$AG_UI_Posted", "posted"))}</span></div>${qfilterRow(have, false)}` +
      items.map((x) => `<div class="row tight"><span class="tier">''')

# ---- the hall's subtitle
rep('''    : (data.branch ? t("$AG_UI_Branch", "Skyrim Region · {0} Branch", data.branch) : t("$AG_UI_Region", "Skyrim Region"));''',
    '''    : data.hall ? t("$AG_UI_HallBranch", "Skyrim Region · The Guild Hall")
    : (data.branch ? t("$AG_UI_Branch", "Skyrim Region · {0} Branch", data.branch) : t("$AG_UI_Region", "Skyrim Region"));''')

# ---- clicks: the filters (a new filter goes back to the list's first page)
rep('  if (b.dataset.qsec) { qsec = b.dataset.qsec; note = null; render(); return; }',
    '''  if (b.dataset.qsec) { qsec = b.dataset.qsec; note = null; holdPick = false; qrank = ""; render(); return; }
  const firstPage = () => { page.board = page.notices = page.bounties = 0; };
  if (b.dataset.qpick) { holdPick = !holdPick; render(); return; }
  if (b.dataset.qhold) { qhold = b.dataset.qhold; holdPick = false; firstPage(); render(); return; }
  if (b.dataset.qrank !== undefined) { qrank = b.dataset.qrank; firstPage(); render(); return; }
  if (b.dataset.qsort) { qsort = qsort === "high" ? "low" : "high"; firstPage(); render(); return; }''')
rep("const page = { quests: 0, board: 0, notices: 0,", "const page = { quests: 0, board: 0, notices: 0, bounties: 0,")
# focus keys for the controller (keyOf): the new buttons are found again after a render
rep('(d.qsec && "qsec:" + d.qsec) ||',
    '(d.qsec && "qsec:" + d.qsec) || (d.qhold && "qhold:" + d.qhold) || (d.qrank !== undefined && "qrank:" + d.qrank) || (d.qsort && "qsort") || (d.qpick && "qpick") ||')

open(OUT, "w", encoding="utf-8", newline="").write(s)
print("->", OUT)
