import os
from pathlib import Path
import subprocess
import tempfile
import unittest


SOURCE = (Path(__file__).resolve().parents[1] / "nikki/files/nikki.init").read_text()
FUNCTIONS = SOURCE[SOURCE.index("proxy_schedule_cron() {"):SOURCE.index("report_subscription_failure() (")]


class ServiceTest(unittest.TestCase):
    def run_shell(self, body, **env):
        with tempfile.TemporaryDirectory() as directory:
            result = subprocess.run(["/bin/sh", "-c", FUNCTIONS + r'''
config_get() { export "$1=${INTERVAL:-1}"; }
flock() { return "${BUSY:-0}"; }
ucode() { echo checked; return "${FAILED:-0}"; }
STARTED_FLAG_PATH="$TEMP_DIR/started.flag"
UCODE_DIR=/etc/nikki/ucode
''' + body], env={**os.environ, "TEMP_DIR": directory, **env},
                capture_output=True, text=True)
            return result

    def test_minute_tick_reads_interval_in_worker(self):
        self.assertEqual(self.run_shell("proxy_schedule_cron").stdout.strip(), "* * * * *")
        self.assertIn('"$UCODE_DIR/schedule.uc" "$@"', SOURCE)
        self.assertIn('schedule_proxies --force >/dev/null 2>&1 &', SOURCE)
        self.assertNotIn('procd_add_reload_trigger "nikki_schedule"', SOURCE)

    def test_stopped_or_locked_service_does_no_work(self):
        self.assertEqual(self.run_shell("schedule_proxies").stdout, "")
        self.assertEqual(self.run_shell('touch "$STARTED_FLAG_PATH"; schedule_proxies', BUSY="1").stdout, "")

    def test_worker_exits_after_check_and_propagates_failure(self):
        body = 'touch "$STARTED_FLAG_PATH"; schedule_proxies'
        result = self.run_shell(body)
        self.assertEqual(result.stdout, "checked\n")
        self.assertEqual(result.returncode, 0)
        self.assertEqual(self.run_shell(body, FAILED="1").returncode, 1)


if __name__ == "__main__":
    unittest.main()
