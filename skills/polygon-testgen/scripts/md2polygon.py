#!/usr/bin/env python3
"""
把 statement.md 轉成 Polygon 題敘用的 LaTeX（Polygon 題敘只吃 LaTeX，不支援 Markdown）。

用法：
    python md2polygon.py pA            轉換並寫到 pA/.build/statement.tex（預覽用），印出警告
    python md2polygon.py pA --stdout   直接印出，不寫檔

upload_to_polygon.py 與 local_check.py 會 import 這支，三者要放在同一層。

statement.md 的章節（## 標題）對應 Polygon 題敘欄位：
    ## Legend          → legend        （也接受：題目敘述、題目描述、敘述）
    ## Input format    → input         （Input、輸入格式、輸入說明）
    ## Output format   → output        （Output、輸出格式、輸出說明）
    ## Interaction     → interaction   （互動、互動格式；只有互動題才會上傳）
    ## Scoring         → scoring       （配分、子題、子任務）
    ## Notes           → notes         （Note、附註、備註、說明）
    ## Tutorial        → tutorial      （題解）
`# 標題` 一行會被忽略，題名以 polygon.json 的 title 為準。範例不寫在題敘裡，
Polygon 會用勾選 use in statements 的測資自動排版。

支援的 Markdown 子集（其他語法會原樣當文字並發出警告）：
    段落、**粗體**、*斜體*、`行內程式碼`、$數學$、$$區塊數學$$、[連結](url)、
    - 無序清單、1. 有序清單（可巢狀）、表格、```程式碼區塊```、### 小標題、![圖](檔名)
只用標準函式庫。
"""
import argparse, json, re, sys
from pathlib import Path

SECTION_ALIASES = {
    "legend": ["legend", "statement", "description", "題目敘述", "題目描述", "敘述", "題目"],
    "input": ["input format", "input", "輸入格式", "輸入說明", "輸入"],
    "output": ["output format", "output", "輸出格式", "輸出說明", "輸出"],
    "interaction": ["interaction", "interaction protocol", "互動", "互動格式", "互動說明"],
    "scoring": ["scoring", "subtasks", "配分", "子題", "子題配分", "子任務", "評分"],
    "notes": ["notes", "note", "附註", "備註", "說明", "注意"],
    "tutorial": ["tutorial", "editorial", "題解"],
}
FIELDS = list(SECTION_ALIASES)
_ALIAS = {a: k for k, al in SECTION_ALIASES.items() for a in al}

CJK = r"\u2e80-\u9fff\uf900-\ufaff\uff00-\uffef\u3000-\u303f"
_cjk_end = re.compile(f"[{CJK}]$")
_cjk_start = re.compile(f"^[{CJK}]")


# ───────────────────────── 章節切割 ─────────────────────────

def split_sections(md):
    """回傳 (title, {field: markdown}, warnings)。"""
    title, cur, out, warns = None, None, {}, []
    buf = []
    in_fence = False

    def flush():
        if cur is not None:
            text = "\n".join(buf).strip("\n")
            out[cur] = (out[cur] + "\n\n" + text) if cur in out else text

    for line in md.splitlines():
        if line.lstrip().startswith("```"):
            in_fence = not in_fence
        if not in_fence:
            m = re.match(r"^(#{1,2})\s+(.*?)\s*#*\s*$", line)
            if m and len(m.group(1)) == 1 and title is None and cur is None:
                title = m.group(2)
                continue
            if m and len(m.group(1)) == 2:
                flush()
                buf = []
                name = re.sub(r"[\s:：]+$", "", m.group(2)).strip()
                cur = _ALIAS.get(name.lower())
                if cur is None:
                    warns.append(f"不認得的章節「## {name}」，內容併入 notes")
                    cur = "notes"
                    buf.append(f"### {name}")
                continue
        if cur is None:
            if line.strip():
                cur = "legend"  # 沒有 ## 標題的開頭內容當 legend
                buf.append(line)
        else:
            buf.append(line)
    flush()
    return title, out, warns


# ───────────────────────── 行內轉換 ─────────────────────────

_ESC = {"\\": r"\textbackslash{}", "{": r"\{", "}": r"\}", "%": r"\%", "&": r"\&",
        "#": r"\#", "_": r"\_", "~": r"\textasciitilde{}", "^": r"\textasciicircum{}",
        "$": r"\$"}


def escape(s):
    return "".join(_ESC.get(c, c) for c in s)


_INLINE = re.compile(
    r"(?P<code>`+)(?P<codebody>.+?)(?P=code)"          # `code`
    r"|(?P<dmath>\$\$.+?\$\$)"                          # $$math$$（行內）
    r"|(?P<math>(?<!\\)\$(?:\\.|[^$\\\n])+\$)"          # $math$
    r"|\\(?P<lit>[\\`*_{}\[\]()#+\-.!$|<>~])"           # Markdown 跳脫 \*
    r"|!\[(?P<imgalt>[^\]]*)\]\((?P<imgsrc>[^)\s]+)[^)]*\)"  # ![alt](src)
    r"|\[(?P<ltext>[^\]]+)\]\((?P<lurl>[^)\s]+)[^)]*\)"      # [text](url)
    r"|(?P<b>\*\*|__)(?P<bbody>.+?)(?P=b)"              # **bold**
    r"|(?<![\w*])\*(?P<ibody>[^\s*](?:.*?[^\s*])?)\*(?![\w*])"  # *italic*
    r"|(?<![\w_])_(?P<ubody>[^\s_](?:.*?[^\s_])?)_(?![\w_])"    # _italic_
    r"|(?P<html><(?:br|BR)\s*/?>)"                      # <br>
    r"|(?P<tag></?[A-Za-z][^>]*>)"                      # 其他 HTML
)


def inline(s, warns):
    out, pos = [], 0
    for m in _INLINE.finditer(s):
        out.append(escape(s[pos:m.start()]))
        pos = m.end()
        g = m.groupdict()
        if g["code"]:
            out.append(r"\texttt{" + escape(g["codebody"].strip()) + "}")
        elif g["dmath"] or g["math"]:
            out.append(g["dmath"] or g["math"])
        elif g["lit"] is not None:
            out.append(escape(g["lit"]))
        elif g["imgsrc"]:
            warns.append(f"圖片 {g['imgsrc']} 要另外上傳到 Polygon 的 statement resources")
            out.append(r"\includegraphics{" + g["imgsrc"] + "}")
        elif g["lurl"]:
            out.append(r"\href{" + g["lurl"].replace("%", r"\%").replace("#", r"\#") + "}{"
                       + inline(g["ltext"], warns) + "}")
        elif g["bbody"]:
            out.append(r"\textbf{" + inline(g["bbody"], warns) + "}")
        elif g["ibody"] or g["ubody"]:
            out.append(r"\textit{" + inline(g["ibody"] or g["ubody"], warns) + "}")
        elif g["html"]:
            out.append(r"\\ ")
        elif g["tag"]:
            warns.append(f"HTML 標籤 {g['tag']} 不支援，已移除")
    out.append(escape(s[pos:]))
    return "".join(out)


# ───────────────────────── 區塊轉換 ─────────────────────────

_LIST = re.compile(r"^(?P<ind>\s*)(?P<mark>[-*+]|\d+[.)])\s+(?P<body>.*)$")
_TABLE_SEP = re.compile(r"^\s*\|?\s*:?-+:?\s*(\|\s*:?-+:?\s*)*\|?\s*$")


def _cells(row):
    row = row.strip()
    if row.startswith("|"):
        row = row[1:]
    if row.endswith("|") and not row.endswith("\\|"):
        row = row[:-1]
    cells, cur, in_math, i = [], "", False, 0
    while i < len(row):
        c = row[i]
        if c == "\\" and i + 1 < len(row) and row[i + 1] == "|":
            cur += "|"
            i += 2
            continue
        if c == "$":
            in_math = not in_math
        if c == "|" and not in_math:
            cells.append(cur.strip())
            cur = ""
        else:
            cur += c
        i += 1
    cells.append(cur.strip())
    return cells


def _join_lines(lines):
    """段落內換行：中文字之間直接相接，其他補空白（LaTeX 會把換行當空白）。"""
    out = ""
    for ln in lines:
        hard = ln.endswith("  ") or ln.endswith("\\")
        ln = ln.rstrip("\\").strip()
        if out and not out.endswith("\n"):
            out += "" if (_cjk_end.search(out) and _cjk_start.search(ln)) else " "
        out += ln
        if hard:
            out += "\x00BR\x00"
    return out


def _table(lines, warns):
    head = _cells(lines[0])
    sep = _cells(lines[1])
    ncol = len(head)
    align = []
    for s in sep + [""] * (ncol - len(sep)):
        s = s.strip()
        align.append("c" if s.startswith(":") and s.endswith(":") else
                     "r" if s.endswith(":") else "l")
    rows = [head] + [_cells(r) for r in lines[2:]]
    out = [r"\begin{center}", r"\begin{tabular}{|" + "|".join(align[:ncol]) + "|}", r"\hline"]
    for k, r in enumerate(rows):
        r = (r + [""] * ncol)[:ncol]
        cells = [inline(c, warns) for c in r]
        if k == 0:
            cells = [r"\textbf{" + c + "}" if c else c for c in cells]
        out.append(" & ".join(cells) + r" \\ \hline")
    out += [r"\end{tabular}", r"\end{center}"]
    return out


def _list(lines, warns):
    """lines：連續的清單行（含續行）。依縮排巢狀。"""
    out, stack = [], []  # stack: [(indent, env)]
    item_buf = []

    def flush_item():
        if item_buf:
            out.append(r"\item " + inline(_join_lines(item_buf), warns).replace("\x00BR\x00", r"\\ "))
            item_buf.clear()

    for ln in lines:
        m = _LIST.match(ln)
        if not m:
            item_buf.append(ln)
            continue
        ind = len(m.group("ind").expandtabs(4))
        env = "enumerate" if m.group("mark")[0].isdigit() else "itemize"
        flush_item()
        while stack and ind < stack[-1][0]:
            out.append(r"\end{" + stack.pop()[1] + "}")
        if not stack or ind > stack[-1][0]:
            stack.append((ind, env))
            out.append(r"\begin{" + env + "}")
        elif stack[-1][1] != env:
            out.append(r"\end{" + stack.pop()[1] + "}")
            stack.append((ind, env))
            out.append(r"\begin{" + env + "}")
        item_buf.append(m.group("body"))
    flush_item()
    while stack:
        out.append(r"\end{" + stack.pop()[1] + "}")
    return out


def md_to_latex(md, warns=None):
    """把一段 Markdown 轉成 Polygon LaTeX。warns 收集警告訊息。"""
    if warns is None:
        warns = []
    lines = md.replace("\r\n", "\n").split("\n")
    blocks, i = [], 0
    while i < len(lines):
        ln = lines[i]
        s = ln.strip()
        if not s:
            i += 1
            continue
        # ``` 程式碼區塊
        if s.startswith("```"):
            body = []
            i += 1
            while i < len(lines) and not lines[i].strip().startswith("```"):
                body.append(lines[i])
                i += 1
            i += 1
            blocks.append("\\begin{verbatim}\n" + "\n".join(body) + "\n\\end{verbatim}")
            continue
        # $$ 區塊數學（可跨行）
        if s.startswith("$$"):
            body = [ln]
            if not (len(s) > 2 and s.endswith("$$") and s != "$$"):
                i += 1
                while i < len(lines) and "$$" not in lines[i]:
                    body.append(lines[i])
                    i += 1
                if i < len(lines):
                    body.append(lines[i])
            i += 1
            blocks.append("\n".join(b.strip() for b in body))
            continue
        # 小標題
        m = re.match(r"^#{1,6}\s+(.*?)\s*#*\s*$", s)
        if m:
            blocks.append(r"\textbf{" + inline(m.group(1), warns) + "}")
            i += 1
            continue
        # 分隔線
        if re.match(r"^([-*_])(\s*\1){2,}$", s):
            i += 1
            continue
        # 表格
        if "|" in s and i + 1 < len(lines) and _TABLE_SEP.match(lines[i + 1]):
            tl = [ln, lines[i + 1]]
            i += 2
            while i < len(lines) and lines[i].strip() and "|" in lines[i]:
                tl.append(lines[i])
                i += 1
            blocks.append("\n".join(_table(tl, warns)))
            continue
        # 清單
        if _LIST.match(ln):
            ll = []
            while i < len(lines):
                cur = lines[i]
                if _LIST.match(cur) or (cur.strip() and cur.startswith((" ", "\t")) and ll):
                    ll.append(cur)
                    i += 1
                elif not cur.strip() and i + 1 < len(lines) and _LIST.match(lines[i + 1]):
                    i += 1  # 清單項目之間的空行
                else:
                    break
            blocks.append("\n".join(_list(ll, warns)))
            continue
        # 引言：去掉 > 當一般段落
        if s.startswith(">"):
            para = []
            while i < len(lines) and lines[i].strip().startswith(">"):
                para.append(lines[i].strip()[1:].strip())
                i += 1
            blocks.append(inline(_join_lines(para), warns).replace("\x00BR\x00", "\\\\\n"))
            continue
        # 一般段落
        para = []
        while i < len(lines):
            cur = lines[i]
            cs = cur.strip()
            if not cs or cs.startswith(("```", "$$", "#", ">")) or _LIST.match(cur) or (
                    "|" in cs and i + 1 < len(lines) and _TABLE_SEP.match(lines[i + 1])):
                break
            para.append(cur)
            i += 1
        blocks.append(inline(_join_lines(para), warns).replace("\x00BR\x00", "\\\\\n"))
    return "\n\n".join(blocks)


# ───────────────────────── 題目層級 ─────────────────────────

def _strip_title(t):
    t = re.sub(r"^p?[A-Za-z0-9]{1,3}[.:：、]\s*", "", t.strip())  # "pA. 題名" → "題名"
    return t.strip()


def scoring_check(md_scoring, groups):
    """比對 Scoring 表的分數欄與 polygon.json groups 的 points，回傳警告列表。"""
    warns = []
    scored = [g for g in groups if g.get("points")]
    if not scored:
        return warns
    if not md_scoring:
        return ["statement.md 沒有 ## Scoring，但 polygon.json 有子題配分"]
    lines = [l for l in md_scoring.splitlines() if l.strip().startswith("|") or "|" in l]
    if len(lines) < 3 or not _TABLE_SEP.match(lines[1]):
        return warns  # 不是表格就不比對
    head = [c.strip().lower() for c in _cells(lines[0])]
    col = next((k for k, h in enumerate(head) if h in ("分數", "配分", "points", "score", "分")), None)
    if col is None:
        return warns
    pts = []
    for r in lines[2:]:
        cells = _cells(r)
        if col < len(cells):
            m = re.search(r"\d+", cells[col])
            if m:
                pts.append(int(m.group()))
    want = [int(g["points"]) for g in scored]
    if pts != want:
        warns.append(f"Scoring 表的分數 {pts} 和 polygon.json groups 的 points {want} 不一致")
    return warns


def convert_problem(root, cfg=None):
    """讀 root/statement.md，回傳 (fields, warnings)。
    fields：{"name": 題名, "legend": …, "input": …, …}，只含 statement.md 有寫的章節（name 除外）。"""
    root = Path(root)
    if cfg is None:
        cfg = json.loads((root / "polygon.json").read_text(encoding="utf-8"))
    p = root / "statement.md"
    if not p.is_file():
        return None, [f"找不到 {p}"]
    md = p.read_text(encoding="utf-8-sig")
    title, secs, warns = split_sections(md)
    fields = {}
    if cfg.get("title"):
        fields["name"] = cfg["title"]
    elif title:
        fields["name"] = _strip_title(title)
        warns.append(f"polygon.json 沒有 title，改用 statement.md 的標題「{fields['name']}」")
    for k in ("legend", "input", "output"):
        if not secs.get(k, "").strip():
            warns.append(f"statement.md 缺少 {k} 章節")
    if secs.get("interaction") and not cfg.get("interactive"):
        warns.append("非互動題卻有 Interaction 章節，上傳時會略過")
    for k, v in secs.items():
        w = []
        fields[k] = md_to_latex(v, w)
        warns += [f"[{k}] {x}" for x in w]
    warns += scoring_check(secs.get("scoring", ""), cfg.get("groups", []))
    return fields, warns


def render_preview(fields):
    """組成一份方便閱讀、可整段複製的 .tex。"""
    out = ["% 由 md2polygon.py 從 statement.md 產生，請改 statement.md，不要改這份。"]
    if fields.get("name"):
        out.append(f"% Name: {fields['name']}")
    for k in FIELDS:
        if k in fields:
            out += ["", f"% ─── {k} " + "─" * (60 - len(k)), "", fields[k]]
    return "\n".join(out) + "\n"


def main():
    if not sys.stdout.isatty():
        sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser(description="statement.md → Polygon 題敘 LaTeX")
    ap.add_argument("problem", help="題目資料夾，例如 pA")
    ap.add_argument("--stdout", action="store_true", help="印出而不寫檔")
    a = ap.parse_args()
    root = Path(a.problem)
    fields, warns = convert_problem(root)
    if fields is None:
        sys.exit(warns[0])
    text = render_preview(fields)
    if a.stdout:
        print(text)
    else:
        out = root / ".build" / "statement.tex"
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(text, encoding="utf-8")
        print(f"已寫入 {out}")
    for w in warns:
        print(f"  [警告] {w}", file=sys.stderr if a.stdout else sys.stdout)


if __name__ == "__main__":
    main()
