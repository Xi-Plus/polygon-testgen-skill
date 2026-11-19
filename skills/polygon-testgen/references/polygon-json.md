# polygon.json 與題目資料夾格式

`upload_to_polygon.py`、`local_check.py`、`stress.py` 都讀這份設定。

## 完整範例

```json
{
  "id": 630399,
  "name": "toi114-taipei-pa-ebookstore",
  "title": "網路書店 (eBookstore)",
  "timeLimit": 1000,
  "memoryLimit": 512,
  "validator": "val.cpp",
  "checker": "std::wcmp.cpp",
  "samples": "1-2",
  "access": {"codeforces": "READ"},
  "groups": [
    {"group": "0", "tests": "1-2",   "points": 0,  "policy": "EACH_TEST"},
    {"group": "1", "tests": "3-8",   "points": 23},
    {"group": "2", "tests": "9-21",  "points": 39},
    {"group": "3", "tests": "22-33", "points": 38, "dependencies": "1,2"},
    {"group": "4", "tests": "34-47", "points": 15, "dependencies": "1,2,3"}
  ],
  "solutions": {
    "main.cpp": "MA",
    "brute.cpp": "RJ",
    "wa_greedy_top.cpp": "WA",
    "tle_naive.cpp": "TL"
  }
}
```

## 欄位

| 欄位 | 必填 | 說明 |
|---|---|---|
| `id` | 否 | Polygon 題目 ID。沒有的話第一次上傳會 `problem.create` 並自動寫回這裡。新題目**不要**自己編 id。 |
| `name` | 是 | Polygon 內部名稱，建立題目時用。只能小寫英數與 `-`，整個 Polygon 唯一，建議 `<比賽>-<年>-<題號>-<英文短名>`。 |
| `title` | 建議 | 題敘名稱（顯示給參賽者看的題名）。沒設的話題目匯入 Codeforces Gym/Mashup 後題名是空白。 |
| `statementLangs` | 否 | 題敘要寫入的 Polygon 語言（題名與 statement.md 轉成的內容），預設 `["english"]`。中文題目放在 `english` 欄位最保險；填帳號不支援的語言時 `saveStatement` 會失敗並顯示原因。 |
| `interactive` | 否 | 互動題設 `true` 時才會上傳 statement.md 的 Interaction 章節（目前其他流程仍只支援非互動題）。 |
| `timeLimit` | 是 | 毫秒。 |
| `memoryLimit` | 是 | MB。 |
| `validator` | 是 | `files/` 裡 validator 的檔名。 |
| `checker` | 是 | 內建用 `std::xxx.cpp`；自訂 checker 放 `files/checker.cpp` 並填 `checker.cpp`。 |
| `samples` | 是 | 範例測資編號範圍，例如 `"1-2"`、`"1-4"`。這些測資手動上傳並勾 use in statements。 |
| `groups` | 有子題時 | 見下節。沒有子題（ICPC 式）就省略，整題全有全無。 |
| `solutions` | 是 | `檔名 → tag`，剛好一支 `MA`。 |
| `access` | 否 | `login → READ / WRITE / NONE`，上傳的 `access` 項目會用 `problem.setAccess` 設定（立即生效、不需 commit、重複設定不會寄通知）。要用於 Codeforces Gym/Mashup 時放 `{"codeforces": "READ"}`；沒寫就不動任何權限。OWNER 不能用這個設定。 |

範圍字串格式：`"3-8"`、`"1,3,5-7"`。

## groups（子題）

- `group`：字串。validator 裡 `validator.group()` 拿到的就是這個字串。
- `tests`：這個子題的測資範圍。每筆測資只能屬於一個 group，所有測資都要被涵蓋。
- `points`：子題總分。上傳腳本會把分數放在該組第一筆測資，其他筆 0 分。
- `policy`：`COMPLETE_GROUP`（預設，全對才給分）或 `EACH_TEST`（每筆分開算）。範例的 group 0 用 `EACH_TEST`、0 分。
- `dependencies`：逗號分隔的 group 名稱。子題 3 的限制包含子題 1、2 時填 `"1,2"`，Polygon 會在前面子題沒過時不給這組分數。

**子題限制的包含關係決定測資放哪組**：「N ≤ 100」的子題 3 包含「K = 3, N ≤ 100」的子題 2，所以子題 2 的測資也滿足子題 3，但測資只放在一個 group，再用 dependencies 表達。

配分總和通常要 100。題本總和不是 100 時照題本保留，並在 statement.md 的 Notes 和 README 註明（附建議的 100 分配法），讓使用者決定。

## 解答 tag

| tag | 意思 | local_check 的判定 |
|---|---|---|
| `MA` | Main correct，用來產生答案 | 必須全部 AC，且不超過時限 |
| `OK` | 其他正確解 | 全部 AC |
| `WA` | 錯誤答案 | 至少一筆 WA，其他只能 AC |
| `TL` | 超時 | 至少一筆 TLE，其他只能 AC |
| `TO` | 可能超時（TL or OK） | 只能 AC 或 TLE |
| `ML` | 記憶體超限 | 本機不檢查 |
| `RE` | 執行錯誤 | 至少一筆 RE |
| `RJ` | Rejected，任何非 AC 皆可 | 至少一筆非 AC（暴力解用這個） |

## 內建 checker 選擇

| 輸出 | checker |
|---|---|
| 單一整數或整數序列（最常見） | `std::wcmp.cpp`（逐 token 比對，空白換行不敏感） |
| 每行需逐行一致 | `std::lcmp.cpp` |
| 浮點數，誤差 1e-6 | `std::rcmp6.cpp`（還有 rcmp4、rcmp9） |
| YES / NO 不分大小寫 | `std::yesno.cpp`（單一）或 `std::nyesno.cpp`（多個） |
| 答案不唯一（輸出任一組解） | 自寫 `files/checker.cpp`，見 testlib-guide.md |

## script.txt

```
<#-- Group 1: N < K -->
gen -K 3 -P 3 -N 1 -type rand 101 > 3
gen -K 4 -P 17 -N 3 -type rand 102 > 4
<#-- Group 2: K = 3, N <= 100 -->
gen -K 3 -P 30 -N 100 -type pairs 201 > 9
```

- 第一個字是 `files/` 裡 generator 的檔名（不含 `.cpp`）。可以有多支 generator（`gen_tree`, `gen_grid`）。
- 最後一個參數慣例上放 seed：同一組參數換 seed 就是不同測資。用「子題編號 × 100 + 序號」當 seed 好辨認。
- 編號用固定數字，從範例的下一號開始，連續不跳號。
- `<#-- -->` 註解只給人看；上傳腳本會先移除（Polygon 看到 Freemarker 語法就不允許固定編號）。不要用其他 Freemarker 語法（`<#list>`、`${}`）。

## tests/ 與 git

範例 `tests/01`、`tests/01.a`… 從題本逐字抄（注意結尾換行、LF），進 git。其餘測資由 Polygon 用 script 產生，本機產生的只是驗證用，建議 `.gitignore`：

```
p?/.build/
p?/tests/*
!p?/tests/01
!p?/tests/01.a
!p?/tests/02
!p?/tests/02.a
# 某題範例較多時個別加，例如 pD 有 4 筆範例：
!pD/tests/03
!pD/tests/03.a
!pD/tests/04
!pD/tests/04.a
```

不要用 `!p?/tests/0[1-9]` 這種萬用字元：會把本機產生的 03～09 也加進 git。
