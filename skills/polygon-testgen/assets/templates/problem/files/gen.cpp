// pA 最大區間和 — generator
// Usage: gen -n <n> -type <type> [-lo L] [-hi H] [-ext 0|1] <seed>
// types（每種型態對應要測的邊界或要殺的錯解）：
//   rand    a_i uniform in [lo, hi]
//   allneg  all a_i in [lo, -1]                  → kills wa_allow_empty（答案為負）
//   big     a_i near +1e9 / -1e9, mostly positive → kills wa_int_overflow（總和超過 2^31）
//   wave    long positive runs separated by deep negative dips（最佳區間要跨過負數）
// -ext 1: 強制放入 lo 與 hi 各一次，讓 validator 統計的上下界被打到
#include "testlib.h"
#include <bits/stdc++.h>
using namespace std;

int main(int argc, char* argv[]) {
    registerGen(argc, argv, 1);
    int n = opt<int>("n");
    string type = opt<string>("type", "rand");
    long long lo = opt<long long>("lo", -1000000000LL);
    long long hi = opt<long long>("hi", 1000000000LL);
    bool ext = opt<int>("ext", 0) != 0;
    ensure(1 <= n && n <= 200000);
    ensure(-1000000000LL <= lo && lo <= hi && hi <= 1000000000LL);

    vector<long long> a(n);
    if (type == "rand") {
        for (auto& x : a) x = rnd.next(lo, hi);
    } else if (type == "allneg") {
        ensure(lo <= -1);
        for (auto& x : a) x = rnd.next(lo, -1LL);
    } else if (type == "big") {
        for (auto& x : a) x = rnd.next(10) ? rnd.next(hi - 1000, hi) : rnd.next(lo, lo + 1000);
    } else if (type == "wave") {
        for (int i = 0; i < n; i++) a[i] = (i % 50 == 49) ? rnd.next(lo, lo / 2) : rnd.next(0LL, hi);
    } else {
        ensuref(false, "unknown type %s", type.c_str());
    }
    if (ext && n >= 2) {
        a[rnd.next(n)] = lo;
        a[rnd.next(n)] = hi;
    }

    printf("%d\n", n);
    for (int i = 0; i < n; i++) printf("%lld%c", a[i], i + 1 == n ? '\n' : ' ');
}
