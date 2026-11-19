// pA 最大區間和 — validator
// 子題限制以 validator.group() 檢查（Polygon 要開 Enable groups）
#include "testlib.h"
#include <bits/stdc++.h>
using namespace std;

int main(int argc, char* argv[]) {
    registerValidation(argc, argv);

    int n = inf.readInt(1, 200000, "n");
    inf.readEoln();
    vector<long long> a = inf.readLongs(n, -1000000000LL, 1000000000LL, "a_i");
    inf.readEoln();
    inf.readEof();

    string g = validator.group();
    if (g == "1") {
        ensuref(n <= 100, "subtask 1 requires n <= 100");
    } else if (g == "2") {
        for (long long x : a) ensuref(x >= 0, "subtask 2 requires a_i >= 0");
    }
    // group "0"（範例）與 "3"：沒有額外限制
}
