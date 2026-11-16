"""
PolyPilot's built-in standard checker.

Polygon requires a checker before a package can be built. When a problem has no custom checker
artifact, PolyPilot uploads this testlib checker as `checker.cpp` and sets it as the problem's
checker (documented API: problem.saveFile + problem.setChecker).

It applies exactly the rule PolyPilot uses for local verification (TokenComparator without float
tolerance): outputs are split into whitespace-separated tokens and every token must match exactly;
the amount and kind of whitespace is ignored. Its behaviour is covered by the sandbox test suite
(tests/test_sandbox.py::test_builtin_checker_*), which is what "verified" refers to.
"""

BUILTIN_CHECKER_NAME = "checker.cpp"

BUILTIN_CHECKER_SOURCE = r'''// PolyPilot built-in checker: exact comparison of whitespace-separated tokens.
#include "testlib.h"
#include <string>

int main(int argc, char* argv[]) {
    registerTestlibCmd(argc, argv);
    int n = 0;
    while (!ans.seekEof() && !ouf.seekEof()) {
        n++;
        std::string expected = ans.readWord();
        std::string found = ouf.readWord();
        if (expected != found)
            quitf(_wa, "%d%s tokens differ - expected: '%s', found: '%s'", n, englishEnding(n).c_str(),
                  compress(expected).c_str(), compress(found).c_str());
    }
    if (!ans.seekEof())
        quitf(_wa, "Answer contains more tokens than the output (output has %d)", n);
    if (!ouf.seekEof())
        quitf(_wa, "Output contains more tokens than the answer (answer has %d)", n);
    quitf(_ok, "%d token(s) match", n);
}
'''
