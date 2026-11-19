# testlib：generator、validator、checker

testlib 官方：https://github.com/MikeMirzayanov/testlib（`assets/testlib.h` 是 0.9.x 版）。

## 目錄

1. Generator
2. 測資設計：怎麼讓錯解被擋下
3. Validator
4. 自訂 checker
5. 常見結構的產生方式

---

## 1. Generator

```cpp
// <題名> — generator
// Usage: gen -n <n> -type <type> [-maxv V] <seed>
// types:
//   rand     a_i uniform in [1, maxv]
//   same     all equal (kills solutions that assume distinct values)
//   desc     strictly decreasing (worst case for naive scan)
//   anti     counterexample for greedy "take the largest first"
#include "testlib.h"
#include <bits/stdc++.h>
using namespace std;

int main(int argc, char* argv[]) {
    registerGen(argc, argv, 1);
    int n = opt<int>("n");
    string type = opt<string>("type", "rand");
    long long maxv = opt<long long>("maxv", 1000000000LL);
    ensure(1 <= n && n <= 200000);
    ensure(1 <= maxv && maxv <= 1000000000LL);

    vector<long long> a(n);
    if (type == "rand") {
        for (auto& x : a) x = rnd.next(1LL, maxv);
    } else if (type == "same") {
        long long v = rnd.next(1LL, maxv);
        for (auto& x : a) x = v;
    } else if (type == "desc") {
        // 相異遞減：需要 maxv >= n
        ensure(maxv >= n);
        set<long long> s;
        while ((int)s.size() < n) s.insert(rnd.next(1LL, maxv));
        a.assign(s.rbegin(), s.rend());
    } else {
        ensuref(false, "unknown type %s", type.c_str());
    }

    printf("%d\n", n);
    for (int i = 0; i < n; i++) printf("%lld%c", a[i], i + 1 == n ? '\n' : ' ');
}
```

要點：

- `registerGen(argc, argv, 1)`；所有隨機都用 `rnd`：`rnd.next(lo, hi)`（閉區間）、`rnd.next(n)`（[0, n)）、`rnd.wnext(n, t)`（偏大/偏小分布）、`rnd.next("[a-z]{5,10}")`、`shuffle(v.begin(), v.end())`、`rnd.perm(n, 1)`（1..n 的排列）。
- 具名參數：`opt<int>("n")`（必填）、`opt<int>("n", 5)`（預設值）、`has_opt("x")`。命令列寫 `-n 5` 或 `-n=5`。
- **seed**：testlib 用整個命令列當亂數種子，所以最後放一個數字就能讓同參數的行產生不同測資。
- 輸出格式和題目要求完全一致：空白分隔、行尾 `\n`、不要多餘空白。
- 輸出大量資料用 `printf`，不要 `cout << endl`。
- 不要讀檔、不要用時間當種子、不要用 `rand()`／`mt19937`。

### 「打到上下界」

Polygon（與 local_check）會統計 validator 每個具名變數是否碰到下界與上界。generator 至少要有：

- 每個規模變數（N、M、Q…）的最小值與最大值各一筆。
- 每個數值（a_i、權重…）的最小值與最大值都出現過。隨機 `rnd.next(1, 1e9)` 幾乎不會剛好產生 1e9，要有型態或參數**強制放入**極值（例如 `-big 1` 時把最大的那個換成上限）。
- 實際不可能達到的邊界（受其他限制）不要靠 generator 硬湊，而是把 validator 的界限改成實際界限。

## 2. 測資設計：怎麼讓錯解被擋下

每個子題的測資清單，大致依這個順序思考：

1. **最小情況**：N = 1、N = 2、空集合、答案為 0／-1／無解。
2. **特殊結構**：全部相同、嚴格遞增／遞減、只有兩種值、全部相異、極端大的值（溢位）。
3. **針對每支錯解的反例**：從錯解反推。貪心錯 → 構造局部最佳不是全域最佳的型態；忘記排序 → 輸入打亂；少一種轉移 → 一定要用到那種轉移才能最佳；溢位 → 答案超過 2^31。
4. **隨機**：中等與最大規模各幾筆，不同參數（值域大/小）。
5. **最大規模**：最後一個子題至少 3～5 筆 N 最大，且包含讓 TLE 解最慢的結構（例如鏈狀樹、全部同值讓 hash 碰撞、大量重複查詢）。

先在小規模用 `stress.py` 找到能殺錯解的參數，再放大放進 script.txt。

每個子題的測資要符合該子題限制（validator 用 group 檢查），而且**也要能擋下該子題範圍內的錯解**：只會子題 1 的部分解不應該拿到子題 2 的分數。

## 3. Validator

```cpp
#include "testlib.h"
#include <bits/stdc++.h>
using namespace std;

int main(int argc, char* argv[]) {
    registerValidation(argc, argv);

    int n = inf.readInt(1, 200000, "n");
    inf.readEoln();
    vector<long long> a = inf.readLongs(n, 1, 1000000000LL, "a_i");  // 自動處理中間空白
    inf.readEoln();
    inf.readEof();

    string g = validator.group();
    if (g == "1") {
        ensuref(n <= 10, "subtask 1 requires n <= 10");
    } else if (g == "2") {
        ensuref(set<long long>(a.begin(), a.end()).size() == a.size(), "subtask 2 requires distinct a_i");
    }
    // group "0"（範例）與最後一組：只有全域限制
}
```

要點：

- 讀法：`readInt/readLong/readDouble(lo, hi, "name")`、`readInts(n, lo, hi, "name")`、`readToken("[a-z]{1,100}", "s")`、`readLine()`、`readSpace()`、`readEoln()`、`readEof()`。
- 變數名稱讓 Polygon 能統計上下界；同一種變數在迴圈裡用同一個名稱（`"a_i"`），不要 `format("a[%d]", i)`，否則會變成上千個變數。
- 圖論題檢查：點編號範圍、無自環／重邊（若題目要求）、連通（union-find）、是否為樹（邊數 n−1 且連通）。
- 「保證有解」「保證答案不超過 X」這類保證也要檢查（必要時在 validator 裡算答案）。
- 不要用 `__int128`、不要依賴 64 位元 `long` 寬度；乘法可能溢位時用飽和運算：

```cpp
// a, b <= 2^31，乘積 <= 2^62 不會溢位；累加到 CAP 就停
long long s = 0;
for (int k = 0; k < n && s < CAP; k++) s += A[i][k] * B[k][j];
C[i][j] = min(s, CAP);
```

## 4. 自訂 checker

答案不唯一（輸出任一組解、構造題）時才需要。

```cpp
#include "testlib.h"
using namespace std;

// 讀選手或標準輸出的解並驗證，回傳其目標值；不合法時用 stream.quitf 給對應的 verdict
long long readAndCheck(InStream& s, int n /* 加入需要的輸入資料 */) {
    long long k = s.readLong(0, n, "k");
    // ... 檢查解是否合法，不合法：s.quitf(_wa, "reason");
    return k;
}

int main(int argc, char* argv[]) {
    registerTestlibCmd(argc, argv);
    int n = inf.readInt();
    long long jury = readAndCheck(ans, n);
    long long part = readAndCheck(ouf, n);
    if (part > jury) quitf(_fail, "participant found better answer: %lld > %lld", part, jury);
    if (part < jury) quitf(_wa, "not optimal: %lld < %lld", part, jury);
    quitf(_ok, "k = %lld", part);
}
```

- `inf` 輸入、`ouf` 選手輸出、`ans` 標準答案。選手比標準答案好時用 `_fail`（代表題目或正解有問題）。
- polygon.json 的 `checker` 填 `checker.cpp`，檔案放 `files/`。local_check 會用 `checker <in> <out> <ans>` 呼叫它，結束碼 0 視為 AC。

## 5. 常見結構的產生方式

```cpp
// 隨機樹（parent 形式），再打亂編號
vector<int> p(n + 1);
for (int i = 2; i <= n; i++) p[i] = rnd.next(1, i - 1);
// 鏈：p[i] = i - 1；菊花：p[i] = 1；
// 偏深的樹：p[i] = rnd.wnext(1, i - 1, 5) 之類（t > 0 偏向大值）
vector<int> perm = rnd.perm(n, 1);  // 重新編號：真正的點 = perm[i-1]

// 無重邊的隨機連通圖：先生成樹，再加不重複的邊（set<pair<int,int>> 去重）

// 相異整數：set 收集，或在 [1, V] 取樣後 shuffle
// 字串：rnd.next("[a-c]{%d}", n) 小字母集較容易產生重複與回文
```
