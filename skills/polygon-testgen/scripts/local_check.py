#!/usr/bin/env python3
"""
在本機模擬 Polygon：轉換題敘 → 編譯 → 依 script.txt 產生測資 → validator → 產生答案 → 跑所有解答並對照 tag。

用法：
    python local_check.py pA                 完整檢查
    python local_check.py pA --no-gen        沿用 tests/ 現有測資，只跑 validator 與解答
    python local_check.py pA --only wa_x.cpp,brute.cpp   只跑指定解答（main 一定會跑）
    python local_check.py pA --tl-factor 1.5 本機比 Polygon 慢時放寬時限

題目資料夾結構與 polygon.json 格式見 skill 的 references/polygon-json.md。
需要 g++（PATH 中，或用 --cxx 指定）。只用 Python 標準函式庫。

結束碼：0 = 全部通過；1 = 有錯誤（測資不合法、解答不符 tag…）。警告不影響結束碼。
"""
import argparse, concurrent.futures as cf, hashlib, json, os, re, shlex, shutil, subprocess, sys, tempfile, time
from pathlib import Path

EXE = ".exe" if os.name == "nt" else ""
HERE = Path(__file__).resolve().parent
errors, warnings = [], []


def err(msg):
    errors.append(msg)
    print(f"  [錯誤] {msg}")


def warn(msg):
    warnings.append(msg)
    print(f"  [警告] {msg}")


def parse_range(s):
    out = []
    for part in str(s).split(","):
        part = part.strip()
        if "-" in part:
            lo, hi = map(int, part.split("-"))
            out.extend(range(lo, hi + 1))
        elif part:
            out.append(int(part))
    return out


def test_path(root, idx):
    for name in (f"{idx:02d}", f"{idx}"):
        if (root / "tests" / name).is_file():
            return root / "tests" / name
    return root / "tests" / f"{idx:02d}"


# ---------------------------------------------------------------- 編譯

def find_testlib(root):
    for p in (root / "files" / "testlib.h", root.parent / "testlib.h",
              HERE.parent / "assets" / "testlib.h"):
        if p.is_file():
            return p.parent
    sys.exit("找不到 testlib.h：請放在 files/testlib.h（skill 的 assets/testlib.h 可直接複製）")


def compile_one(src, out, include_dir, a):
    if out.is_file() and out.stat().st_mtime >= src.stat().st_mtime and \
            out.stat().st_mtime >= (include_dir / "testlib.h").stat().st_mtime:
        return True, ""
    cmd = [a.cxx, f"-std={a.std}", "-O2", "-I", str(include_dir), "-o", str(out), str(src)]
    if os.name == "nt":
        # Windows 預設 stack 很小，遞迴解會 RE；
        # FOR_LINUX：testlib 在 Windows 的 strict 模式預設要求 CRLF，但 Polygon（Linux）上的測資是 LF
        cmd[1:1] = ["-Wl,--stack=268435456", "-DFOR_LINUX"]
    r = subprocess.run(cmd, capture_output=True, text=True, errors="replace")
    return r.returncode == 0, r.stderr


def portability_lint(src):
    """Polygon 的 validator / generator / checker 可能用 32 位元 g++ 編譯。"""
    text = src.read_text(encoding="utf-8", errors="replace")
    text = re.sub(r"//[^\n]*|/\*.*?\*/", "", text, flags=re.S)  # 註解裡提到不算
    if "__int128" in text:
        err(f"{src.name} 使用 __int128：Polygon 以 32 位元 g++ 編譯時會失敗，請改寫")
    if re.search(r"\b(rand|srand|random_shuffle)\s*\(", text) or "mt19937" in text:
        warn(f"{src.name} 用了 rand()/random_shuffle/mt19937：請改用 testlib 的 rnd，否則不同平台產生的測資不同")


# ---------------------------------------------------------------- 執行

def run(exe, args=(), stdin_path=None, stdout_path=None, timeout=None):
    """回傳 (returncode 或 None 表示逾時, 秒數, stderr)"""
    fin = open(stdin_path, "rb") if stdin_path else subprocess.DEVNULL
    fout = open(stdout_path, "wb") if stdout_path else subprocess.DEVNULL
    t = time.perf_counter()
    try:
        p = subprocess.run([str(exe), *args], stdin=fin, stdout=fout, stderr=subprocess.PIPE, timeout=timeout)
        return p.returncode, time.perf_counter() - t, p.stderr.decode(errors="replace")
    except subprocess.TimeoutExpired:
        return None, time.perf_counter() - t, ""
    finally:
        if stdin_path: fin.close()
        if stdout_path: fout.close()


# ---------------------------------------------------------------- checker

def make_checker(cfg, root, bins, a):
    name = cfg.get("checker", "std::wcmp.cpp")
    std = name.removeprefix("std::").removesuffix(".cpp")
    if not name.startswith("std::"):
        exe = bins.get(Path(name).stem)
        if exe is None:
            sys.exit(f"checker {name} 不在 files/ 裡")

        def custom(inp, out, ans):
            rc, _, msg = run(exe, [str(inp), str(out), str(ans)], timeout=30)
            return rc == 0, msg.strip()[:200]
        return custom

    def tokens(p):
        return Path(p).read_bytes().decode(errors="replace").split()

    if std in ("rcmp", "rcmp4", "rcmp6", "rcmp9", "acmp", "dcmp", "rncmp"):
        eps = {"rcmp4": 1e-4, "rcmp6": 1e-6, "rcmp9": 1e-9, "acmp": 1.5e-5, "dcmp": 1e-6}.get(std, 1.5e-5)

        def real(inp, out, ans):
            o, e = tokens(out), tokens(ans)
            if len(o) != len(e):
                return False, f"token 數不同：{len(o)} vs {len(e)}"
            for i, (x, y) in enumerate(zip(o, e)):
                try:
                    fx, fy = float(x), float(y)
                except ValueError:
                    return False, f"第 {i+1} 個不是實數"
                if abs(fx - fy) > eps * max(1.0, abs(fy)):
                    return False, f"第 {i+1} 個：{x} vs {y}"
            return True, ""
        return real

    if std not in ("wcmp", "ncmp", "lcmp", "fcmp", "hcmp", "yesno", "nyesno", "icmp", "uncmp"):
        warn(f"checker {name} 沒有在本機模擬，改用逐 token 比對")
    fold = std in ("yesno", "nyesno")

    def tok(inp, out, ans):
        o, e = tokens(out), tokens(ans)
        if fold:
            o, e = [x.lower() for x in o], [x.lower() for x in e]
        if std == "uncmp":
            o, e = sorted(o), sorted(e)
        if o == e:
            return True, ""
        for i, (x, y) in enumerate(zip(o, e)):
            if x != y:
                return False, f"第 {i+1} 個 token：{x[:30]} vs {y[:30]}"
        return False, f"token 數不同：{len(o)} vs {len(e)}"
    return tok


# ---------------------------------------------------------------- 主流程

def main():
    if not sys.stdout.isatty():  # 輸出被導到檔案或管線時，Windows 預設 cp950 會讓中文亂碼
        sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser(description="在本機模擬 Polygon 檢查題目")
    ap.add_argument("problem", help="題目資料夾，例如 pA")
    ap.add_argument("--no-gen", action="store_true", help="不重新產生測資")
    ap.add_argument("--only", help="只跑這些解答（逗號分隔，main 一定會跑）")
    ap.add_argument("--tl-factor", type=float, default=1.0, help="時限倍率（預設 1.0）")
    ap.add_argument("--jobs", type=int, default=max(1, (os.cpu_count() or 2) // 2))
    ap.add_argument("--cxx", default=os.environ.get("CXX", "g++"))
    ap.add_argument("--std", default="c++17")
    a = ap.parse_args()

    root = Path(a.problem).resolve()
    cfg = json.loads((root / "polygon.json").read_text(encoding="utf-8"))
    if shutil.which(a.cxx) is None:
        sys.exit(f"找不到編譯器 {a.cxx}（請安裝 g++ 或用 --cxx 指定）")
    tl = cfg.get("timeLimit", 1000) / 1000 * a.tl_factor
    build = root / ".build"
    build.mkdir(exist_ok=True)
    (root / "tests").mkdir(exist_ok=True)
    inc = find_testlib(root)
    print(f"== {root.name}  TL={tl:.2f}s  checker={cfg.get('checker', 'std::wcmp.cpp')}")

    # 0. 題敘：statement.md → Polygon LaTeX（上傳時用同一套轉換），預覽寫到 .build/statement.tex
    print("\n[0] 題敘")
    try:
        sys.path.insert(0, str(HERE))
        import md2polygon
    except ImportError:
        warn("找不到 md2polygon.py（要和 local_check.py 放同一層），略過題敘檢查")
    else:
        if not (root / "statement.md").is_file():
            warn("沒有 statement.md，上傳時不會寫入題敘內容")
        else:
            fields, swarns = md2polygon.convert_problem(root, cfg)
            for w in swarns:
                warn(f"題敘：{w}")
            (build / "statement.tex").write_text(md2polygon.render_preview(fields), encoding="utf-8")
            print(f"  章節：{', '.join(k for k in md2polygon.FIELDS if k in fields)}；"
                  f"預覽 {build / 'statement.tex'}")

    # 1. 編譯 files/*.cpp 與 solutions/*.cpp
    print("\n[1] 編譯")
    bins = {}
    for src in sorted((root / "files").glob("*.cpp")):
        portability_lint(src)
        ok, msg = compile_one(src, build / (src.stem + EXE), inc, a)
        if not ok:
            sys.exit(f"{src.name} 編譯失敗：\n{msg}")
        bins[src.stem] = build / (src.stem + EXE)
    sol_cfg = cfg.get("solutions", {})
    mains = [f for f, t in sol_cfg.items() if t == "MA"]
    if len(mains) != 1:
        sys.exit(f"polygon.json 的 solutions 需要剛好一支 MA，目前 {mains}")
    main_sol = mains[0]
    for f in sorted((root / "solutions").iterdir()):
        if f.is_file() and f.name not in sol_cfg:
            warn(f"solutions/{f.name} 沒列在 polygon.json，不會上傳")
    only = set(x.strip() for x in a.only.split(",")) if a.only else None
    sols = {}
    for fn, tag in sol_cfg.items():
        if only and fn not in only and fn != main_sol:
            continue
        src = root / "solutions" / fn
        if not src.is_file():
            err(f"polygon.json 列了 solutions/{fn} 但檔案不存在")
            continue
        if src.suffix != ".cpp":
            warn(f"{fn} 不是 C++，本機略過（Polygon 上仍會跑）")
            continue
        out = build / ("sol_" + src.stem + EXE)
        ok, msg = compile_one(src, out, inc, a)
        if not ok:
            if fn == main_sol:
                sys.exit(f"{fn} 編譯失敗：\n{msg}")
            err(f"{fn} 編譯失敗：{msg.strip().splitlines()[0] if msg.strip() else ''}")
            continue
        sols[fn] = (tag, out)
    print(f"  generator/validator/checker: {', '.join(bins)}；解答 {len(sols)} 支")

    samples = parse_range(cfg.get("samples", ""))
    groups = cfg.get("groups", [])
    group_of = {i: str(g["group"]) for g in groups for i in parse_range(g["tests"])}

    # 2. 產生測資
    print("\n[2] 產生測資")
    script_tests = {}
    script_file = root / "script.txt"
    if script_file.is_file():
        text = re.sub(r"<#--.*?-->", "", script_file.read_text(encoding="utf-8"), flags=re.S)
        next_idx = max(samples, default=0) + 1
        for ln, line in enumerate(text.splitlines(), 1):
            line = line.strip()
            if not line:
                continue
            if "<#" in line or "${" in line:
                err(f"script.txt 第 {ln} 行有 Freemarker 語法；本機不支援，且會讓 Polygon 禁止固定編號")
                continue
            m = re.fullmatch(r"(.+?)\s*>\s*(\$|\d+)", line)
            if not m:
                err(f"script.txt 第 {ln} 行格式不對（要 `gen 參數 > 編號`）：{line}")
                continue
            parts = shlex.split(m.group(1))
            idx = next_idx if m.group(2) == "$" else int(m.group(2))
            next_idx = max(next_idx, idx + 1)
            if idx in samples:
                err(f"script.txt 產生 test {idx}，但它是手動範例")
            if idx in script_tests:
                err(f"script.txt 重複產生 test {idx}")
            if parts[0] not in bins:
                err(f"script.txt 第 {ln} 行：files/ 沒有 generator {parts[0]}.cpp")
                continue
            script_tests[idx] = parts
    else:
        warn("沒有 script.txt")

    if not a.no_gen:
        for idx, parts in sorted(script_tests.items()):
            dst = root / "tests" / f"{idx:02d}"
            rc, sec, msg = run(bins[parts[0]], parts[1:], stdout_path=dst, timeout=60)
            # Windows 上 generator 的 stdout 是文字模式，會寫出 CRLF；Polygon（Linux）產生的是 LF
            data = dst.read_bytes()
            if b"\r\n" in data:
                dst.write_bytes(data.replace(b"\r\n", b"\n"))
            if rc != 0:
                err(f"test {idx}：generator 失敗（{'逾時' if rc is None else 'exit ' + str(rc)}）{msg.strip()[:200]}")
        print(f"  產生 {len(script_tests)} 筆")

    all_tests = sorted(set(samples) | set(script_tests))
    if not a.no_gen:
        for i in samples:
            if not test_path(root, i).is_file():
                err(f"範例 test {i} 不存在（tests/{i:02d}）")
    if a.no_gen:
        all_tests = sorted(set(all_tests) | {int(p.name) for p in (root / "tests").iterdir() if p.name.isdigit()})
    if all_tests and all_tests != list(range(1, all_tests[-1] + 1)):
        missing = sorted(set(range(1, all_tests[-1] + 1)) - set(all_tests))
        err(f"測資編號不連續，缺 {missing[:10]}")
    if groups:
        no_group = [i for i in all_tests if i not in group_of]
        if no_group:
            err(f"這些測資沒有被任何 group 涵蓋：{no_group[:10]}")
        extra = sorted(set(group_of) - set(all_tests))
        if extra:
            err(f"polygon.json 的 groups 指到不存在的測資：{extra[:10]}")
    seen = {}
    for i in all_tests:
        p = test_path(root, i)
        if p.is_file():
            h = hashlib.md5(p.read_bytes()).hexdigest()
            if h in seen:
                warn(f"test {i} 與 test {seen[h]} 內容完全相同")
            seen.setdefault(h, i)

    # 3. validator
    print("\n[3] validator")
    val = bins.get(Path(cfg.get("validator", "val.cpp")).stem)
    hits = {}  # var -> [min_hit, max_hit]
    if val is None:
        warn("沒有 validator，略過")
    else:
        with tempfile.TemporaryDirectory() as td:
            for i in all_tests:
                p = test_path(root, i)
                if not p.is_file():
                    continue
                log = Path(td) / f"{i}.log"
                args = ["--testOverviewLogFileName", str(log)]
                if i in group_of:
                    args += ["--group", group_of[i]]
                rc, _, msg = run(val, args, stdin_path=p, timeout=60)
                if rc != 0:
                    err(f"test {i}（group {group_of.get(i, '-')}）不合法：{msg.strip()[:300]}")
                if log.is_file():
                    for line in log.read_text(errors="replace").splitlines():
                        mm = re.match(r'"(.+)":(.*)$', line)
                        if mm:
                            h = hits.setdefault(mm.group(1), [False, False])
                            h[0] |= "min-value-hit" in mm.group(2)
                            h[1] |= "max-value-hit" in mm.group(2)
        for var, (lo, hi) in sorted(hits.items()):
            if not (lo and hi):
                which = "/".join(x for x, b in (("最小值", lo), ("最大值", hi)) if not b)
                warn(f"變數 {var} 的{which}沒有被任何測資打到（Polygon 也會警告）")
        if not hits:
            warn("validator 沒有回報任何變數：readInt 等函式記得加上變數名稱")
        print(f"  {len(all_tests)} 筆檢查完畢，追蹤 {len(hits)} 個變數")

    # 4. 產生答案
    print("\n[4] 產生答案（main = %s）" % main_sol)
    checker = make_checker(cfg, root, bins, a)
    tag, main_exe = sols[main_sol]
    main_time = 0.0
    for i in all_tests:
        p = test_path(root, i)
        if not p.is_file():
            continue
        ans = Path(str(p) + ".a")
        old = ans.read_bytes() if (i in samples and ans.is_file()) else None
        rc, sec, msg = run(main_exe, stdin_path=p, stdout_path=ans, timeout=max(tl * 3, tl + 2))
        main_time = max(main_time, sec)
        if rc != 0:
            err(f"main 在 test {i} {'逾時' if rc is None else 'RE (exit %s)' % rc}")
        elif sec > tl:
            err(f"main 在 test {i} 用了 {sec:.2f}s，超過時限")
        elif sec > tl * 0.5:
            warn(f"main 在 test {i} 用了 {sec:.2f}s，超過時限一半")
        if old is not None:
            with tempfile.NamedTemporaryFile(delete=False) as f:
                f.write(old)
            ok, why = checker(p, ans, f.name)
            os.unlink(f.name)
            if not ok:
                err(f"main 在範例 {i} 的輸出和題本答案不同：{why}")
    print(f"  main 最慢 {main_time:.2f}s")

    # 5. 其他解答
    print("\n[5] 解答")
    order = [g["group"] for g in groups] if groups else ["all"]

    def judge(fn, exe, i):
        p = test_path(root, i)
        out = build / f"out_{Path(fn).stem}_{i}"
        rc, sec, _ = run(exe, stdin_path=p, stdout_path=out, timeout=max(tl * 2, tl + 1))
        if rc is None or sec > tl:
            v = "TL"
        elif rc != 0:
            v = "RE"
        else:
            v = "OK" if checker(p, out, str(p) + ".a")[0] else "WA"
        out.unlink(missing_ok=True)
        return i, v, sec

    width = max(len(x) for x in sols)
    for fn, (tag, exe) in sols.items():
        if fn == main_sol:
            continue
        tests = [i for i in all_tests if test_path(root, i).is_file()]
        with cf.ThreadPoolExecutor(a.jobs) as ex:
            res = list(ex.map(lambda i: judge(fn, exe, i), tests))
        verdicts = {i: v for i, v, _ in res}
        kinds = set(verdicts.values())
        bad = kinds - {"OK"}
        expect = {
            "OK": not bad,
            "WA": "WA" in kinds and not (kinds - {"OK", "WA"}),
            "PE": "WA" in kinds,
            "TL": "TL" in kinds and not (kinds - {"OK", "TL"}),
            "TO": not (kinds - {"OK", "TL"}),
            "TM": not (kinds - {"OK", "TL"}),
            "RE": "RE" in kinds,
            "RJ": bool(bad),
            "ML": True,
        }.get(tag, True)
        cols = []
        for g in order:
            idxs = [i for i in tests if (group_of.get(i) == str(g)) or g == "all"]
            fails = [verdicts[i] for i in idxs if verdicts[i] != "OK"]
            cols.append(f"g{g}:{len(fails)}bad" + (f"({','.join(sorted(set(fails)))})" if fails else ""))
        mark = "ok " if expect else "BAD"
        print(f"  {mark} {fn:<{width}} [{tag}] " + "  ".join(cols))
        if not expect:
            if tag in ("WA", "TL", "RJ", "RE", "PE") and not bad:
                err(f"{fn}（{tag}）通過了全部測資：測資沒擋下它，請加針對性的測資")
            else:
                err(f"{fn}（{tag}）的結果 {sorted(kinds)} 不符合 tag")

    print(f"\n== {root.name}：{len(errors)} 個錯誤、{len(warnings)} 個警告")
    sys.exit(1 if errors else 0)


if __name__ == "__main__":
    main()
