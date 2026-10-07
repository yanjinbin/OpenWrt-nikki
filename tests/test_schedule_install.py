import os
from pathlib import Path
import subprocess
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]


class InstallTest(unittest.TestCase):
    def test_patch_installs_scheduler_dependencies_and_menu(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            bin_dir = root / "bin"
            bin_dir.mkdir()
            (bin_dir / "wget").write_text('''#!/bin/sh
source=${3#https://fixture/}
source=${source%%\\?*}
cp "$TEST_REPO/$source" "$2"
''')
            (bin_dir / "uci").write_text('''#!/bin/sh
case "$*" in
    '-q get nikki.procd') echo procd ;;
    '-q get nikki.procd.clear_connections_on_reload') echo 1 ;;
    *) exit 1 ;;
esac
''')
            for path in bin_dir.iterdir():
                path.chmod(0o755)
            dest = root / "install"
            result = subprocess.run(["/bin/sh", str(ROOT / "install-luci-patch.sh")],
                env={**os.environ, "PATH": str(bin_dir) + os.pathsep + os.environ["PATH"],
                     "DESTDIR": str(dest), "RESTART_SERVICES": "0", "GITHUB_PROXY": "",
                     "NIKKI_RAW_BASE": "https://fixture", "TEST_REPO": str(ROOT)},
                capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            for source, target in [
                ("nikki/files/ucode/proxy_schedule.uc", "etc/nikki/ucode/proxy_schedule.uc"),
                ("nikki/files/ucode/schedule.uc", "etc/nikki/ucode/schedule.uc"),
                ("nikki/files/nikki.init", "etc/init.d/nikki"),
                ("luci-app-nikki/htdocs/luci-static/resources/view/nikki/schedule.js", "www/luci-static/resources/view/nikki/schedule.js"),
                ("luci-app-nikki/root/usr/share/luci/menu.d/luci-app-nikki.json", "usr/share/luci/menu.d/luci-app-nikki.json"),
            ]:
                self.assertEqual((dest / target).read_bytes(), (ROOT / source).read_bytes())
            self.assertTrue((dest / "etc/config/nikki_schedule").is_file())
            acl = (dest / "usr/share/rpcd/acl.d/luci-app-nikki.json").read_text()
            self.assertIn('nikki_schedule', acl)
            self.assertTrue(os.access(dest / "etc/init.d/nikki", os.X_OK))
            saved = dest / "etc/config/nikki_schedule"
            saved.write_text("# Existing user schedules\n")
            repeat = subprocess.run(["/bin/sh", str(ROOT / "install-luci-patch.sh")],
                env={**os.environ, "PATH": str(bin_dir) + os.pathsep + os.environ["PATH"],
                     "DESTDIR": str(dest), "RESTART_SERVICES": "0", "GITHUB_PROXY": "",
                     "NIKKI_RAW_BASE": "https://fixture", "TEST_REPO": str(ROOT)},
                capture_output=True, text=True)
            self.assertEqual(repeat.returncode, 0, repeat.stderr)
            self.assertEqual(saved.read_text(), "# Existing user schedules\n")


if __name__ == "__main__":
    unittest.main()
