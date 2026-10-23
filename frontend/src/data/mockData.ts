import { Problem } from '../types/problem';

export const DEMO_PROBLEM: Problem = {
  id: 'poly-101',
  title: 'Subsegment XOR Partition',
  slug: 'subsegment-xor-partition',
  shortIdea: 'Given an array of n integers and a threshold k, count the number of valid partitions where each subsegment has an XOR sum strictly greater than k.',
  difficulty: 'Div. 2 C (1400-1600)',
  intendedAlgorithm: 'Trie + Dynamic Programming + Prefix XOR',
  constraints: '1 <= n <= 200,000, 0 <= a[i], k < 2^30. Sum of n over all test cases <= 200,000.',
  timeLimitMs: 2000,
  memoryLimitMb: 256,
  preferredLanguage: 'C++17',
  status: 'verified',
  createdAt: '2026-10-23T14:20:00Z',
  updatedAt: '2026-10-23T16:45:00Z',
  artifacts: {
    statement: {
      legend: `You are given an integer array $a$ of length $n$ and an integer $k$.\n\nA partition of array $a$ into $m$ ($1 \\le m \\le n$) contiguous subsegments is represented as $[l_1, r_1], [l_2, r_2], \\dots, [l_m, r_m]$ such that $l_1 = 1$, $r_m = n$, and $l_{i+1} = r_i + 1$ for all $1 \\le i < m$.\n\nA partition is called **valid** if for every subsegment $[l_i, r_i]$, the bitwise XOR sum of elements in that subsegment is strictly greater than $k$:\n$$\\bigoplus_{j=l_i}^{r_i} a_j > k$$\n\nFind the total number of valid partitions modulo $998\\,244\\,353$.`,
      inputFormat: `The first line contains a single integer $t$ ($1 \\le t \\le 10^4$) — the number of test cases.\n\nThe first line of each test case contains two integers $n$ and $k$ ($1 \\le n \\le 2 \\cdot 10^5$, $0 \\le k < 2^{30}$).\n\nThe second line of each test case contains $n$ integers $a_1, a_2, \\dots, a_n$ ($0 \\le a_i < 2^{30}$).\n\nIt is guaranteed that the sum of $n$ over all test cases does not exceed $2 \\cdot 10^5$.`,
      outputFormat: `For each test case, output a single integer — the number of valid partitions modulo $998\\,244\\,353$.`,
      samples: [
        {
          input: `2\n4 2\n3 1 4 2\n3 0\n1 2 3`,
          output: `2\n3`,
          explanation: `In the first test case, the array is [3, 1, 4, 2] and k = 2.\n- Partition [1, 1], [2, 3], [4, 4] gives XOR sums 3 > 2, 1 XOR 4 = 5 > 2, and 2 (not > 2, invalid).\n- The valid partitions are:\n  1. [1, 4] with XOR 3 ^ 1 ^ 4 ^ 2 = 4 > 2.\n  2. [1, 2], [3, 4] with XORs (3^1=2 no), [1, 3], [4, 4] -> valid partition gives 2.`
        }
      ],
      notes: `Modulo arithmetic must be handled carefully. Notice that prefix XOR allows rephrasing the condition as $P[r] \\oplus P[l-1] > k$.`
    },
    editorial: {
      approach: `Let $P[i] = a_1 \\oplus a_2 \\oplus \\dots \\oplus a_i$ be the prefix XOR array, with $P[0] = 0$.\n\nA subsegment $a[l \\dots r]$ has XOR sum $P[r] \\oplus P[l-1]$. Thus, the condition for a valid transition in dynamic programming is:\n$$dp[i] = \\sum_{j=0}^{i-1} [P[i] \\oplus P[j] > k] \\cdot dp[j]$$\nwith base case $dp[0] = 1$.\n\nSince $n \\le 2 \\cdot 10^5$, an $O(n^2)$ loop will TLE. We maintain a binary Trie over the values $P[j]$ storing the sum of $dp[j]$ in each subtree.\n\nTo query all $j$ where $P[i] \\oplus P[j] > k$, we traverse the Trie from the 29-th bit down to 0:\n1. If the current bit of $k$ is 0, then choosing the branch where $P[j]$'s bit differs from $P[i]$'s bit gives a XOR bit of 1, which is strictly greater than 0. We can immediately add all $dp$ values in that subtree to our answer, and then follow the branch where the XOR bit matches 0.\n2. If the current bit of $k$ is 1, any branch producing a 0 XOR bit is $< k$ and cannot satisfy $> k$. Hence we must follow the branch producing a 1 XOR bit.`,
      complexityTime: `O(n \\log(\\max A)) where \\log(\\max A) \\le 30. Total time <= 0.35s for n = 2 * 10^5.`,
      complexitySpace: `O(n \\log(\\max A)) for the trie nodes. Memory footprint <= 64 MB.`,
      proof: `The prefix XOR equivalence preserves contiguous partitions because any partition l_1, r_1, ..., l_m, r_m forms a chain P[0] -> P[r_1] -> ... -> P[n]. The trie query accurately accumulates DP weights in O(30) steps per prefix.`
    },
    solutions: [
      {
        id: 'sol-ref',
        filename: 'solution.cpp',
        tag: 'main',
        description: 'Optimal C++17 Trie + DP solution. Runs in O(30n).',
        language: 'cpp',
        code: `#include <bits/stdc++.h>
using namespace std;

static const int MOD = 998244353;
static const int BITS = 30;

struct TrieNode {
    int next[2];
    int sum;
    TrieNode() {
        next[0] = next[1] = -1;
        sum = 0;
    }
};

vector<TrieNode> trie;

void insert(int val, int weight) {
    int u = 0;
    trie[u].sum = (trie[u].sum + weight) % MOD;
    for (int b = BITS - 1; b >= 0; --b) {
        int bit = (val >> b) & 1;
        if (trie[u].next[bit] == -1) {
            trie[u].next[bit] = trie.size();
            trie.emplace_back();
        }
        u = trie[u].next[bit];
        trie[u].sum = (trie[u].sum + weight) % MOD;
    }
}

int query_greater(int val, int k) {
    int u = 0;
    int ans = 0;
    for (int b = BITS - 1; b >= 0; --b) {
        if (u == -1) break;
        int val_bit = (val >> b) & 1;
        int k_bit = (k >> b) & 1;
        if (k_bit == 0) {
            // Branch where XOR bit is 1 gives > k
            int diff_branch = trie[u].next[val_bit ^ 1];
            if (diff_branch != -1) {
                ans = (ans + trie[diff_branch].sum) % MOD;
            }
            u = trie[u].next[val_bit];
        } else {
            // Must follow branch where XOR bit is 1
            u = trie[u].next[val_bit ^ 1];
        }
    }
    return ans;
}

void solve() {
    int n, k;
    if (!(cin >> n >> k)) return;
    vector<int> a(n);
    for (int i = 0; i < n; ++i) cin >> a[i];

    trie.clear();
    trie.emplace_back();

    insert(0, 1);
    int pref = 0;
    int dp = 0;

    for (int i = 0; i < n; ++i) {
        pref ^= a[i];
        dp = query_greater(pref, k);
        insert(pref, dp);
    }

    cout << dp << "\\n";
}

int main() {
    ios::sync_with_stdio(false);
    cin.tie(nullptr);
    int t;
    if (cin >> t) {
        while (t--) solve();
    }
    return 0;
}`
      },
      {
        id: 'sol-brute',
        filename: 'slow.cpp',
        tag: 'accepted',
        description: 'O(N^2) Brute Force for differential testing on small inputs.',
        language: 'cpp',
        code: `#include <bits/stdc++.h>
using namespace std;

static const int MOD = 998244353;

void solve() {
    int n, k;
    if (!(cin >> n >> k)) return;
    vector<int> a(n);
    for (int i = 0; i < n; ++i) cin >> a[i];

    vector<int> pref(n + 1, 0);
    for (int i = 0; i < n; ++i) pref[i + 1] = pref[i] ^ a[i];

    vector<int> dp(n + 1, 0);
    dp[0] = 1;

    for (int i = 1; i <= n; ++i) {
        long long current = 0;
        for (int j = 0; j < i; ++j) {
            if ((pref[i] ^ pref[j]) > k) {
                current = (current + dp[j]) % MOD;
            }
        }
        dp[i] = current;
    }
    cout << dp[n] << "\\n";
}

int main() {
    ios::sync_with_stdio(false);
    cin.tie(nullptr);
    int t;
    if (cin >> t) {
        while (t--) solve();
    }
    return 0;
}`
      },
      {
        id: 'sol-wa',
        filename: 'wa_greedy.cpp',
        tag: 'wrong-answer',
        description: 'Flawed solution ignoring modulo or using >= instead of >.',
        language: 'cpp',
        code: `// Intentionally wrong: uses >= k instead of > k
#include <bits/stdc++.h>
using namespace std;

int main() {
    int t; cin >> t;
    while(t--) {
        int n, k; cin >> n >> k;
        vector<int> a(n);
        for(int &x : a) cin >> x;
        cout << 0 << "\\n";
    }
}`
      },
      {
        id: 'sol-tle',
        filename: 'tle_recursion.cpp',
        tag: 'time-limit-exceeded',
        description: 'Exponential naive recursion that reliably TLEs on N > 25.',
        language: 'cpp',
        code: `// Naive recursion O(2^N)
#include <iostream>
using namespace std;
int main() {
    cout << "TLE candidate" << endl;
}`
      }
    ],
    validator: {
      filename: 'validator.cpp',
      boundsNotes: 'Ensures sum of N <= 200,000, 0 <= a_i, k < 2^30, t in [1, 10000].',
      code: `#include "testlib.h"
#include <bits/stdc++.h>

using namespace std;

const int MAX_T = 10000;
const int MAX_SUM_N = 200000;
const int MAX_VAL = (1 << 30) - 1;

int main(int argc, char* argv[]) {
    registerValidation(argc, argv);

    int t = inf.readInt(1, MAX_T, "t");
    inf.readEoln();

    int sum_n = 0;
    for (int tc = 1; tc <= t; ++tc) {
        setTestCase(tc);
        int n = inf.readInt(1, MAX_SUM_N, "n");
        inf.readSpace();
        int k = inf.readInt(0, MAX_VAL, "k");
        inf.readEoln();

        sum_n += n;
        ensuref(sum_n <= MAX_SUM_N, "Sum of n exceeded 200,000");

        for (int i = 0; i < n; ++i) {
            inf.readInt(0, MAX_VAL, format("a[%d]", i + 1));
            if (i + 1 < n) inf.readSpace();
            else inf.readEoln();
        }
    }
    inf.readEof();
    return 0;
}`
    },
    checker: {
      filename: 'checker.cpp',
      type: 'standard',
      standardName: 'ncmp.cpp',
      code: `// Standard numeric checker: tests integers modulo 998244353
#include "testlib.h"

int main(int argc, char * argv[]) {
    setName("compare integers from user and answer");
    registerTestlibCmd(argc, argv);

    int testCase = 0;
    while (!ans.seekEof()) {
        testCase++;
        int expected = ans.readInt();
        int actual = ouf.readInt();
        if (expected != actual) {
            quitf(_wa, "Test %d: expected %d, found %d", testCase, expected, actual);
        }
    }
    quitf(_ok, "All answers match correctly");
}`
    },
    generators: [
      {
        filename: 'gen_random.cpp',
        code: `#include "testlib.h"
#include <iostream>

using namespace std;

int main(int argc, char* argv[]) {
    registerGen(argc, argv, 1);
    int t = opt<int>(1);
    int max_n = opt<int>(2);
    int max_val = opt<int>(3);

    cout << t << "\\n";
    for(int i = 0; i < t; ++i) {
        int n = rnd.next(1, max_n);
        int k = rnd.next(0, max_val);
        cout << n << " " << k << "\\n";
        for(int j = 0; j < n; ++j) {
            cout << rnd.next(0, max_val) << (j + 1 == n ? "" : " ");
        }
        cout << "\\n";
    }
    return 0;
}`,
        scriptCommands: [
          'gen_random 1 5 10 > $',
          'gen_random 5 20 100 > $',
          'gen_random 1 200000 1073741823 > $'
        ]
      }
    ],
    tests: [
      { id: 1, type: 'sample', inputPreview: '2\n4 2\n3 1 4 2\n3 0\n1 2 3', outputPreview: '2\n3', validated: true },
      { id: 2, type: 'manual', generatorCmd: 'manual: all zeros', inputPreview: '1\n5 0\n0 0 0 0 0', outputPreview: '0', validated: true },
      { id: 3, type: 'manual', generatorCmd: 'manual: k = 2^30 - 1', inputPreview: '1\n3 1073741823\n1 2 3', outputPreview: '0', validated: true },
      { id: 4, type: 'random', generatorCmd: 'gen_random 1 10 15', inputPreview: '1\n10 5\n1 9 4 12 7 3 15 2 8 6', outputPreview: '48', validated: true },
      { id: 5, type: 'adversarial', generatorCmd: 'gen_random 1 200000 1073741823', inputPreview: '1\n200000 500000\n[200000 elements...]', outputPreview: '492817302', validated: true }
    ]
  },
  verification: {
    status: 'passed',
    lastRunTimestamp: '2026-10-23T16:30:12Z',
    compilation: {
      referenceSolution: true,
      bruteForceSolution: true,
      validator: true,
      checker: true,
      generators: true
    },
    samplesPassed: 2,
    totalSamples: 2,
    stressTestsRun: 50,
    stressTestsPassed: 50,
    counterexamples: [],
    waCandidatesCaught: 1,
    totalWaCandidates: 1,
    tleCandidatesTimedOut: 1,
    totalTleCandidates: 1,
    executionMetrics: {
      maxTimeMs: 248,
      maxMemoryMb: 34.2
    }
  },
  polygon: {
    linked: true,
    problemId: '382941',
    problemUrl: 'https://polygon.codeforces.com/p/author/subsegment-xor-partition',
    latestRevision: 14,
    packageBuildStatus: 'ready',
    lastSyncTime: '2026-10-23T16:45:00Z',
    warnings: [],
    cautions: []
  }
};

export const INITIAL_AI_PROVIDERS = [
  {
    id: 'gemini' as const,
    name: 'Google Gemini',
    description: 'Fast, high-context reasoning powered by Gemini 2.5 Flash and Gemini 2.5 Pro.',
    models: [
      { id: 'gemini-2.5-flash', name: 'Gemini 2.5 Flash', contextWindow: '1M tokens', recommended: true },
      { id: 'gemini-2.5-pro', name: 'Gemini 2.5 Pro', contextWindow: '2M tokens', recommended: false }
    ],
    selectedModel: 'gemini-2.5-flash',
    apiKey: '',
    isConfigured: false,
    status: 'disconnected' as const
  },
  {
    id: 'openai' as const,
    name: 'OpenAI',
    description: 'General reasoning models including GPT-4o and o3-mini.',
    models: [
      { id: 'gpt-4o', name: 'GPT-4o', contextWindow: '128k tokens', recommended: true },
      { id: 'o3-mini', name: 'o3-mini (High Reasoning)', contextWindow: '200k tokens', recommended: false }
    ],
    selectedModel: 'gpt-4o',
    apiKey: '',
    isConfigured: false,
    status: 'disconnected' as const
  },
  {
    id: 'anthropic' as const,
    name: 'Anthropic Claude',
    description: 'Deep mathematical analysis and competitive programming generation.',
    models: [
      { id: 'claude-3-7-sonnet', name: 'Claude 3.7 Sonnet', contextWindow: '200k tokens', recommended: true }
    ],
    selectedModel: 'claude-3-7-sonnet',
    apiKey: '',
    isConfigured: false,
    status: 'disconnected' as const
  },
  {
    id: 'groq' as const,
    name: 'Groq (LPU)',
    description: 'Ultra-low latency open-weights inference (Llama 3.3 70B).',
    models: [
      { id: 'llama-3.3-70b-versatile', name: 'Llama 3.3 70B', contextWindow: '128k tokens', recommended: true }
    ],
    selectedModel: 'llama-3.3-70b-versatile',
    apiKey: '',
    isConfigured: false,
    status: 'disconnected' as const
  },
  {
    id: 'ollama' as const,
    name: 'Ollama / Local LLM',
    description: 'Self-hosted local models without cloud API charges.',
    models: [
      { id: 'qwen2.5-coder:32b', name: 'Qwen 2.5 Coder 32B', contextWindow: '32k tokens', recommended: true },
      { id: 'deepseek-r1:14b', name: 'DeepSeek R1 14B', contextWindow: '64k tokens', recommended: false }
    ],
    selectedModel: 'qwen2.5-coder:32b',
    apiKey: '',
    isConfigured: false,
    status: 'disconnected' as const,
    customEndpoint: 'http://localhost:11434'
  }
];
