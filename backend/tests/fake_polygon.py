"""
In-memory fake of the Polygon API for routine tests (no network, no real Polygon writes).

It independently re-implements the documented signature check (sorted params, SHA-512 of
"<rand>/<method>?<params>#<secret>") and the 5-minute time window, and simulates a small
subset of Polygon state: problems, working copy, files, solutions, statements, tests,
commits and packages. Failure injection: `fail[method] = mode` where mode is one of
  "timeout_after_apply"  — apply the change, then time out (ambiguous write)
  "timeout_before_apply" — time out without applying
  "429" / "500"          — HTTP error
  "FAILED:<comment>"     — Polygon JSON failure
"""
import base64
import hashlib
import json
import time
from urllib.parse import parse_qsl

import httpx

KEY, SECRET = "testkey1234", "testsecret5678"


def expected_sig(rand, method, pairs, secret=SECRET):
    s = f"{rand}/{method}?" + "&".join(f"{k}={v}" for k, v in sorted(pairs)) + f"#{secret}"
    return rand + hashlib.sha512(s.encode("utf-8")).hexdigest()


class FakePolygon:
    def __init__(self):
        self.problems = {}
        self.next_id = 1000
        self.calls = []          # (method, params dict)
        self.fail = {}
        self.secret = SECRET
        self.skew = 0

    # ── helpers ──
    def add_problem(self, name, owner="tester", access="OWNER"):
        pid = self.next_id
        self.next_id += 1
        self.problems[pid] = {"id": pid, "name": name, "owner": owner, "accessType": access, "deleted": False,
                              "favourite": False, "revision": 1, "workingCopyRevision": 1, "modified": False,
                              "info": {"inputFile": "stdin", "outputFile": "stdout", "interactive": False,
                                       "timeLimit": 2000, "memoryLimit": 256},
                              "files": {}, "solutions": {}, "statements": {}, "tests": {}, "validator": "",
                              "checker": "", "packages": [], "mtime": 1}
        return self.problems[pid]

    def summary(self, p):
        return {k: p[k] for k in ("id", "name", "owner", "accessType", "deleted", "favourite", "revision",
                                  "workingCopyRevision", "modified")}

    def _touch(self, p):
        p["modified"] = True
        p["mtime"] += 1
        return p["mtime"]

    def transport(self):
        return httpx.MockTransport(self.handle)

    def handle(self, request: httpx.Request) -> httpx.Response:
        method = request.url.path.rsplit("/", 1)[-1]
        assert request.method == "POST"
        assert request.url.host == "polygon.codeforces.com"
        pairs = parse_qsl(request.content.decode("utf-8"), keep_blank_values=True)
        params = {}
        for k, v in pairs:
            params.setdefault(k, v)
        self.calls.append((method, params))
        hdr = {"date": time.strftime("%a, %d %b %Y %H:%M:%S GMT", time.gmtime(time.time() + self.skew))}
        signed = [(k, v) for k, v in pairs if k != "apiSig"]
        if params.get("apiKey") != KEY:
            return self._json({"status": "FAILED", "comment": "apiKey: Incorrect API key"}, hdr)
        if abs(int(params["time"]) - (time.time() + self.skew)) > 300:
            return self._json({"status": "FAILED", "comment": "time: Too big difference between server and client time"}, hdr)
        sig = params.get("apiSig", "")
        if sig != expected_sig(sig[:6], method, signed, self.secret):
            return self._json({"status": "FAILED", "comment": "apiSig: Incorrect signature"}, hdr)
        mode = self.fail.pop(method, None)
        if mode == "429":
            return httpx.Response(429, headers=hdr, text="Too many requests")
        if mode == "500":
            return httpx.Response(500, headers=hdr, text="oops")
        if mode and mode.startswith("FAILED:"):
            return self._json({"status": "FAILED", "comment": mode[7:]}, hdr)
        if mode == "timeout_before_apply":
            raise httpx.ReadTimeout("timeout", request=request)
        try:
            result = getattr(self, "m_" + method.replace(".", "_"))(params)
        except KeyError as e:
            return self._json({"status": "FAILED", "comment": f"{e.args[0]}"}, hdr)
        if mode == "timeout_after_apply":
            raise httpx.ReadTimeout("timeout", request=request)
        if isinstance(result, bytes):
            return httpx.Response(200, headers={**hdr, "content-type": "application/octet-stream"}, content=result)
        body = {"status": "OK"} if result is None else {"status": "OK", "result": result}
        return self._json(body, hdr)

    @staticmethod
    def _json(body, hdr):
        return httpx.Response(200, headers={**hdr, "content-type": "application/json"}, content=json.dumps(body))

    def _p(self, params):
        try:
            p = self.problems[int(params["problemId"])]
        except (KeyError, ValueError):
            raise KeyError("problemId: Problem not found")
        if p["accessType"] == "NONE":
            raise KeyError("You have no access to this problem")
        return p

    # ── methods ──
    def m_problems_list(self, q):
        out = [self.summary(p) for p in self.problems.values()]
        if q.get("id"):
            out = [p for p in out if str(p["id"]) == q["id"]]
        if q.get("name"):
            out = [p for p in out if q["name"] in p["name"]]
        return out

    def m_problem_create(self, q):
        return self.summary(self.add_problem(q["name"]))

    def m_problem_info(self, q):
        return self._p(q)["info"]

    def m_problem_updateInfo(self, q):
        p = self._p(q)
        for k in ("inputFile", "outputFile"):
            if k in q:
                p["info"][k] = q[k]
        for k in ("timeLimit", "memoryLimit"):
            if k in q:
                p["info"][k] = int(q[k])
        self._touch(p)

    def m_problem_files(self, q):
        p = self._p(q)
        return {"resourceFiles": [], "auxFiles": [],
                "sourceFiles": [{"name": n, "modificationTimeSeconds": f["mtime"], "length": len(f["content"])}
                                for n, f in p["files"].items()]}

    def m_problem_viewFile(self, q):
        return self._p(q)["files"][q["name"]]["content"].encode()

    def m_problem_saveFile(self, q):
        p = self._p(q)
        if q.get("checkExisting") == "true" and q["name"] in p["files"]:
            raise KeyError("File already exists")
        p["files"][q["name"]] = {"content": q["file"].replace("\r\n", "\n"), "mtime": self._touch(p)}

    def m_problem_solutions(self, q):
        return [{"name": n, "modificationTimeSeconds": s["mtime"], "length": len(s["content"]), "sourceType": "cpp.g++17",
                 "tag": s["tag"]} for n, s in self._p(q)["solutions"].items()]

    def m_problem_viewSolution(self, q):
        return self._p(q)["solutions"][q["name"]]["content"].encode()

    def m_problem_saveSolution(self, q):
        p = self._p(q)
        if q.get("checkExisting") == "true" and q["name"] in p["solutions"]:
            raise KeyError("Solution already exists")
        p["solutions"][q["name"]] = {"content": q["file"], "tag": q.get("tag"), "mtime": self._touch(p)}

    def m_problem_validator(self, q):
        return self._p(q)["validator"]

    def m_problem_checker(self, q):
        return self._p(q)["checker"]

    def m_problem_setValidator(self, q):
        p = self._p(q)
        if q["validator"] not in p["files"]:
            raise KeyError("validator: file not found")
        p["validator"] = q["validator"]
        self._touch(p)

    def m_problem_setChecker(self, q):
        p = self._p(q)
        p["checker"] = q["checker"]
        self._touch(p)

    def m_problem_statements(self, q):
        return self._p(q)["statements"]

    def m_problem_saveStatement(self, q):
        p = self._p(q)
        if "\n" in q.get("name", ""):
            raise KeyError("name: must be single line")
        st = p["statements"].setdefault(q["lang"], {"encoding": "UTF-8", "name": "", "legend": "", "input": "",
                                                    "output": "", "notes": "", "tutorial": ""})
        for k in ("name", "legend", "input", "output", "notes", "tutorial", "encoding"):
            if k in q:
                st[k] = q[k]
        self._touch(p)

    def m_problem_tests(self, q):
        return [{"index": i, "manual": True, "input": t["input"],
                 "inputBase64": base64.b64encode(t["input"].encode()).decode(), "useInStatements": t["stmt"]}
                for i, t in sorted(self._p(q)["tests"].items())]

    def m_problem_testInput(self, q):
        return self._p(q)["tests"][int(q["testIndex"])]["input"].encode()

    def m_problem_saveTest(self, q):
        p = self._p(q)
        idx = int(q["testIndex"])
        if q.get("checkExisting") == "true" and idx in p["tests"]:
            raise KeyError("Test already exists")
        p["tests"][idx] = {"input": q["testInput"].replace("\r\n", "\n"),
                           "stmt": q.get("testUseInStatements") == "true"}
        self._touch(p)

    def m_problem_commitChanges(self, q):
        p = self._p(q)
        if not p["modified"]:
            return {"committed": False, "conflictOccurred": False, "message": "No changes"}
        p["revision"] += 1
        p["workingCopyRevision"] = p["revision"]
        p["modified"] = False
        return {"committed": True, "conflictOccurred": False, "message": q.get("message")}

    def m_problem_updateWorkingCopy(self, q):
        p = self._p(q)
        p["workingCopyRevision"] = p["revision"]

    def m_problem_cautions(self, q):
        p = self._p(q)
        issues = [] if p["checker"] else [{"type": "CHECKER_IS_NOT_SET", "message": "Checker is not set"}]
        return {"common": [], "statement": [], "structure": [], "issues": [], "packageReadinessIssues": issues,
                "ai": {"disabled": True, "statements": []}}

    def m_problem_buildPackage(self, q):
        p = self._p(q)
        p["packages"].append({"id": len(p["packages"]) + 1, "revision": p["revision"],
                              "creationTimeSeconds": int(time.time()), "state": "PENDING", "comment": "",
                              "type": "standard"})

    def m_problem_packages(self, q):
        return self._p(q)["packages"]
