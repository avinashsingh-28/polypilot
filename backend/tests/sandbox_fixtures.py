"""Shared C++ sources for sandbox/engine tests: 'sum of n integers' problem."""

VALIDATOR = r'''
#include "testlib.h"
int main(int argc, char* argv[]) {
    registerValidation(argc, argv);
    int n = inf.readInt(1, 10, "n"); inf.readEoln();
    for (int i = 0; i < n; i++) { inf.readInt(-100, 100, "a_i"); if (i + 1 < n) inf.readSpace(); }
    inf.readEoln(); inf.readEof();
}
'''

GENERATOR = r'''
#include "testlib.h"
#include <iostream>
int main(int argc, char* argv[]) {
    registerGen(argc, argv, 1);
    std::string t = argv[1];
    int n = t == "edge" ? 10 : rnd.next(1, 10);
    std::cout << n << "\n";
    for (int i = 0; i < n; i++) std::cout << (t == "edge" ? 100 : rnd.next(-100, 100)) << (i + 1 < n ? " " : "\n");
}
'''

REFERENCE = r'''
#include <bits/stdc++.h>
int main(){ int n; std::cin >> n; long long s = 0; for (int i = 0; i < n; i++) { long long x; std::cin >> x; s += x; } std::cout << s << "\n"; }
'''

BRUTE = r'''
#include <bits/stdc++.h>
int main(){ int n; std::cin >> n; std::vector<long long> a(n); for (auto& x : a) std::cin >> x; long long s = 0; for (int i = 0; i < n; i++) for (int j = 0; j <= i; j++) if (i == j) s += a[i]; std::cout << s << "\n"; }
'''

# Wrong whenever the input contains a negative number.
BUGGY = r'''
#include <bits/stdc++.h>
int main(){ int n; std::cin >> n; long long s = 0; for (int i = 0; i < n; i++) { long long x; std::cin >> x; s += x < 0 ? -x : x; } std::cout << s << "\n"; }
'''

SLOW = r'''
#include <bits/stdc++.h>
int main(){ int n; std::cin >> n; volatile unsigned long long z = 0; for (;;) z++; }
'''

CHECKER = r'''
#include "testlib.h"
int main(int argc, char* argv[]) {
    registerTestlibCmd(argc, argv);
    long long a = ans.readLong(), o = ouf.readLong();
    if (a != o) quitf(_wa, "expected %lld, found %lld", a, o);
    quitf(_ok, "sum %lld", a);
}
'''
