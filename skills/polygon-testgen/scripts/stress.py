#!/usr/bin/env python3
"""
隨機對拍：用 generator 產生大量小測資，比較兩支解答（預設 main 對 --sol）。

用法：
    python stress.py pA --gen "gen -K -1 -P -1 -N 8 -type rand" --sol brute.cpp
    python stress.py pA --gen "gen -n 6 -type rand" --sol brute.cpp --ref main.cpp --count 1000

--gen 是 script.txt 一行裡 `>` 前面、不含 seed 的部分；seed 會依序附上 1, 2, 3…
找到不一致時，把輸入存到 <題目>/.build/stress_fail.txt 並印出兩邊的輸出。
--ref 是當作標準答案的解答（預設 polygon.json 中標 MA 的那支）。
"""
import argparse, json, os, shlex, shutil, sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import local_check as lc  # noqa: E402


def main():
    if not sys.stdout.isatty():
        sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser(description="隨機對拍")
    ap.add_argument("problem")
    ap.add_argument("--gen", required=True, help='例如 "gen -n 8 -type rand"（不含 seed）')
    ap.add_argument("--sol", required=True, help="要檢查的解答檔名（solutions/ 底下）")
    ap.add_argument("--ref", help="標準解答（預設為 MA）")
    ap.add_argument("--count", type=int, default=300)
    ap.add_argument("--seed-start", type=int, default=1)
    ap.add_argument("--no-validate", action="store_true", help="不對每筆輸入跑 validator")
    ap.add_argument("--cxx", default=os.environ.get("CXX", "g++"))
    ap.add_argument("--std", default="c++17")
    a = ap.parse_args()

    root = Path(a.problem).resolve()
    cfg = json.loads((root / "polygon.json").read_text(encoding="utf-8"))
    if shutil.which(a.cxx) is None:
        sys.exit(f"找不到編譯器 {a.cxx}")
    ref = a.ref or next(f for f, t in cfg["solutions"].items() if t == "MA")
    build = root / ".build"
    build.mkdir(exist_ok=True)
    inc = lc.find_testlib(root)

    def comp(src, name):
        out = build / (name + lc.EXE)
        ok, msg = lc.compile_one(src, out, inc, a)
        if not ok:
            sys.exit(f"{src.name} 編譯失敗：\n{msg}")
        return out

    bins = {s.stem: comp(s, s.stem) for s in sorted((root / "files").glob("*.cpp"))}
    gen_parts = shlex.split(a.gen)
    if gen_parts[0] not in bins:
        sys.exit(f"files/ 沒有 {gen_parts[0]}.cpp")
    ref_exe = comp(root / "solutions" / ref, "sol_" + Path(ref).stem)
    sol_exe = comp(root / "solutions" / a.sol, "sol_" + Path(a.sol).stem)
    val = bins.get(Path(cfg.get("validator", "val.cpp")).stem)
    checker = lc.make_checker(cfg, root, bins, a)

    inp, out_ref, out_sol = build / "stress_in.txt", build / "stress_ref.txt", build / "stress_sol.txt"
    for k in range(a.seed_start, a.seed_start + a.count):
        rc, _, msg = lc.run(bins[gen_parts[0]], gen_parts[1:] + [str(k)], stdout_path=inp, timeout=30)
        if rc != 0:
            sys.exit(f"seed {k}：generator 失敗 {msg.strip()[:300]}")
        data = inp.read_bytes().replace(b"\r\n", b"\n")
        inp.write_bytes(data)
        if val and not a.no_validate:
            rc, _, msg = lc.run(val, stdin_path=inp, timeout=30)
            if rc != 0:
                sys.exit(f"seed {k}：輸入不合法 {msg.strip()[:300]}")
        for exe, o in ((ref_exe, out_ref), (sol_exe, out_sol)):
            rc, _, _ = lc.run(exe, stdin_path=inp, stdout_path=o, timeout=10)
            if rc != 0:
                (build / "stress_fail.txt").write_bytes(data)
                sys.exit(f"seed {k}：{exe.stem} {'逾時' if rc is None else 'RE'}，輸入存在 .build/stress_fail.txt")
        ok, why = checker(inp, out_sol, out_ref)
        if not ok:
            (build / "stress_fail.txt").write_bytes(data)
            print(f"seed {k} 不一致：{why}")
            print("--- 輸入（前 20 行）"); print("\n".join(data.decode(errors="replace").splitlines()[:20]))
            print(f"--- {ref}"); print(out_ref.read_text(errors="replace")[:500])
            print(f"--- {a.sol}"); print(out_sol.read_text(errors="replace")[:500])
            print(f"\n重現：{a.gen} {k}")
            sys.exit(1)
        if (k - a.seed_start + 1) % 100 == 0:
            print(f"  {k - a.seed_start + 1} 筆一致")
    print(f"{a.count} 筆全部一致（{ref} vs {a.sol}）")


if __name__ == "__main__":
    main()
