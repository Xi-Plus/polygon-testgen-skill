#!/usr/bin/env python3
"""
把題目資料夾上傳到 Codeforces Polygon（官方 API），可一次處理多題、只更新指定項目。

用法：
    python upload_to_polygon.py pA                    上傳 pA/ 的全部項目並建 package
    python upload_to_polygon.py A C                   單一字母會自動找 pA/、pC/
    python upload_to_polygon.py --all                 所有含 polygon.json 的 p*/ 資料夾
    python upload_to_polygon.py pA pB --only statement,package
    python upload_to_polygon.py --all --skip package
    python upload_to_polygon.py --all --dry-run       只列出會送的請求

項目（--only / --skip 用逗號分隔，不指定就是全部）：
    info       時間、記憶體限制（新題目一定會做）
    title      只寫題名（polygon.json 的 title）
    statement  題敘內容 + 題名（statement.md → LaTeX），之後請 Polygon 編譯並回報錯誤
    validator  files/ 全部檔案 + 設定 validator 與 checker
    solution   solutions/ 的解答與 tag
    test       files/ 全部檔案 + 範例 + test script + 群組、配分、dependencies
    access     依 polygon.json 的 access 設定使用者權限（例如 {"codeforces": "READ"}），立即生效、不需 commit；
               沒有 access 欄位就不動任何權限
    package    建 Full package（含 verification）並等待完成

流程：每題依序上傳選到的項目並 commit 一次；所有題目 commit 完後一起建 package、輪詢狀態。
某題失敗不會中止其他題，最後印出總表；有任何失敗時結束碼為 1。

每題一個資料夾，內容：
    polygon.json      題目設定（Polygon id、名稱、題名 title、時限、checker、範例、群組配分、解答標記）
    files/            testlib.h、gen.cpp、val.cpp…（.h → resource，其餘 → source）
    solutions/        解答
    tests/01, 02…     範例測資（對應 polygon.json 的 samples）
    script.txt        test script，由 Polygon 用 generator 產生其餘測資
    statement.md      題敘；用 md2polygon.py 轉成 LaTeX 後上傳（Polygon 題敘不支援 Markdown）

polygon.json 沒有 id 時會建立新題目並把 id 寫回。
key/secret 從 .env（key=… / secret=…）或環境變數 POLYGON_KEY / POLYGON_SECRET 讀取。
API key 在 Polygon 右上角 Settings → API Keys 產生。需要: pip install requests
"""
import argparse, hashlib, json, os, random, re, string, sys, time
from pathlib import Path

API = "https://polygon.codeforces.com/api/"
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import md2polygon  # noqa: E402  同一層的 md2polygon.py

PARTS = ["info", "title", "statement", "validator", "solution", "test", "access", "package"]
ACCESS_TYPES = ("READ", "WRITE", "NONE")
POLL_INTERVAL = 20      # 秒；輪詢 package 狀態的間隔（太密會被 429）
PACKAGE_TIMEOUT = 1800  # 秒


class PolygonError(Exception):
    pass


def load_dotenv(roots):
    """依序從題目資料夾、其上一層、目前目錄、腳本所在資料夾找 .env 讀 key / secret。
    只讀第一個找到的檔案，不覆蓋已存在的環境變數。"""
    alias = {"KEY": "POLYGON_KEY", "SECRET": "POLYGON_SECRET",
             "POLYGON_KEY": "POLYGON_KEY", "POLYGON_SECRET": "POLYGON_SECRET"}
    cands = []
    for r in roots:
        cands += [r / ".env", r.parent / ".env"]
    cands += [Path.cwd() / ".env", HERE / ".env"]
    for p in cands:
        if not p.is_file():
            continue
        for line in p.read_text(encoding="utf-8-sig").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            k = k.strip().removeprefix("export ").strip().upper()
            v = v.strip().strip('"').strip("'")
            if k in alias and v:
                os.environ.setdefault(alias[k], v)
        return


def parse_range(s):
    """'1-2' → [1, 2]；'3,5,7-9' → [3, 5, 7, 8, 9]"""
    out = []
    for part in str(s).split(","):
        part = part.strip()
        if "-" in part:
            lo, hi = map(int, part.split("-"))
            out.extend(range(lo, hi + 1))
        elif part:
            out.append(int(part))
    return out


class Polygon:
    def __init__(self, key, secret, dry):
        self.key, self.secret, self.dry = key, secret, dry
        self.prefix = ""
        if not dry:
            import requests
            self.s = requests.Session()

    def call(self, method, fatal=True, quiet=False, **params):
        params = {k: (str(v).lower() if isinstance(v, bool) else str(v)) for k, v in params.items()}
        if self.dry:
            short = {k: (v[:40] + "…" if len(v) > 40 else v) for k, v in params.items()}
            print(f"{self.prefix}[dry-run] {method} {short}")
            return {}
        params["apiKey"] = self.key
        for wait in (5, 10, 20, 40, 60, 90, 120, None):
            p = dict(params)
            p["time"] = str(int(time.time()))  # 每次重試都要重新簽章
            rand = "".join(random.choices(string.ascii_lowercase + string.digits, k=6))
            q = "&".join(f"{k}={v}" for k, v in sorted(p.items()))
            p["apiSig"] = rand + hashlib.sha512(f"{rand}/{method}?{q}#{self.secret}".encode()).hexdigest()
            try:
                r = self.s.post(API + method, data={k: v.encode() for k, v in p.items()}, timeout=60)
            except Exception as e:  # 網路斷線、逾時
                if wait is None:
                    raise PolygonError(f"{method}: {type(e).__name__}: {e}")
                print(f"{self.prefix}    {method}: {type(e).__name__}，{wait} 秒後重試…")
                time.sleep(wait)
                continue
            if (r.status_code == 429 or r.status_code >= 500) and wait is not None:
                print(f"{self.prefix}    {method}: HTTP {r.status_code}，{wait} 秒後重試…")
                time.sleep(wait)
                continue
            break
        try:
            j = r.json()
        except ValueError:
            raise PolygonError(f"{method}: HTTP {r.status_code}, 非 JSON 回應: {r.text[:300]}")
        if j.get("status") != "OK":
            if not fatal:
                print(f"{self.prefix}    {method} 失敗（略過）: {j.get('comment')}")
                return None
            raise PolygonError(f"{method} 失敗: {j.get('comment')}")
        if not quiet:
            print(f"{self.prefix}OK  {method}")
        return j.get("result")


def resolve_problem_dir(arg):
    """'pA' / 'path/to/pA' 直接當路徑；單一字母 'A' 依序在目前目錄與腳本所在資料夾找 pA/。"""
    p = Path(arg)
    if p.is_dir():
        return p.resolve()
    s = arg.strip()
    if len(s) <= 2 and s.upper().removeprefix("P").isalpha():
        name = "p" + s.upper().removeprefix("P")
        for base in (Path.cwd(), HERE):
            if (base / name).is_dir():
                return (base / name).resolve()
    sys.exit(f"找不到題目資料夾：{arg}")


def find_all_problems():
    """目前目錄（找不到再用腳本所在資料夾）下所有含 polygon.json 的 p*/。"""
    for base in (Path.cwd(), HERE):
        dirs = sorted(d.resolve() for d in base.glob("p*") if (d / "polygon.json").is_file())
        if dirs:
            return dirs
    sys.exit("找不到任何含 polygon.json 的 p*/ 資料夾")


def parse_parts(only, skip):
    def split(s):
        items = [x.strip() for x in s.split(",") if x.strip()]
        bad = [x for x in items if x not in PARTS]
        if bad:
            sys.exit(f"不認得的項目：{', '.join(bad)}（可用：{', '.join(PARTS)}）")
        return items
    if only and skip:
        sys.exit("--only 與 --skip 不能同時使用")
    if only:
        sel = set(split(only))
    else:
        sel = set(PARTS) - set(split(skip or ""))
    if not sel:
        sys.exit("沒有任何要做的項目")
    return [p for p in PARTS if p in sel]


# ---------------------------------------------------------------- 各項目

def read(root, p):
    return (root / p).read_text(encoding="utf-8")


def test_file(root, idx):
    for name in (f"tests/{idx:02d}", f"tests/{idx}"):
        if (root / name).is_file():
            return name
    raise PolygonError(f"找不到範例測資 tests/{idx:02d}")


def upload_statement(pg, pid, root, cfg, with_body):
    """with_body=True：statement.md 轉 LaTeX 後連同題名寫入每個 statementLangs；
    False：只寫題名。回傳是否上傳了內容。"""
    langs = cfg.get("statementLangs", ["english"])
    if not with_body:
        if not cfg.get("title"):
            raise PolygonError("polygon.json 沒有 title")
        for lang in langs:
            pg.call("problem.saveStatement", problemId=pid, lang=lang, name=cfg["title"])
        return False
    if not (root / "statement.md").is_file():
        raise PolygonError(f"找不到 {root / 'statement.md'}")
    fields, warns = md2polygon.convert_problem(root, cfg)
    for w in warns:
        print(f"{pg.prefix}    [題敘警告] {w}")
    kw = {"encoding": "UTF-8"}
    if fields.get("name"):
        kw["name"] = fields["name"]
    # statement.md 是唯一來源：沒寫的章節送空字串，清掉 Polygon 上的舊內容
    for k in ("legend", "input", "output", "scoring", "notes"):
        kw[k] = fields.get(k, "")
    if cfg.get("interactive"):
        kw["interaction"] = fields.get("interaction", "")
    if "tutorial" in fields:
        kw["tutorial"] = fields["tutorial"]
    for lang in langs:
        pg.call("problem.saveStatement", problemId=pid, lang=lang, **kw)
    return True


def check_render(pg, pid):
    """請 Polygon 編譯題敘，回傳失敗的項目清單（例如 ['english pdf']）；API 不支援時回傳 []。"""
    res = pg.call("problem.renderStatements", fatal=False, problemId=pid)
    failed = []
    for kind in ("statements", "tutorials"):
        for item in (res or {}).get(kind) or []:
            for fmt in ("html", "pdf"):
                r = item.get(fmt) or {}
                if r.get("status") == "FAILED":
                    msg = str(r.get("message") or "")
                    m = re.search(r"! (LaTeX Error: [^\n]*|[^\n]*Error[^\n]*)", msg)
                    print(f"{pg.prefix}  ⚠ {kind} {item.get('language')} {fmt} 編譯失敗："
                          f"{m.group(1) if m else msg[:200]}")
                    failed.append(f"{item.get('language')} {fmt}")
    return failed


def upload_files(pg, pid, root):
    for f in sorted((root / "files").iterdir()):
        if f.is_file():
            typ = "resource" if f.suffix == ".h" else "source"
            pg.call("problem.saveFile", problemId=pid, type=typ, name=f.name,
                    file=f.read_text(encoding="utf-8"))


def upload_tests(pg, pid, root, cfg):
    groups = cfg.get("groups", [])
    samples = parse_range(cfg.get("samples", ""))
    group_of = {i: str(g["group"]) for g in groups for i in parse_range(g["tests"])}
    if groups:
        pg.call("problem.enablePoints", problemId=pid, enable=True)
        pg.call("problem.enableGroups", problemId=pid, testset="tests", enable=True)

    # 範例：手動上傳
    for idx in samples:
        kw = dict(problemId=pid, testset="tests", testIndex=idx,
                  testInput=read(root, test_file(root, idx)), testUseInStatements=True)
        if idx in group_of:
            kw["testGroup"] = group_of[idx]
            kw["testPoints"] = 0
        pg.call("problem.saveTest", **kw)

    # 其餘：Polygon 依 script.txt 產生
    # 拿掉 Freemarker 註解 <#-- -->：有它 Polygon 會進 Freemarker 模式，就不能用 "> 3" 這種固定編號
    if (root / "script.txt").is_file():
        script = re.sub(r"<#--.*?-->", "", read(root, "script.txt"), flags=re.S)
        script = "\n".join(l for l in script.splitlines() if l.strip()) + "\n"
        pg.call("problem.saveScript", problemId=pid, testset="tests", source=script)

    # 群組；每組分數放在該組第一筆，其餘預設 0
    for g in groups:
        idxs = [i for i in parse_range(g["tests"]) if i not in samples]  # 範例已在上面設好群組
        if idxs:
            pg.call("problem.setTestGroup", problemId=pid, testset="tests", testGroup=g["group"],
                    testIndices=",".join(map(str, idxs)))
        if g.get("points"):
            pg.call("problem.saveTest", problemId=pid, testset="tests",
                    testIndex=parse_range(g["tests"])[0], testPoints=g["points"])
    for g in groups:
        kw = dict(problemId=pid, testset="tests", group=g["group"],
                  pointsPolicy=g.get("policy", "COMPLETE_GROUP"))
        if g.get("dependencies"):
            kw["dependencies"] = g["dependencies"]
        pg.call("problem.saveTestGroup", **kw)


def set_access(pg, pid, cfg):
    """polygon.json 的 access：{login: READ|WRITE|NONE}。回傳摘要字串；沒有設定時回傳 None。
    problem.setAccess 是冪等的：重複設定相同權限會成功且不寄通知。"""
    acc = cfg.get("access")
    if not acc:
        return None
    if not isinstance(acc, dict):
        raise PolygonError('polygon.json 的 access 必須是 {"login": "READ"} 這種物件')
    out = []
    for login, typ in acc.items():
        typ = str(typ).upper()
        if typ not in ACCESS_TYPES:
            raise PolygonError(f"access 的 {login} 權限 {typ} 不合法（可用 {', '.join(ACCESS_TYPES)}）")
        pg.call("problem.setAccess", problemId=pid, login=login, accessType=typ)
        out.append(f"{login}={typ}")
    return " ".join(out)


# ---------------------------------------------------------------- 每題

def process_problem(pg, root, parts, problem_id, dry):
    """上傳一題選到的項目（package 除外）並 commit。回傳結果 dict。"""
    label = root.name
    res = {"label": label, "pid": "", "done": [], "error": None, "render_failed": [], "access": None}
    cfg_file = root / "polygon.json"
    if not cfg_file.is_file():
        res["error"] = f"找不到 {cfg_file}"
        return res
    cfg = json.loads(cfg_file.read_text(encoding="utf-8"))
    pg.prefix = f"[{label}] "
    try:
        # 題目 ID：--problem-id > polygon.json 的 id > 建立新題目（並把 id 寫回 polygon.json）
        pid = str(problem_id or cfg.get("id") or "")
        parts = list(parts)
        if not pid:
            r = pg.call("problem.create", name=cfg["name"])
            pid = str(r["id"]) if r else "<new-id>"
            print(f"{pg.prefix}已建立題目 id={pid}")
            if not dry:
                # 插在第一個 { 後面，保留原本的排版
                text = cfg_file.read_text(encoding="utf-8")
                text = re.sub(r"^\s*\{", lambda m: m.group(0) + f'\n  "id": {pid},', text, count=1)
                cfg_file.write_text(text, encoding="utf-8")
                print(f"{pg.prefix}已把 id 寫回 {cfg_file}")
            if "info" not in parts:
                parts.insert(0, "info")
        res["pid"] = pid

        if "info" in parts:
            pg.call("problem.updateInfo", problemId=pid, inputFile="stdin", outputFile="stdout",
                    interactive=False, timeLimit=cfg.get("timeLimit", 1000),
                    memoryLimit=cfg.get("memoryLimit", 256))
            res["done"].append("info")
        if "statement" in parts:
            upload_statement(pg, pid, root, cfg, with_body=True)
            res["done"].append("statement")
        elif "title" in parts:
            upload_statement(pg, pid, root, cfg, with_body=False)
            res["done"].append("title")
        if "validator" in parts or "test" in parts:
            upload_files(pg, pid, root)
        if "validator" in parts:
            if cfg.get("validator"):
                pg.call("problem.setValidator", problemId=pid, validator=cfg["validator"])
            pg.call("problem.setChecker", problemId=pid, checker=cfg.get("checker", "std::wcmp.cpp"))
            res["done"].append("validator")
        if "solution" in parts:
            for fn, tag in cfg["solutions"].items():
                pg.call("problem.saveSolution", problemId=pid, name=fn,
                        file=read(root, f"solutions/{fn}"), tag=tag)
            res["done"].append("solution")
        if "test" in parts:
            upload_tests(pg, pid, root, cfg)
            res["done"].append("test")

        if res["done"]:
            pg.call("problem.commitChanges", problemId=pid, minorChanges=True,
                    message=f"{label}: update {','.join(res['done'])} via upload_to_polygon.py")
        if "statement" in res["done"]:
            res["render_failed"] = check_render(pg, pid)
        if "access" in parts:  # 權限存在題目層級，不經過 working copy，所以放在 commit 之後
            res["access"] = set_access(pg, pid, cfg) or "polygon.json 沒有 access，未變更"
    except PolygonError as e:
        res["error"] = str(e)
        print(f"{pg.prefix}✗ {e}")
    except (OSError, KeyError, json.JSONDecodeError) as e:
        res["error"] = f"{type(e).__name__}: {e}"
        print(f"{pg.prefix}✗ {res['error']}")
    pg.prefix = ""
    return res


def build_packages(pg, results, dry):
    """對成功的題目一起送出 buildPackage，再輪詢到全部 READY / FAILED 或逾時。"""
    pending = {}
    for r in results:
        if r["error"] or not r["pid"]:
            continue
        pg.prefix = f"[{r['label']}] "
        try:
            before = set() if dry else {x["id"] for x in pg.call(
                "problem.packages", quiet=True, problemId=r["pid"]) or []}
            pg.call("problem.buildPackage", problemId=r["pid"], full=True, verify=True)
            r["package"] = "dry-run" if dry else "建置中"
            if not dry:
                pending[r["label"]] = (r, before)
        except PolygonError as e:
            r["package"] = f"FAILED（{e}）"
            print(f"{pg.prefix}✗ {e}")
        time.sleep(0 if dry else 1)
    pg.prefix = ""
    if not pending:
        return
    print(f"\n等待 {len(pending)} 題的 package 建置完成（每題約 2～4 分鐘，每 {POLL_INTERVAL} 秒查詢一次）…")
    start = time.time()
    while pending and time.time() - start < PACKAGE_TIMEOUT:
        time.sleep(POLL_INTERVAL)
        for label in list(pending):
            r, before = pending[label]
            try:
                pkgs = pg.call("problem.packages", quiet=True, problemId=r["pid"]) or []
            except PolygonError as e:
                print(f"[{label}]     problem.packages: {e}")
                continue
            new = [x for x in pkgs if x["id"] not in before]
            if new and new[0].get("state") in ("READY", "FAILED"):
                x = new[0]
                state = x["state"]
                comment = (x.get("comment") or "").strip()
                r["package"] = f"{state} #{x['id']} rev{x.get('revision')}"
                if state == "FAILED":
                    r["package"] += f"（{comment[:300]}）"
                print(f"[{label}] package {r['package']}  {comment[:120] if state == 'READY' else ''}")
                del pending[label]
            time.sleep(1)
    for label, (r, _) in pending.items():
        r["package"] = "逾時（到 Polygon Package 頁查看）"


def print_summary(results, parts):
    print("\n==== 總表 ====")
    for r in results:
        status = f"✗ {r['error']}" if r["error"] else "ok"
        line = f"{r['label']:<4} id={r['pid'] or '-':<8} {status}"
        if r["done"]:
            line += f"  上傳：{','.join(r['done'])}"
        if r.get("access"):
            line += f"  權限：{r['access']}"
        if r.get("package"):
            line += f"  package：{r['package']}"
        if r["render_failed"]:
            line += f"  題敘編譯失敗：{', '.join(r['render_failed'])}"
        print(line)
    if any(r["render_failed"] and all(f.endswith("pdf") for f in r["render_failed"]) for r in results):
        print("\n只有 PDF 編譯失敗時，通常是題敘含中文而 Polygon 的 LaTeX 不支援；HTML 題敘與 package 不受影響。")
    if "package" not in parts and any(r["done"] for r in results):
        print("\n沒有建 package：內容有變動時，記得用 --only package 重新建立。")
    print("到 Polygon 確認：Statements 預覽 HTML；Tests → Preview tests。")
    if any((r.get("access") or "").startswith("polygon.json 沒有") for r in results):
        print('要用於 Codeforces Gym/Mashup 時，polygon.json 加上 "access": {"codeforces": "READ"} 再跑 --only access。')


def main():
    for stream in (sys.stdout, sys.stderr):  # 導到檔案或管線時，Windows 預設 cp950 會讓中文亂碼
        if not stream.isatty():
            stream.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser(description="上傳題目到 Codeforces Polygon（可多題、可只更新部分項目）")
    ap.add_argument("problems", nargs="*", help="題目資料夾（例如 pA pB），或單一字母（A B）")
    ap.add_argument("--all", action="store_true", help="所有含 polygon.json 的 p*/ 資料夾")
    ap.add_argument("--only", help=f"只做這些項目，逗號分隔：{','.join(PARTS)}")
    ap.add_argument("--skip", help="跳過這些項目，逗號分隔")
    ap.add_argument("--problem-id", help="指定題目 ID（只能搭配單一題目）")
    ap.add_argument("--dry-run", action="store_true", help="只列出會送的請求")
    a = ap.parse_args()

    if a.all and a.problems:
        sys.exit("--all 不能和題目參數一起使用")
    roots = find_all_problems() if a.all else [resolve_problem_dir(p) for p in a.problems]
    if not roots:
        ap.error("請指定題目資料夾，或使用 --all")
    if a.problem_id and len(roots) != 1:
        sys.exit("--problem-id 只能搭配單一題目")
    parts = parse_parts(a.only, a.skip)
    print(f"題目：{' '.join(r.name for r in roots)}")
    print(f"項目：{','.join(parts)}{'（dry-run）' if a.dry_run else ''}\n")

    load_dotenv(roots)
    key, secret = os.environ.get("POLYGON_KEY"), os.environ.get("POLYGON_SECRET")
    if not a.dry_run and not (key and secret):
        sys.exit("找不到 key/secret：請在 .env 寫 key=... 與 secret=...，或設定環境變數 POLYGON_KEY / POLYGON_SECRET")
    pg = Polygon(key, secret, a.dry_run)

    upload_parts = [p for p in parts if p != "package"]
    results = []
    for root in roots:
        results.append(process_problem(pg, root, upload_parts, a.problem_id, a.dry_run))
        print()
    if "package" in parts:
        build_packages(pg, results, a.dry_run)
    print_summary(results, parts)
    sys.exit(1 if any(r["error"] or "FAILED" in str(r.get("package", "")) for r in results) else 0)


if __name__ == "__main__":
    main()
