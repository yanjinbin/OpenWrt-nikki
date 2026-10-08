import json
import os
from pathlib import Path
import shutil
import subprocess
import threading
import time
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer


ROOT = Path(__file__).resolve().parents[1]
MODULE = ROOT / "nikki/files/ucode/proxy_schedule.uc"
UCODE = os.environ.get("UCODE", shutil.which("ucode") or "ucode")
GROUP = '📺 油管 / "test"? #&'
INSIDE = "🇺🇸-ai专用-dmit ' $(touch /tmp/nikki-injection)"
OUTSIDE = "高质量节点-select"


def rule(**values):
    return {".name": "youtube", "enabled": "1", "group": GROUP,
            "start_time": "18:00", "end_time": "22:00",
            "inside": INSIDE, "outside": OUTSIDE, **values}


def proxies(now=OUTSIDE):
    return {GROUP: {"type": "Selector", "all": [INSIDE, OUTSIDE], "now": now},
            "Fallback": {"type": "Fallback", "all": ["DIRECT"], "now": "DIRECT"}}


class ScheduleTest(unittest.TestCase):
    def evaluate(self, expression, data):
        source = (f"import * as schedule from '{MODULE}';\n"
                  f"const data = {json.dumps(data, ensure_ascii=False)};\n"
                  f"print(sprintf('%J', {expression}));\n")
        paths = ["-L", os.environ["UCODE_LIB"]] if os.environ.get("UCODE_LIB") else []
        result = subprocess.run([UCODE, *paths, "-e", source], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        return json.loads(result.stdout)

    def plan(self, rules=None, now=18 * 60, groups=None):
        return self.evaluate("schedule.plan(data.rules, data.proxies, data.minute)", {
            "rules": rules if rules is not None else [rule()],
            "proxies": groups if groups is not None else proxies(), "minute": now})

    def test_daily_boundaries(self):
        for minute, target in ((0, None), (1079, None), (1080, INSIDE),
                               (1319, INSIDE), (1320, None), (1439, None)):
            with self.subTest(minute=minute):
                self.assertEqual(self.plan(now=minute)[0].get("target"), target)

    def test_overnight_boundaries(self):
        rules = [rule(start_time="22:00", end_time="06:00")]
        for minute, target in ((1319, None), (1320, INSIDE), (0, INSIDE),
                               (359, INSIDE), (360, None)):
            with self.subTest(minute=minute):
                self.assertEqual(self.plan(rules, minute)[0].get("target"), target)

    def test_invalid_times_and_missing_fields(self):
        for fields in ({"start_time": "8:00"}, {"start_time": "24:00"},
                       {"end_time": "22:60"}, {"start_time": "18:00\n"},
                       {"start_time": "22:00"}, {"inside": ""}, {"group": ""},
                       {"start_time": None}):
            with self.subTest(fields=fields):
                self.assertIn("error", self.plan([rule(**fields)])[0])

    def test_disabled_rules_and_duplicate_groups(self):
        self.assertEqual(self.plan([rule(enabled="0")]), [])
        self.assertEqual(self.plan([rule(enabled=None)]), [])
        result = self.plan([rule(), rule(**{".name": "duplicate"})])
        self.assertTrue(all("error" in item for item in result))
        self.assertNotIn("error", self.plan([rule(), rule(enabled="0")])[0])

    def test_missing_group_type_or_candidate(self):
        for groups in ({}, {GROUP: {"type": "Fallback", "all": [INSIDE, OUTSIDE]}},
                       {GROUP: {"type": "Selector", "all": [OUTSIDE]}}):
            with self.subTest(groups=groups):
                self.assertIn("error", self.plan(groups=groups)[0])

    def test_matching_selection_is_unchanged(self):
        self.assertFalse(self.plan(groups=proxies(INSIDE))[0]["changed"])
        self.assertTrue(self.plan()[0]["changed"])

    def test_outside_target_is_optional_and_legacy_values_are_ignored(self):
        for outside in (None, "", "deleted target"):
            value = rule(outside=outside)
            if outside is None:
                del value["outside"]
            result = self.plan([value])[0]
            self.assertNotIn("error", result)
            self.assertEqual(result["target"], INSIDE)

    def test_outside_period_preserves_any_current_selection(self):
        for current in (INSIDE, OUTSIDE, "manual selection"):
            result = self.plan(now=1320, groups=proxies(current))[0]
            self.assertEqual(result["period"], "outside")
            self.assertEqual(result["current"], current)
            self.assertFalse(result["changed"])
            self.assertNotIn("target", result)

    def test_leading_zero_hours(self):
        self.assertEqual(self.plan([rule(start_time="08:00", end_time="09:00")],
                                   8 * 60)[0]["target"], INSIDE)


class ControllerTest(unittest.TestCase):
    evaluate = ScheduleTest.evaluate

    def setUp(self):
        self.calls = []
        self.current = OUTSIDE
        self.get_status = 200
        self.put_status = 204
        self.invalid_json = False
        self.delay = 0
        owner = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *_):
                pass

            def do_GET(self):
                owner.calls.append(("GET", self.path, self.headers.get("Authorization")))
                time.sleep(owner.delay)
                self.send_response(owner.get_status)
                self.end_headers()
                body = "invalid" if owner.invalid_json else json.dumps({"proxies": proxies(owner.current)})
                try:
                    self.wfile.write(body.encode())
                except (BrokenPipeError, ConnectionResetError):
                    pass

            def do_PUT(self):
                body = self.rfile.read(int(self.headers["Content-Length"]))
                owner.calls.append(("PUT", self.path, json.loads(body)))
                self.send_response(owner.put_status)
                self.end_headers()
                if owner.put_status == 204:
                    owner.current = json.loads(body)["name"]

        self.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.profile = {"external-controller": f"0.0.0.0:{self.server.server_port}",
                        "secret": "test'$(false) token"}

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join()

    def reconcile(self, rules=None, minute=1080):
        return self.evaluate("schedule.reconcile(data.rules, data.minute, data.profile)", {
            "rules": rules if rules is not None else [rule()],
            "minute": minute, "profile": self.profile})

    def test_switch_is_encoded_authenticated_and_idempotent(self):
        from urllib.parse import quote
        result = self.reconcile()
        self.assertTrue(result[0]["changed"])
        self.assertEqual(self.calls[0], ("GET", "/proxies", "Bearer " + self.profile["secret"]))
        self.assertEqual(self.calls[1], ("PUT", "/proxies/" + quote(GROUP, safe=""), {"name": INSIDE}))
        self.calls.clear()
        self.assertFalse(self.reconcile()[0]["changed"])
        self.assertEqual(len(self.calls), 1)

    def test_period_end_and_manual_changes_do_not_send_put(self):
        self.reconcile()
        for minute, current in ((1320, INSIDE), (1439, OUTSIDE), (0, INSIDE)):
            self.current = current
            self.calls.clear()
            result = self.reconcile(minute=minute)[0]
            self.assertFalse(result["changed"])
            self.assertEqual(self.current, current)
            self.assertTrue(all(call[0] == "GET" for call in self.calls))

    def test_failed_switch_is_retried_next_run(self):
        self.put_status = 400
        self.assertIn("error", self.reconcile()[0])
        self.assertEqual(self.current, OUTSIDE)
        self.put_status = 204
        self.assertTrue(self.reconcile()[0]["changed"])
        self.assertEqual(self.current, INSIDE)

    def test_get_failure_never_switches(self):
        for status, invalid in ((401, False), (503, False), (200, True)):
            self.get_status, self.invalid_json = status, invalid
            self.calls.clear()
            self.assertIn("error", self.reconcile()[0])
            self.assertTrue(all(call[0] == "GET" for call in self.calls))

    def test_disabled_schedule_makes_no_requests(self):
        self.assertEqual(self.reconcile([rule(enabled="0")]), [])
        self.assertEqual(self.calls, [])

    def test_api_unavailable_then_recovers(self):
        self.get_status = 503
        self.assertIn("error", self.reconcile()[0])
        self.get_status = 200
        self.assertTrue(self.reconcile()[0]["changed"])

    def test_group_discovery_only_returns_selectors(self):
        result = self.evaluate("schedule.get_groups(data)", self.profile)
        self.assertEqual(list(result), [GROUP])
        self.assertEqual(result[GROUP]["all"], [INSIDE, OUTSIDE])

    def test_slow_api_is_bounded_and_does_not_switch(self):
        self.delay = 6
        start = time.monotonic()
        self.assertIn("error", self.reconcile()[0])
        elapsed = time.monotonic() - start
        self.assertGreaterEqual(elapsed, 4)
        self.assertLess(elapsed, 6)
        self.assertTrue(all(call[0] == "GET" for call in self.calls))

    def test_missing_controller_fails_without_requests(self):
        self.profile = {}
        self.assertIn("error", self.reconcile()[0])
        self.assertEqual(self.calls, [])

    def test_conflicting_rules_never_switch(self):
        result = self.reconcile([rule(), rule(**{".name": "duplicate"})])
        self.assertTrue(all("error" in item for item in result))
        self.assertTrue(all(call[0] == "GET" for call in self.calls))


if __name__ == "__main__":
    unittest.main()
