---
name: polygon-testgen
description: 從程式競賽題本（PDF 或 Markdown）建立 Codeforces Polygon 格式的完整題目包：題敘、testlib generator／validator、test script、子題群組配分、正解／暴力解／錯誤解，並在本機驗證測資強度後透過 Polygon API 上傳。只要使用者提到「出測資」、「產生測資」、「把題本搬到 Polygon」、「做成 Codeforces Gym / Mashup」、「寫 generator / validator」、「testlib」、「子題配分」、「讓錯解被擋下」，或丟了一份競賽題本 PDF／Markdown（TOI、北市賽、APCS、校內賽、ICPC 等）要做成可評測的題目，就使用這個 skill，即使沒有明說 Polygon。Also use for "make test data / testcases for this problem set", "port contest PDF to Polygon", "write testlib generator and validator".
---

# Polygon 測資產生

把一份題本變成「可以直接上傳 Polygon、測資夠強、子題設定正確」的題目資料夾。

成品的價值在於**測資能擋下錯誤解**、而且**上傳後不用再修**。所以這個流程的重點不是把檔案寫出來，而是：寫正解與錯解 → 設計專門殺錯解的測資 → 在本機跑過一輪證明它們真的被殺掉 → 才上傳。

## 產出的資料夾結構

每題一個資料夾（預設 `pA/`, `pB/`…，若使用者已有命名慣例就沿用）：

```
<contest>/
├── upload_to_polygon.py      ┐
├── local_check.py            │ 從 scripts/ 複製，四支放同一層
├── stress.py                 ├ （stress.py import local_check.py；
├── md2polygon.py             ┘   upload / local_check import md2polygon.py）
├── .env.example              ┐
├── .gitignore                ├ 從 assets/templates/contest/ 複製（.env 一定要在 .gitignore 裡）
├── .gitattributes            ┘
└── pA/
    ├── polygon.json          題目設定，格式見 references/polygon-json.md
    ├── statement.md          題敘（Legend / Input format / Output format / Scoring / Notes）
    ├── README.md             這題的 Polygon 設定說明 + 本機驗證結果
    ├── script.txt            test script（由 Polygon 用 generator 產生測資）
    ├── files/
    │   ├── testlib.h         從 assets/testlib.h 複製
    │   ├── gen.cpp           generator
    │   └── val.cpp           validator（用 validator.group() 檢查子題限制）
    ├── solutions/
    │   ├── main.cpp          正解（Main correct, MA）
    │   ├── brute.cpp         暴力解（Rejected, RJ：小測資正確，大測資超時或錯）
    │   └── wa_*.cpp / tle_*.cpp   錯誤解，每支代表一種真實會犯的錯
    └── tests/
        ├── 01, 01.a, 02, 02.a     範例（從題本抄，手動上傳並勾選 use in statements）
        └── 03…                    local_check.py 在本機產生，不進 git
```

`assets/templates/problem/` 是一題完整、已通過 local_check 的範例題（最大區間和），每個檔案都可以複製後改寫；先看一遍它就知道每個檔案該長什麼樣子。使用者若已有自己的資料夾或慣例，沿用他們的。

## 工作流程

用 TodoList 逐題追蹤。題目之間互相獨立；題數多時可以每題派一個 subagent 平行做，但每個 subagent 都要讀這份 SKILL.md 和相關 references。

### 1. 讀題本、寫 statement.md

- PDF 用 Read 工具讀（大檔分頁讀），或 `pdftotext -layout`。數學式、表格、範例輸入輸出逐字核對：PDF 轉文字常會把上下標、`≤`、空白和換行弄亂。
- 每題抓出：輸入格式、**每個變數的上下界**、子題（分數 + 額外限制）、範例輸入／輸出、時間與記憶體限制（題本沒寫就問使用者，或預設 1 秒 / 256 MB 並在 README 註明）。
- 寫 `statement.md`，章節用 `## Legend` / `## Input format` / `## Output format` / `## Scoring` / `## Notes`，數學用 `$...$`。這些章節對應 Polygon 題敘的欄位；Polygon 題敘只吃 LaTeX，上傳時 `md2polygon.py` 會轉換，所以只用它支援的 Markdown 子集：段落、`**粗體**`、`*斜體*`、`` `程式碼` ``、`$...$` / `$$...$$`、清單、表格、`### 小標題`。不要寫 HTML、註腳或 LaTeX 套件指令；範例輸入輸出**不要**寫進題敘（Polygon 用勾選 use in statements 的測資自動排版），範例說明放 Notes。
- Markdown 的單一換行會被併成同一段；題本上分開的兩行（例如「第一行…」「第二行…」）要空一行分段。
- `local_check.py` 的 `[0] 題敘` 會轉換一次、列出警告（不認得的章節、HTML、Scoring 分數和 polygon.json 不一致…），並把結果寫到 `.build/statement.tex` 供檢查。
- **題本有錯不要默默修**：範例算不出來、子題配分總和不是 100、限制互相矛盾（例如 N = 1 時 M 沒有合法值）都是常見狀況。在 `## Notes` 與 README 寫清楚原文是什麼、你怎麼處理、理由，最後在回報裡提醒使用者。

### 2. 寫解答（先於測資）

先有解答才知道測資要殺什麼。

- `main.cpp`：正解。要能證明正確，或至少和暴力解大量對拍過。注意溢位（答案上界算一下要不要 `long long`）。
- `brute.cpp`：直接照題意窮舉的暴力，越笨越好，用來驗證 main。標 `RJ`，因為它在大測資一定會 TLE。
- 錯誤解 3～6 支：想像真實參賽者會怎麼寫錯，每支只犯**一種**錯，檔名說明錯在哪（`wa_greedy_top.cpp`、`wa_int_overflow.cpp`、`wa_no_sort.cpp`、`tle_naive_n2.cpp`）。檔頭註解寫「錯在哪、預期哪個子題擋下」。常見來源：
  - 看似對的貪心、少考慮一種轉移、邊界（N = 1、全部相同、答案為 0 / -1）
  - `int` 溢位、取模忘記、浮點誤差
  - 正確但複雜度太差（`tle_*`，標 `TL`）—— 用來確認最大測資真的夠大
  - 只會做某個子題的部分解（標 `RJ` 或依情況 `WA`）

### 3. 寫 validator（`files/val.cpp`）

Validator 是測資的守門員，Polygon 會用它檢查每一筆測資，也會統計每個變數的上下界有沒有被測到。

- 嚴格檢查格式：`readInt(lo, hi, "name")` → `readSpace()` / `readEoln()` → 最後 `readEof()`。**每個 read 都給變數名稱**，Polygon 才能回報「N 的最大值沒被測到」。
- 上下界寫題目**實際能達到的**範圍。如果其他限制讓某個邊界不可能出現（例如 `1 ≤ M ≤ 2N(N−1)` 且 `M ≥ 1` 使 N 實際下界是 2），validator 就寫實際下界並加註解，不然 Polygon 會一直警告「未達最小值」。
- 子題限制用 `validator.group()` 判斷（群組名稱是字串 `"1"`, `"2"`…）；範例所在的 group 0 只檢查全域限制。
- 圖、樹、排列、相異性等結構性限制也要檢查（連通、無重邊、是否為樹…），不只是數字範圍。
- 只用標準 C++，**不要用 `__int128`**：Polygon 可能用 32 位元 g++ 編譯 validator／generator，會編譯失敗。需要大數比較就改用飽和運算或 `long double` 仔細處理。

### 4. 寫 generator（`files/gen.cpp`）

一支 generator 用參數控制所有測資型態，讓 `script.txt` 一行一筆測資。

- `registerGen(argc, argv, 1)`，參數用 `opt<int>("n")` 這種具名參數，最後一個位置參數放 seed（讓同參數的不同行產生不同測資，也讓 Polygon 能區分）。
- 只用 `rnd`（`rnd.next`, `shuffle`），不要用 `rand()` / `std::mt19937` / `random_shuffle`，否則不同編譯器產生的測資不同。
- 用 `-type` 參數切換型態，**每種型態對應一個要殺的錯解或要測的邊界**，在檔頭註解列出。典型型態：`rand`、全部相同、極端值、遞增/遞減、針對貪心的反例構造、最大規模（殺 TLE）、答案為特殊值（0、-1、無解）。
- 確保每個變數的**上界與下界都至少被一筆測資打到**（例如最大值 1e9−1 而不是隨機值剛好沒到）。這也是 local_check 會檢查的項目。
- 用 `ensure(...)` 檢查參數合法，寫錯參數時直接失敗而不是默默產生壞測資。

細節與範例程式見 `references/testlib-guide.md`。

### 5. 寫 script.txt 與 polygon.json

- `script.txt` 每行 `gen <參數> <seed> > <編號>`，用**固定編號**。範例（1～s）不寫在 script 裡，手動上傳。
- 可以用 `<#-- 註解 -->` 分段標註子題，上傳腳本會先把註解拿掉。（原因：script 裡只要出現 Freemarker 語法，Polygon 就只允許 `> $`，固定編號會被拒絕。）
- 同一子題的測資編號連續，方便 `polygon.json` 用 `"3-8"` 這種範圍指定群組。
- 每個子題 5～15 筆左右；最後一個子題（無額外限制）要有多筆最大規模測資。
- `polygon.json` 的完整欄位說明在 `references/polygon-json.md`。重點：`name` 是 Polygon 內部名稱（小寫英數與 `-`），`title` 是題目顯示名稱（不設的話匯入 Codeforces 後題名會是空白），`access` 預設 `{"codeforces": "READ"}`；group 0 是範例，配分 0、`EACH_TEST`；有包含關係的子題要設 `dependencies`。

### 6. 本機驗證（不可省略）

```bash
python local_check.py pA            # 編譯、產生測資、validate、產生答案、跑所有解答
python local_check.py pA --no-gen   # 只重跑解答
```

`local_check.py` 需要本機有 `g++`。它會做的事和預期結果：

| 檢查 | 要達到 |
|---|---|
| script.txt 每行都產得出測資，編號連續、無重複內容 | 無錯誤 |
| 每筆測資通過 validator（帶入該筆的 group） | 全部通過 |
| 每個變數的最小值、最大值都被某筆測資打到 | 沒有 `never hit` 警告，或在 README 解釋為何不可能 |
| main 在範例上的輸出 = 題本範例答案 | 一致 |
| 每支解答的結果符合它的 tag | 全部 `ok` |

Tag 的意思：`MA`/`OK` 全部 AC；`WA` 至少一筆 WA；`TL` 至少一筆 TLE；`RJ` 至少一筆非 AC；`TO` 只能 AC 或 TLE。

如果某支錯解沒被擋下，回到第 4 步加針對它的測資型態，**不要改錯解讓它變得更錯**。如果 brute 和 main 在小測資不一致，先查清楚誰錯。

額外的隨機對拍（建議每題都做，尤其是 main 不好證明時）：

```bash
python stress.py pA --gen "gen -K -1 -P -1 -N 8 -type rand" --sol brute.cpp --count 500
```

### 7. 寫 README.md

每題的 README 給要在 Polygon 上手動檢查的人看：檔案對應到 Polygon 的哪裡、時間記憶體限制、群組配分表、各解答的 tag 與預期結果、本機驗證結果（從 local_check 輸出摘要：哪支錯解在哪些子題被擋下幾筆）、題本更正說明。範本在 `assets/templates/problem/README.md`。

### 8. 上傳到 Polygon（使用者要求時才做）

上傳是對外的動作，先確認使用者要上傳、而且已經有 API key。

```bash
python upload_to_polygon.py --all --dry-run          # 先看會送哪些請求
python upload_to_polygon.py pA pB                    # 指定題目；預設做全部項目並建 package
python upload_to_polygon.py --all                    # 所有含 polygon.json 的 p*/
python upload_to_polygon.py pC --only statement,package
python upload_to_polygon.py --all --skip package
```

- 項目：`info`（時限、記憶體）、`title`（只寫題名）、`statement`（題敘內容＋題名）、`validator`（files/＋validator＋checker）、`solution`、`test`（files/＋範例＋script＋群組配分）、`access`（依 polygon.json 的 `access` 設定使用者權限）、`package`（Full package＋verification）。`--only` / `--skip` 用逗號分隔，不指定就是全部。
- polygon.json 沒有 `id` 時會建立題目並把 id 寫回，且一定會做 `info`。
- 每題上傳完 commit 一次；所有題目 commit 完才一起建 package 並輪詢（一題約 2～4 分鐘）。某題失敗不會中止其他題，最後印總表，有失敗時結束碼為 1。
- key/secret 放在 `.env`（`key=...`、`secret=...`），Polygon 右上角 Settings → API Keys 產生。**絕對不要把 .env commit 或印出來**。
- 腳本已處理 429/5xx 重試、Freemarker 註解、群組與配分、範例標記。
- 題敘會從 statement.md 轉成 LaTeX 上傳到 polygon.json 的 `statementLangs`（預設 `english`），上傳後腳本會請 Polygon 編譯題敘並回報錯誤。中文題敘的 PDF 一定會編譯失敗（見 pitfalls），不影響 HTML 題敘與 package。
- 建 package 時 Polygon 會用 verification 跑全部解答並比對 tag，READY 就代表 Invocations 結果符合 tag。只改了部分內容時，記得連同 `package` 一起做（或之後 `--only package`），Codeforces 只認最新 commit 之後建的 package。
- 上傳後提醒使用者：Statements 頁預覽 HTML 確認排版；Tests 頁 Preview 確認產生與 validator。
- 要在 Codeforces Gym/Mashup 使用時，Polygon 題目要給 `codeforces` 使用者 read 權限：polygon.json 放 `"access": {"codeforces": "READ"}`（範本已預設），上傳時 `access` 項目會自動設定。給權限等於把題目分享出去，使用者不打算放 Gym 時就把這個欄位拿掉。

## 回報

完成後告訴使用者：每題的子題配分、測資數、每支錯解被哪些子題擋下、題本中發現並處理的問題、還需要人工做的步驟；有上傳時附上每題的 Polygon id 與 package 狀態。發現的題本錯誤要放在最前面，因為那是使用者最需要做決定的地方。

## 參考檔

- `references/polygon-json.md` —— polygon.json 欄位、群組／配分／dependencies、解答 tag 對照
- `references/testlib-guide.md` —— generator、validator、checker 的寫法與範例
- `references/pitfalls.md` —— 實際踩過的坑（Polygon 編譯器、Freemarker、題名空白、429…），上傳前讀一次
