"""One command: python scripts/check_all.py

Real database integration runs ONLY against owned disposable processes with data on V:.
Prints test counts separately from lint/typecheck/build/audit check results. Exits nonzero
for any failed/blocked check, including unresolved dependency audit findings.
"""
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import uuid
import xml.etree.ElementTree as ET

from disposable_databases import MongoServer, MysqlServer, v_directory

ROOT = Path(__file__).resolve().parents[1]
RUN = uuid.uuid4().hex[:12]
OUTPUT = ROOT / "work" / f"checks_{RUN}"
OUTPUT.mkdir(parents=True)
results = []
counts = {"passed": 0, "failed": 0, "skipped": 0}


def command(name, args, cwd=ROOT, env=None):
    print(f"RUN {name}: {' '.join(map(str, args))}", flush=True)
    proc = subprocess.run(args, cwd=cwd, env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                          encoding="utf-8", errors="replace")
    (OUTPUT / f"{name}.log").write_text(proc.stdout, encoding="utf-8")
    result = {"check": name, "status": "passed" if proc.returncode == 0 else "failed", "exit_code": proc.returncode}
    results.append(result)
    print(f"{name}: {result['status']} (exit {proc.returncode}); log {OUTPUT / (name + '.log')}", flush=True)
    if proc.returncode:
        if name != "dependency-audit":
            print(proc.stdout[-5000:], flush=True)
    return proc


def junit(path):
    totals = {"passed": 0, "failed": 0, "skipped": 0}
    for case in ET.parse(path).getroot().iter("testcase"):
        key = "failed" if case.find("failure") is not None or case.find("error") is not None else "skipped" if case.find("skipped") is not None else "passed"
        totals[key] += 1
    for key, value in totals.items():
        counts[key] += value
    return totals


def database_checks():
    # Missing V:, binaries or dependencies are BLOCKED, never converted to mock passes.
    directory = v_directory(Path("V:/Codex/medsub-checks") / RUN)
    mysql = MysqlServer(directory / "mysql")
    mongo = MongoServer(directory / "mongo")
    env = os.environ.copy()
    for line in (ROOT / ".env.example").read_text().splitlines():
        if line and not line.startswith("#") and "=" in line:
            key, value = line.split("=", 1)
            env[key] = value
    env.update(MYSQL_HOST="127.0.0.1", MYSQL_PORT=str(mysql.port), MYSQL_ROOT_USER="root", MYSQL_ROOT_PASSWORD="",
               MONGO_URI=mongo.uri, MONGO_TEST_URI=mongo.uri, MEDSUB_TEST_WORK=str(directory), SYNC_BACKGROUND="false",
               TEMP=str(directory), TMP=str(directory), PYTHONIOENCODING="utf-8")
    try:
        mysql.start()
        mongo.start()
        print(f"Real MySQL data: {mysql.data}; MongoDB data: {mongo.data}", flush=True)
        results.append({"check": "real-service-preflight", "status": "passed", "mysql_data": str(mysql.data), "mongo_data": str(mongo.data)})
        for label, marker, real in [("backend-real", "not stub_mongo", True), ("backend-stubs", "stub_mongo", False)]:
            per_run = env.copy()
            per_run["MEDSUB_TEST_RUN_ID"] = RUN + ("_real" if real else "_stubs")
            if not real:
                per_run.pop("MONGO_TEST_URI", None)
            report = OUTPUT / f"{label}.xml"
            proc = command(label, [sys.executable, "-m", "pytest", "tests", "-q", "-m", marker, f"--junitxml={report}"], env=per_run)
            if report.exists():
                results[-1]["tests"] = junit(report)
            else:
                results[-1]["status"] = "failed"
            excluded = re.search(r"(\d+) deselected", proc.stdout)
            results[-1]["excluded"] = int(excluded.group(1)) if excluded else 0
            results[-1]["exclusion_reason"] = "fault-injection stubs run separately" if real else "real integration tests ran in backend-real"
    finally:
        mongo.stop()
        mysql.stop()
        print("Stopped only this command's owned servers; retained V: logs/data folders for review.", flush=True)


def main():
    npm = shutil.which("npm.cmd" if os.name == "nt" else "npm")
    if not npm:
        results.append({"check": "frontend-prerequisites", "status": "blocked", "reason": "npm unavailable"})
    else:
        env = os.environ.copy()
        env.update(NEXT_TELEMETRY_DISABLED="1", PYTHONIOENCODING="utf-8")
        # Keep temporary compiler/cache files beside the run when V: exists.
        if Path("V:/").is_dir():
            temp = v_directory(Path("V:/Codex/medsub-checks") / RUN / "temp")
            env.update(TEMP=str(temp), TMP=str(temp), npm_config_cache=str(temp / "npm-cache"))
        for name in ["lint", "typecheck"]:
            command(name, [npm, "run", name], ROOT / "frontend", env)
        command("contrast", [sys.executable, "scripts/check_contrast.py"], env=env)
        path = OUTPUT / "frontend-tests.json"
        command("frontend-tests", [npm, "test", "--", "--reporter=json", f"--outputFile={path}"], ROOT / "frontend", env)
        if path.exists():
            report = json.loads(path.read_text(encoding="utf-8"))
            totals = {"passed": report["numPassedTests"], "failed": report["numFailedTests"], "skipped": report["numPendingTests"]}
            results[-1]["tests"] = totals
            for key, value in totals.items():
                counts[key] += value
        command("build", [npm, "run", "build"], ROOT / "frontend", env)
        proc = command("dependency-audit", [npm, "audit", "--json", "--fetch-retries=0", "--fetch-timeout=20000"], ROOT / "frontend", env)
        try:
            results[-1]["vulnerabilities"] = json.loads(proc.stdout)["metadata"]["vulnerabilities"]
        except (json.JSONDecodeError, KeyError):
            results[-1]["status"] = "blocked"
            results[-1]["reason"] = "audit did not return usable registry data"
    try:
        database_checks()
    except Exception as error:
        results.append({"check": "real-database-checks", "status": "blocked", "reason": str(error)})
    summary = {"run_id": RUN, "tests": counts, "checks": results,
               "excluded_from_real_run": {"reason": "three existing simulated MongoDB outage/retry/503 tests use _MongoDown; run separately in backend-stubs",
                   "count": next((r.get("excluded", 0) for r in results if r["check"] == "backend-real"), 0)}}
    (OUTPUT / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps(summary, indent=2), flush=True)
    print(f"Individual tests: {counts['passed']} passed; {counts['failed']} failed; {counts['skipped']} skipped.")
    print("Non-test checks: " + "; ".join(f"{r['check']}={r['status']}" for r in results if "tests" not in r))
    print(f"Summary: {OUTPUT / 'summary.json'}")
    return int(any(result["status"] != "passed" for result in results))


if __name__ == "__main__":
    raise SystemExit(main())
