# pA 最大區間和 — Codeforces Polygon 匯入說明

## 檔案

| 檔案 | Polygon 位置 | 說明 |
|---|---|---|
| `files/testlib.h` | Files → Resource files | 若 Polygon 已內建可略過 |
| `files/gen.cpp` | Files → Source files | generator，名稱 `gen` |
| `files/val.cpp` | Validator | 以 `validator.group()` 檢查子題限制 |
| checker | Checker | 內建 **`std::wcmp.cpp`** |
| `solutions/main.cpp` | Solutions | **Main correct**：Kadane O(N) |
| `solutions/brute.cpp` | Solutions | **Rejected**：O(N²)，大測資 TLE |
| `solutions/wa_int_overflow.cpp` | Solutions | **Wrong answer**：總和用 int |
| `solutions/wa_allow_empty.cpp` | Solutions | **Wrong answer**：允許空區間 |
| `script.txt` | Tests → Script | 產生 test 3–25 |
| `tests/01`, `tests/02` | Tests → 手動新增，勾 **Use in statements** | 範例 |
| `statement.md` | Statement | 題敘 |

## 設定

1. **General info**：Time limit 1 s，Memory limit 256 MB，stdin/stdout。
2. **Tests**：勾選 **Enable groups** 與 **Enable points**：

| Group | Tests | 分數 | Points policy | Dependencies |
|---|---|---|---|---|
| 0 | 1–2 | 0 | each test | — |
| 1 | 3–9 | 20 | complete group | — |
| 2 | 10–15 | 30 | complete group | — |
| 3 | 16–25 | 50 | complete group | 1, 2 |

3. **Invocations** 全部跑一次，預期結果見下節。
4. Package → Create package（Full）。

（以上都可以用 `python upload_to_polygon.py pA` 自動完成，包含題敘與 package；建 package 時的 verification 等同 Invocations。）

## 本機驗證結果（`python local_check.py pA`）

- 25 筆測資全數通過 validator（含各子題限制），n 與 a_i 的上下界都有測到。
- `main` 與 `brute` 在 300 組隨機小測資一致（`stress.py`）。
- 範例：test 1 → 4、test 2 → -2，與題本一致。
- 錯誤解被擋下的測資：

| 解答 | g0 | g1 | g2 | g3 |
|---|---|---|---|---|
| brute (RJ) | – | – | 4 TL | 8 TL |
| wa_int_overflow | – | 2 | 3 | 5 |
| wa_allow_empty | 1 | 2 | – | 3 |

## 題本更正

（沒有就寫「無」。有的話：原文、更正、理由。）
