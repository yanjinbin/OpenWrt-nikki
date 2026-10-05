import os
from pathlib import Path
import subprocess
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
FUNCTIONS = (ROOT / "nikki/files/nikki.init").read_text().split("report_subscription_failure()", 1)[1]
FUNCTIONS = "report_subscription_failure()" + FUNCTIONS
STUBS = r'''
config_load() { :; }
config_get() {
    local value
    case "$3" in
        auto_update) value="${ENABLED:-1}" ;;
        update_interval) value="${HOURS:-72}" ;;
        last_attempt) value="${LAST:-740800}" ;;
        profile) value="${PROFILE:-subscription:sample}" ;;
        name) value="Sample" ;;
        url) value="https://example.com/private-token" ;;
        *) value="$4" ;;
    esac
    export "$1=$value"
}
config_get_bool() { config_get "$@"; }
uci_set() { printf 'set %s %s\n' "$3" "$4" >> "$TRACE"; }
uci_remove() { printf 'remove %s\n' "$3" >> "$TRACE"; }
uci_commit() { :; }
date() { echo 1000000; }
log() { :; }
flock() { return "${LOCK_RESULT:-0}"; }
prepare_files() { :; }
report_subscription_failure() { echo "report $*" >> "$TRACE"; }
curl() {
    printf '%s' "${HTTP_STATUS:-200}"
    printf 'proxies: []\n' > "$TEMP_DIR/sample.yaml"
    : > "$TEMP_DIR/sample.header"
    return "${CURL_RESULT:-0}"
}
yq() { return "${YAML_RESULT:-0}"; }
core_check() { return "${CORE_RESULT:-0}"; }
cp() { [ "${SAVE_RESULT:-0}" = 0 ] && command cp "$@"; }
PROG=core_check
'''


class SubscriptionTest(unittest.TestCase):
    def run_shell(self, body, **env):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "temp").mkdir()
            (root / "subscriptions").mkdir()
            (root / "subscriptions/sample.yaml").write_text("old profile\n")
            trace = root / "trace"
            trace.touch()
            result = subprocess.run(
                ["/bin/sh", "-c", FUNCTIONS + STUBS + body],
                env={**os.environ, "TEMP_DIR": str(root / "temp"),
                     "SUBSCRIPTIONS_DIR": str(root / "subscriptions"),
                     "RUN_DIR": str(root), "TRACE": str(trace), **env},
                capture_output=True, text=True,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            return trace.read_text(), (root / "subscriptions/sample.yaml").read_text()

    def test_due_boundary_and_defaults(self):
        body = '''
update_subscription() { echo attempted >> "$TRACE"; return 0; }
subscription_reload=0
update_subscription_if_due sample
echo "reload $subscription_reload" >> "$TRACE"
'''
        trace, _ = self.run_shell(body)
        self.assertIn("attempted", trace)
        self.assertIn("reload 1", trace)
        for env in ({"LAST": "740801"}, {"ENABLED": "0"}, {"HOURS": "1.5"}, {"HOURS": "0"}, {"HOURS": "8761"}):
            with self.subTest(env=env):
                trace, _ = self.run_shell(body, **env)
                self.assertNotIn("attempted", trace)
                self.assertIn("reload 0", trace)
        trace, _ = self.run_shell(body, LAST="996400", HOURS="1", PROFILE="profile:local.yaml")
        self.assertIn("attempted", trace)
        self.assertIn("reload 0", trace)

    def test_first_interval_and_clock_rollback(self):
        for last in ("0", "2000000"):
            trace, _ = self.run_shell("update_subscription_if_due sample", LAST=last)
            self.assertIn("set last_attempt 1000000", trace)
            self.assertNotIn("report", trace)

    def test_failure_preserves_profile_and_success_metadata(self):
        for env, reason in (({"CURL_RESULT": "22", "HTTP_STATUS": "503"}, "download_failed"),
                            ({"YAML_RESULT": "1"}, "invalid_profile"),
                            ({"CORE_RESULT": "1"}, "invalid_profile"),
                            ({"SAVE_RESULT": "1"}, "save_failed")):
            with self.subTest(env=env):
                trace, profile = self.run_shell("update_subscription sample; test $? = 1", **env)
                self.assertEqual(profile, "old profile\n")
                self.assertIn("set last_attempt 1000000", trace)
                self.assertIn("set success 0", trace)
                self.assertIn("report sample " + reason, trace)
                self.assertNotIn("remove", trace)

    def test_success_replaces_profile(self):
        trace, profile = self.run_shell("update_subscription sample")
        self.assertEqual(profile, "proxies: []\n")
        self.assertIn("set success 1", trace)
        self.assertNotIn("report", trace)

    def test_failed_schedule_does_not_reload(self):
        trace, profile = self.run_shell('''
subscription_reload=0
update_subscription_if_due sample
echo "reload $subscription_reload" >> "$TRACE"
''', CURL_RESULT="7")
        self.assertIn("reload 0", trace)
        self.assertEqual(profile, "old profile\n")

    def test_busy_update_does_not_write(self):
        trace, profile = self.run_shell("update_subscription sample; test $? = 1", LOCK_RESULT="1")
        self.assertEqual(trace, "")
        self.assertEqual(profile, "old profile\n")


if __name__ == "__main__":
    unittest.main()
