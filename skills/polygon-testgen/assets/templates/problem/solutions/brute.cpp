// 暴力：枚舉所有區間，O(N^2)。小測資正確，大測資 TLE。Tag: Rejected
#include <bits/stdc++.h>
using namespace std;
int main() {
    int n;
    scanf("%d", &n);
    vector<long long> a(n);
    for (auto& x : a) scanf("%lld", &x);
    long long best = LLONG_MIN;
    for (int l = 0; l < n; l++) {
        long long s = 0;
        for (int r = l; r < n; r++) s += a[r], best = max(best, s);
    }
    printf("%lld\n", best);
}
