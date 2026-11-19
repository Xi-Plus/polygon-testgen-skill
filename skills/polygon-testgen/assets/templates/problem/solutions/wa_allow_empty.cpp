// 錯誤：允許空區間（答案至少 0）。全部為負時答錯，範例 2 就會擋下。Tag: Wrong answer
#include <bits/stdc++.h>
using namespace std;
int main() {
    int n;
    scanf("%d", &n);
    long long best = 0, cur = 0;
    for (int i = 0; i < n; i++) {
        long long x;
        scanf("%lld", &x);
        cur = max(0LL, cur + x);
        best = max(best, cur);
    }
    printf("%lld\n", best);
}
