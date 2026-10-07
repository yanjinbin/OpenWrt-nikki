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
        auto_update|enabled) value="${ENABLED:-1}" ;;
        update_weekdays) value="${DAYS-0}" ;;
        update_time) value="${TIME-04:00}" ;;
        last_scheduled_update) value="${SLOT-}" ;;
        last_attempt) value="${LAST:-740800}" ;;
        profile) value="${PROFILE:-subscription:sample}" ;;
        name) value="Sample" ;;
        url) value="https://example.com/private-token" ;;
        *) value="$4" ;;
    esac
    export "$1=$value"
}
config_get_bool() { config_get "$@"; }
uci_set() {
    printf 'set %s %s\n' "$3" "$4" >> "$TRACE"
    [ "$3" != last_scheduled_update ] || SLOT="$4"
}
uci_remove() { printf 'remove %s\n' "$3" >> "$TRACE"; }
uci_commit() { :; }
date() {
    case "$1" in
        +%s) echo 1000000 ;;
        *) echo "${NOW:-2026-10-11T04:00:0}" ;;
    esac
}
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
                     "RUN_DIR": str(root), "TRACE": str(trace),
                     "STARTED_FLAG_PATH": str(root / "started.flag"), **env},
                capture_output=True, text=True,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            return trace.read_text(), (root / "subscriptions/sample.yaml").read_text()

    def test_weekday_time_and_defaults(self):
        body = '''
update_subscription() { echo attempted >> "$TRACE"; return 0; }
subscription_reload=0
update_subscription_if_due sample
echo "reload $subscription_reload" >> "$TRACE"
'''
        trace, _ = self.run_shell(body)
        self.assertIn("attempted", trace)
        self.assertIn("reload 1", trace)
        for env in ({"NOW": "2026-10-11T03:59:0"}, {"NOW": "2026-10-11T04:01:0"},
                    {"NOW": "2026-10-12T04:00:1"}, {"ENABLED": "0"},
                    {"DAYS": ""}, {"DAYS": "7"}, {"DAYS": "00"}, {"DAYS": "0 *"},
                    {"TIME": "4:00"}, {"TIME": "24:00"}, {"TIME": "04:60"},
                    {"TIME": "04:00\n"}):
            with self.subTest(env=env):
                trace, _ = self.run_shell(body, **env)
                self.assertNotIn("attempted", trace)
                self.assertIn("reload 0", trace)
        trace, _ = self.run_shell(body, DAYS="1 3 0", PROFILE="file:local.yaml")
        self.assertIn("attempted", trace)
        self.assertIn("reload 0", trace)

    def test_once_per_slot_and_manual_updates_do_not_move_schedule(self):
        body = '''
update_subscription() { echo attempted >> "$TRACE"; return "${UPDATE_RESULT:-0}"; }
update_subscription_if_due sample
update_subscription_if_due sample
'''
        for result in ("0", "1"):
            trace, _ = self.run_shell(body, UPDATE_RESULT=result, LAST="1000000")
            self.assertEqual(trace.count("attempted"), 1)
            self.assertIn("set last_scheduled_update 2026-10-11T04:00", trace)
        trace, _ = self.run_shell(body, SLOT="2026-10-11T04:00")
        self.assertNotIn("attempted", trace)
        trace, _ = self.run_shell(body, SLOT="2026-10-11T04:00", NOW="2026-10-18T04:00:0")
        self.assertEqual(trace.count("attempted"), 1)

    def test_custom_weekdays_and_time(self):
        body = 'update_subscription() { echo attempted >> "$TRACE"; }; update_subscription_if_due sample'
        for day in range(7):
            trace, _ = self.run_shell(body, DAYS="1 3 5", TIME="23:59", NOW=f"2026-10-12T23:59:{day}")
            self.assertEqual("attempted" in trace, day in (1, 3, 5))

    def test_worker_uses_one_clock_snapshot_and_skips_when_stopped(self):
        body = '''
config_foreach() { "$1" sample; "$1" second; }
update_subscription_if_due() { echo "tick $subscription_now" >> "$TRACE"; }
touch "$STARTED_FLAG_PATH"
update_subscriptions
rm "$STARTED_FLAG_PATH"
update_subscriptions
'''
        trace, _ = self.run_shell(body)
        self.assertEqual(trace.splitlines(), ["tick 2026-10-11T04:00:0"] * 2)

    def test_migration_defaults_and_preserves_existing_schedule(self):
        body = '''
config_get() {
    case "$3" in
        update_weekdays) export "$1=${SAVED_DAYS-}" ;;
        update_time) export "$1=${SAVED_TIME-}" ;;
    esac
}
config_foreach() { "$1" sample; }
migrate_subscription_schedules
'''
        trace, _ = self.run_shell(body)
        self.assertIn("set update_weekdays 0", trace)
        self.assertIn("set update_time 04:00", trace)
        self.assertIn("remove update_interval", trace)
        trace, _ = self.run_shell(body, SAVED_DAYS="1 4", SAVED_TIME="05:30", ENABLED="0")
        self.assertEqual(trace, "remove update_interval\n")

    def test_slot_write_failure_does_not_download(self):
        trace, _ = self.run_shell('''
uci_commit() { return 1; }
update_subscription() { echo attempted >> "$TRACE"; }
update_subscription_if_due sample
test $? = 1
''')
        self.assertNotIn("attempted", trace)

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
