# 實際踩過的坑

這些都是真實把一整套題本搬上 Polygon 時遇到的問題。上傳前讀一次，寫 generator / validator 時就避開。

## Polygon 端

**validator 用了 `__int128` 編譯失敗**
`error: expected unqualified-id before '__int128'`。Polygon 可能用 32 位元 g++ 編譯 validator／generator／checker。改用 `long long` 加飽和運算（見 testlib-guide.md 第 3 節），或改用不需要大數的檢查方法。local_check 會對 `files/` 裡的程式掃描 `__int128`。解答（solutions/）可以用 64 位元編譯器，比較不受影響，但 validator 一定要可移植。

**`saveScript` 失敗：`When using Freemarker it is only allowed to use $ as a test index.`**
script 裡只要出現 `<#-- -->` 等 Freemarker 語法，Polygon 就要求所有測資用 `> $`。上傳腳本會先把 `<#-- -->` 註解移除再送出，所以本機可以保留註解。不要用 `<#list>` 之類的迴圈；需要大量相似測資就直接展開成多行。

**`HTTP 429 Too Many Requests`**
一題可能要送上百個 API 請求（每筆範例、每個群組…）。上傳腳本遇到 429／5xx 會等待 5, 10, 20… 秒後重新簽章重試。輪詢 package 狀態也會觸發 429（實測同時輪詢 6 題時出現過），腳本每 20 秒查一次、題目之間間隔 1 秒。

**匯入 Codeforces 後題目名稱是空白**
Polygon 的題目 `name`（內部名稱）不是題名；題名是 statement 的 `name` 欄位。在 polygon.json 設 `title`，上傳時會寫入 statement；已上傳的題目用 `--only title,package` 補（改完要重建 package）。

**題敘裡的 Markdown 原樣顯示星號、表格變成一行**
Polygon 題敘只吃 LaTeX，不支援 Markdown。上傳腳本會用 `md2polygon.py` 轉換 statement.md；直接在 Polygon 網頁貼 Markdown 就會出現這個問題。轉換器不認得的語法（HTML、註腳）會被移除或原樣當文字，`local_check` 的 `[0] 題敘` 會警告。數學模式外的 `%` 在 LaTeX 是註解（後面整行消失），轉換器會自動跳脫；直接在 Polygon 改題敘時要自己寫 `\%`。

**題敘在 Polygon 被覆蓋**
上傳時 statement.md 是唯一來源：沒寫的章節會送空字串，在 Polygon 網頁上手動改過的題敘會被蓋掉。要在網頁上改，就同步改回 statement.md，或之後用 `--skip statement` 上傳（仍會寫題名）。

**中文題敘 PDF 編譯失敗：`LaTeX Error: Unicode character 接 (U+63A5) not set up for use with LaTeX`**
Polygon 用 pdfLaTeX 編 PDF，不支援中文字，題敘放在 `english` 欄位也一樣。HTML 題敘顯示正常，Full package 也照樣建得成功（實測 7 題都 READY），Codeforces Gym/Mashup 用的是 HTML。需要可印的 PDF 時，用原始題本或在本機用 XeLaTeX 另外產生。注意 LaTeX 在第一個中文字就停止，所以後面的表格、數學式錯誤不會被回報，要在 Statements 頁預覽 HTML 確認。

**建 package 很慢**
Full package（含 verification）一題約 1.5～4 分鐘，解答多或有 TLE 解時更久。腳本會先把所有題目的 build 送出再一起輪詢。內容沒變的 commit 不會增加 revision，原本的 package 仍然有效。

**`Could not download problem descriptor`（加進 Gym/Mashup 時）**
1. Polygon 題目要把 `codeforces` 使用者加為 read 權限：polygon.json 寫 `"access": {"codeforces": "READ"}` 後跑 `upload_to_polygon.py --all --only access`（或網頁 Manage access）。需要直接的 WRITE/OWNER 權限，透過群組取得的權限不行；每人每分鐘最多 60 次實際變更。
2. 題目要有已建好的 package（`upload_to_polygon.py --only package`，或 Package → Create package，Full），且是在最新 commit 之後建立的。
3. Mashup 只能用 Polygon 題目 ID 一題一題加；整個 Polygon contest 一次加入需要 contest uid，且 `codeforces` 要是 contest 的 manager。

**validator 警告「N 的最小值沒有被測到」但其實不可能測到**
例如 `1 ≤ N ≤ 100`、`1 ≤ M ≤ 2N(N−1)`：N = 1 時 M 沒有合法值，所以 N 的實際下界是 2。把 validator 改成 `readInt(2, 100, "N")` 並註解原因。題本寫法不必改，但 README 註明。

**最大值沒被測到**
隨機 `rnd.next(1, 999999999)` 幾乎不會剛好產生上限。generator 要有一個參數（例如 `-big 1`）把某個值強制換成上限，並在最大子題用上。

## 本機（Windows）端

**本機 validator 說 `Expected EOLN`，但測資看起來沒問題**
testlib 在 Windows 的 strict 模式預設要求 CRLF。local_check 在 Windows 會加 `-DFOR_LINUX` 讓它和 Polygon（Linux）一樣要求 LF。手動編譯 validator 時也要加。

**generator 在 Windows 產生 CRLF**
Windows 的 stdout 是文字模式，`printf("\n")` 會變成 `\r\n`。local_check 產生測資後會轉回 LF。範例檔（tests/01…）要確保是 LF，git 設定 `core.autocrlf=true` 時可以加 `.gitattributes`：`p*/tests/* text eol=lf`。

**遞迴解在本機 RE**
Windows 預設 stack 1 MB。local_check 編譯時加 `-Wl,--stack=268435456`。Polygon 上 stack 通常等於記憶體限制。

**中文輸出亂碼**
Windows 主控台或管線用 cp950。腳本在非 tty 輸出時改用 UTF-8；若仍亂碼，設 `PYTHONIOENCODING=utf-8`。

## 題本端

**範例錯誤**
曾遇過題本範例 2 的輸入誤印成和範例 1 相同。用正解跑範例對不上時，先懷疑自己，再懷疑題本；確定題本錯了，就反推最合理的更正版本（例如「只取前 5 本書」剛好得到題本的答案），在 statement.md 的 Notes 與 README 寫清楚，並在最後回報時告訴使用者。

**子題配分總和不是 100**
照題本保留，附上建議的 100 分配法，讓使用者決定。

**子題限制寫得含糊**
例如「N < K」到底有沒有包含 K 的其他限制。用最保守的解讀寫 validator，並在 README 註明。
