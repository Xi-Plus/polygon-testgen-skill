// 正解：Kadane，O(N)。Tag: Main correct
#include <bits/stdc++.h>
using namespace std;
int main() {
    int n;
    scanf("%d", &n);
    long long best = LLONG_MIN, cur = 0;
    for (int i = 0; i < n; i++) {
        long long x;
        scanf("%lld", &x);
        cur = max(cur + x, x);
        best = max(best, cur);
    }
    printf("%lld\n", best);
}
