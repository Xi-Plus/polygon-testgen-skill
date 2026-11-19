// 錯誤：總和用 int，超過 2^31 時溢位。預期在子題 2、3 的 big 測資被擋下。Tag: Wrong answer
#include <bits/stdc++.h>
using namespace std;
int main() {
    int n;
    scanf("%d", &n);
    int best = INT_MIN, cur = 0;
    for (int i = 0; i < n; i++) {
        int x;
        scanf("%d", &x);
        cur = max(cur + x, x);
        best = max(best, cur);
    }
    printf("%d\n", best);
}
