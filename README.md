# polygon-testgen

一個 [Claude](https://claude.ai) skill：把程式競賽題本（PDF 或 Markdown）變成可以直接上傳 [Codeforces Polygon](https://polygon.codeforces.com/) 的完整題目包。

給它一份題本，它會為每一題產生：

- `statement.md`：整理好的題敘（Legend / Input / Output / Scoring / Notes）
- `files/gen.cpp`、`files/val.cpp`：testlib generator 與 validator（含子題限制檢查）
- `script.txt`：Polygon test script
- `solutions/`：正解、暴力解，以及數支「真實參賽者會犯的錯」的錯誤解
- `polygon.json`：時限、checker、子題群組、配分、dependencies、解答 tag
- `README.md`：Polygon 設定說明與本機驗證結果

重點是**測資夠強**：每支錯誤解都要在本機被測資擋下，validator 的每個上下界都要被打到，才算完成。

## 安裝

### Claude Code（plugin）

```
/plugin marketplace add Xi-Plus/polygon-testgen-skill
/plugin install polygon-testgen@polygon-testgen
```

### Claude Code（手動）

把 `skills/polygon-testgen/` 複製到 `~/.claude/skills/polygon-testgen/`（全域）或專案的 `.claude/skills/polygon-testgen/`。

### Claude.ai / Claude Desktop

把 `skills/polygon-testgen/` 資料夾壓成 zip，在 Settings → Capabilities → Skills 上傳。（claude.ai 的執行環境通常沒有 g++ 與網路，只能產生檔案，本機驗證與上傳要自己在電腦上跑。）

## 使用

在放題本的資料夾裡開 Claude Code，直接說：

> 幫我把 `北市賽題本.pdf` 的六題做成 Polygon 題目，每題一個資料夾

> 這是我們校內賽 pC 的題敘（statement.md），幫我出測資、寫 validator，要能擋掉 O(N²) 的解

> 上傳 pA 到 Polygon

## 需求

| 用途 | 需求 |
|---|---|
| 本機驗證（`local_check.py`、`stress.py`） | Python 3.8+、`g++`（支援 C++17） |
| 上傳（`upload_to_polygon.py`） | `pip install requests`、Polygon API key |

Windows 可用 MinGW / TDM-GCC / MSYS2 的 g++。腳本已處理 Windows 的 CRLF、stack 大小與中文編碼問題。

### Polygon API key

Polygon 右上角 **Settings → API Keys** 建立，然後在比賽資料夾放一個 `.env`：

```
key=xxxxxxxx
secret=xxxxxxxx
```

`.env` 要加進 `.gitignore`，不要 commit。

## 內附腳本

都在 `skills/polygon-testgen/scripts/`，只依賴 Python 標準函式庫（上傳需要 `requests`）。也可以不透過 Claude 直接使用。

```bash
# 編譯 → 依 script.txt 產生測資 → validator（含 group 與上下界統計）→ 產生答案 → 跑所有解答並對照 tag
python local_check.py pA

# 隨機對拍：main vs brute
python stress.py pA --gen "gen -n 8 -type rand" --sol brute.cpp --count 500

# 上傳（第一次會建立題目並把 id 寫回 polygon.json）
python upload_to_polygon.py pA --dry-run
python upload_to_polygon.py pA
python upload_to_polygon.py pA --title-only       # 只更新題名
python upload_to_polygon.py pA --statement-only   # 只更新題敘

# 預覽題敘轉成的 LaTeX（Polygon 題敘不支援 Markdown，上傳時用同一套轉換）
python md2polygon.py pA            # 寫到 pA/.build/statement.tex
```

`local_check.py` 的輸出長這樣，一眼就能看出每支錯解在哪個子題被擋下：

```
[5] 解答
  ok  brute.cpp           [RJ] g0:0bad  g1:0bad  g2:4bad(TL)  g3:8bad(TL)
  ok  wa_int_overflow.cpp [WA] g0:0bad  g1:2bad(WA)  g2:3bad(WA)  g3:5bad(WA)
  ok  wa_allow_empty.cpp  [WA] g0:1bad(WA)  g1:2bad(WA)  g2:0bad  g3:3bad(WA)
```

## 結構

```
.claude-plugin/               plugin 與 marketplace 設定
skills/polygon-testgen/
├── SKILL.md                  主要流程
├── scripts/                  local_check.py、stress.py、upload_to_polygon.py、md2polygon.py
├── references/
│   ├── polygon-json.md       polygon.json 欄位、子題、tag、checker
│   ├── testlib-guide.md      generator / validator / checker 寫法
│   └── pitfalls.md           實際踩過的坑
├── assets/
│   ├── testlib.h
│   └── templates/
│       ├── problem/          一題完整的範例（可直接跑 local_check）
│       └── contest/          .gitignore、.gitattributes、.env.example
└── evals/                    skill 的測試案例
```

## 限制

- 目前只支援標準輸入輸出題（非互動題）。
- 題敘只支援 Markdown 子集（段落、粗斜體、程式碼、數學、清單、表格、小標題）轉 LaTeX；圖片要另外上傳到 Polygon 的 statement resources。上傳後仍建議在 Polygon 預覽一次排版。
- 本機的時間判定只是估計；最終以 Polygon 的 Invocations 為準。

## 授權

MIT。`assets/testlib.h` 來自 [testlib](https://github.com/MikeMirzayanov/testlib)，依其原始授權聲明再散布。
