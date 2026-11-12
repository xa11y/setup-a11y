"""Exercise the grant script without sudo or a macOS system database."""
import json
import os
from pathlib import Path
import sqlite3
import subprocess
import tempfile
import unittest

SCRIPT = Path(__file__).with_name("grant-macos-tcc.sh").resolve()

# Replace only the OS boundary. Execute the actual SQL against a temporary DB,
# and inject SQLITE_BUSY failures independently for writes and reads.
SUDO = r'''#!/usr/bin/env python3
import json, os, pathlib, sqlite3, sys
root = pathlib.Path(os.environ["TEST_ROOT"])
args = sys.argv[1:]
with (root / "calls").open("a") as log:
    log.write(json.dumps(args) + "\n")
if args[0] == "launchctl":
    sys.exit(0)
assert args[:3] == ["sqlite3", "-cmd", ".timeout 10000"]
assert args[3] == "/Library/Application Support/com.apple.TCC/TCC.db"
sql = args[4]
operation = "write" if sql.startswith("INSERT") else "read"
counter = root / operation
attempt = int(counter.read_text()) + 1 if counter.exists() else 1
counter.write_text(str(attempt))
if attempt <= int(os.environ.get(operation.upper() + "_FAILURES", "0")):
    print("Error: stepping, database is locked (5)", file=sys.stderr)
    sys.exit(5)
with sqlite3.connect(root / "tcc.db") as db:
    rows = db.execute(sql).fetchall()
    if operation == "write":
        if os.environ.get("GRANT_MODE") == "missing":
            db.execute("DELETE FROM access")
        elif os.environ.get("GRANT_MODE") == "denied":
            db.execute("UPDATE access SET auth_value=0")
        elif os.environ.get("GRANT_MODE") == "other-key":
            db.execute("UPDATE access SET indirect_object_identifier='OTHER'")
    for row in rows:
        print(row[0])
'''


class GrantTests(unittest.TestCase):
    def run_grant(self, client="/tmp/test python", **options):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            with sqlite3.connect(root / "tcc.db") as db:
                db.execute("""CREATE TABLE access (
                    service TEXT, client TEXT, client_type INTEGER,
                    auth_value INTEGER, auth_reason INTEGER, auth_version INTEGER,
                    csreq BLOB, policy_id INTEGER, indirect_object_identifier_type INTEGER,
                    indirect_object_identifier TEXT, indirect_object_code_identity BLOB,
                    flags INTEGER, last_modified INTEGER,
                    PRIMARY KEY(service, client, client_type, indirect_object_identifier))""")
            for name, content in {
                "sudo": SUDO,
                "sleep": '#!/bin/sh\nprintf "%s\\n" "$1" >> "$TEST_ROOT/sleeps"\n',
            }.items():
                path = root / name
                path.write_text(content)
                path.chmod(0o755)
            env = {**os.environ, **options, "TEST_ROOT": directory,
                   "PATH": directory + os.pathsep + os.environ["PATH"]}
            result = subprocess.run(["bash", str(SCRIPT), client], env=env,
                                    text=True, capture_output=True, timeout=10)
            calls = [json.loads(line) for line in (root / "calls").read_text().splitlines()] if (root / "calls").exists() else []
            sleeps = (root / "sleeps").read_text().splitlines() if (root / "sleeps").exists() else []
            with sqlite3.connect(root / "tcc.db") as db:
                rows = db.execute("SELECT client, auth_value FROM access").fetchall()
            return result, calls, sleeps, rows

    def test_empty_client_warns_without_system_calls(self):
        result, calls, sleeps, _ = self.run_grant("")
        self.assertEqual(result.returncode, 0)
        self.assertIn("::warning::", result.stdout)
        self.assertEqual(calls, [])
        self.assertEqual(sleeps, [])

    def test_success_preserves_special_characters_in_client(self):
        client = "/tmp/it's a $(test) interpreter"
        result, calls, sleeps, rows = self.run_grant(client)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(rows, [(client, 2)])
        self.assertEqual(len(calls), 3)
        self.assertEqual(calls[-1], ["launchctl", "stop", "com.apple.tccd"])
        self.assertEqual(sleeps, ["2"])

    def test_write_and_read_each_retry_through_fifth_attempt(self):
        result, calls, sleeps, _ = self.run_grant(WRITE_FAILURES="4", READ_FAILURES="4")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(len(calls), 11)
        self.assertEqual(sleeps, ["2", "4", "6", "8"] * 2 + ["2"])

    def test_exhausted_write_or_read_fails_without_restart(self):
        for operation, count in [("WRITE", 5), ("READ", 6)]:
            with self.subTest(operation=operation):
                result, calls, sleeps, _ = self.run_grant(**{operation + "_FAILURES": "5"})
                self.assertEqual(result.returncode, 1)
                self.assertIn("::error::", result.stderr)
                self.assertIn("failed after 5 attempts", result.stderr)
                self.assertEqual(len(calls), count)
                self.assertTrue(all(call[0] == "sqlite3" for call in calls))
                self.assertEqual(sleeps, ["2", "4", "6", "8"])

    def test_missing_denied_or_wrong_row_fails_verification(self):
        for mode in ["missing", "denied", "other-key"]:
            with self.subTest(mode=mode):
                result, calls, sleeps, _ = self.run_grant(GRANT_MODE=mode)
                self.assertEqual(result.returncode, 1)
                self.assertIn("::error::", result.stderr)
                self.assertIn("no allowed", result.stderr)
                self.assertEqual(len(calls), 2)
                self.assertEqual(sleeps, [])


if __name__ == "__main__":
    unittest.main()
