import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
UCODE = os.environ.get('UCODE') or shutil.which('ucode')
MODULE = ROOT / 'nikki/files/ucode/proxy_schedule.uc'


@unittest.skipUnless(UCODE, 'Set UCODE to a native ucode executable (with fs module)')
class ProxyScheduleTest(unittest.TestCase):
    def run_ucode(self, script, env=None):
        result = subprocess.run([UCODE, '-S', '-e', script], text=True,
                                capture_output=True, env=env)
        self.assertEqual(result.returncode, 0, result.stderr)
        return result.stdout

    def test_curl_transport_escaping_and_auth(self):
        # Execute the real shell command and curl-config generation. This curl
        # double reads the inherited descriptor, so auth is never in argv.
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            curl = root / 'curl'
            curl.write_text('''#!/usr/bin/env python3
import json, os, sys
from pathlib import Path
args = sys.argv[1:]
config = Path(args[args.index('--config') + 1]).read_text()
Path(os.environ['TRACE']).write_text(json.dumps({'args':args,'config':config}))
print(os.environ.get('RESPONSE', '{}'))
print(os.environ.get('HTTP_STATUS', '200'), end='')
sys.exit(int(os.environ.get('CURL_EXIT', '0')))
''')
            curl.chmod(0o755)
            trace = root / 'trace'
            env = {**os.environ, 'PATH': str(root) + ':' + os.environ['PATH'], 'TRACE': str(trace)}
            secret = 'dummy-\'"\\$(`do-not-run`)'
            group = '油管 🇺🇸 / ?#%\'"\\$(do-not-run)'
            target = '目标\'"\\\n🇺🇸'
            profile = {'external-controller': '0.0.0.0:9090', 'secret': secret}
            prefix = 'import { proxy_api, path_encode as encode_name } from ' + json.dumps(str(MODULE)) + '; '
            call = 'print(proxy_api(' + json.dumps(profile) + ', "PUT", "/proxies/" + encode_name(' + json.dumps(group) + '), {name:' + json.dumps(target) + '}));'
            response = json.loads(self.run_ucode(prefix + call, env))
            self.assertTrue(response['ok'])
            recorded = json.loads(trace.read_text())
            args = recorded['args']
            self.assertNotIn(secret, ' '.join(args))
            expected = 'header = "Authorization: Bearer ' + secret.replace('\\', '\\\\').replace('"', '\\"') + '"\n'
            self.assertEqual(recorded['config'], expected)
            self.assertEqual(json.loads(args[args.index('--data-binary') + 1]), {'name': target})
            from urllib.parse import quote
            self.assertEqual(args[args.index('--url') + 1], 'http://127.0.0.1:9090/proxies/' + quote(group, safe='~'))
            for status, exit_code in [('401', '22'), ('503', '22'), ('000', '7'), ('302', '0')]:
                with self.subTest(status=status):
                    result = json.loads(self.run_ucode(prefix + call, {**env, 'HTTP_STATUS': status, 'CURL_EXIT': exit_code}))
                    self.assertFalse(result['ok'])
                    self.assertNotIn(secret, json.dumps(result))
            get_call = prefix + 'print(proxy_api(' + json.dumps(profile) + ', "GET", "/proxies"));'
            self.assertFalse(json.loads(self.run_ucode(get_call, {**env, 'RESPONSE': 'bad json'}))['ok'])
            tls = {'external-controller-tls': '[::]:9443', 'secret': secret}
            self.run_ucode(prefix + 'print(proxy_api(' + json.dumps(tls) + ', "GET", "/proxies"));', env)
            tlsargs = json.loads(trace.read_text())['args']
            self.assertIn('--insecure', tlsargs)
            self.assertEqual(tlsargs[tlsargs.index('--url') + 1], 'https://[::1]:9443/proxies')
            socket = "/tmp/mock 'controller.sock"
            unix = {'external-controller-unix': socket, 'external-controller':'127.0.0.1:9090', 'secret':secret}
            self.run_ucode(prefix + 'print(proxy_api(' + json.dumps(unix) + ', "GET", "/proxies"));', env)
            unixargs = json.loads(trace.read_text())['args']
            self.assertEqual(unixargs[unixargs.index('--unix-socket') + 1], socket)
            self.assertEqual(unixargs[unixargs.index('--url') + 1], 'http://localhost/proxies')
            for profile in [{}, {'external-controller':'evil:0'}, {'external-controller':'host:65536'}, {'external-controller':'x://host:99'}, {'external-controller':'host:90','secret':'x\nheader = bad'}]:
                trace.unlink(missing_ok=True)
                result = json.loads(self.run_ucode(prefix + 'print(proxy_api(' + json.dumps(profile) + ', "GET", "/proxies"));', env))
                self.assertEqual(result['error'], 'Mihomo API is not configured.')
                self.assertFalse(trace.exists())


class ScheduleLifecycleTest(unittest.TestCase):
    def test_cron_start_reload_cleanup(self):
        source = (ROOT / 'nikki/files/nikki.init').read_text()
        start_cron = source.split('\t# cron\n', 1)[1].split('\n}\n', 1)[0]
        cleanup_cron = source.split('\t# delete cron\n', 1)[1].split('\n}\n', 1)[0]
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            cron = root / 'root'
            flag = root / 'started'
            cron.write_text('15 4 * * * echo unrelated\n* * * * * old #nikki old schedule\n')
            def run(body):
                body = body.replace('/etc/crontabs/root', str(cron)).replace('/etc/init.d/cron restart', ':')
                # GNU/BusyBox sed -i syntax is not available on macOS.
                sed = root / 'sed'
                sed.write_text('#!/usr/bin/env python3\nimport sys\nfrom pathlib import Path\np=Path(sys.argv[-1]); p.write_text("".join(x for x in p.read_text().splitlines(True) if "#nikki" not in x))\n')
                sed.chmod(0o755)
                script = "proxy_schedule_cron() { echo '* * * * *'; };\n" + 'log() { :; }; STARTED_FLAG_PATH=' + str(flag) + '\n' + body
                result = subprocess.run(['/bin/sh', '-c', script], env={**os.environ,'PATH':str(root)+':'+os.environ['PATH']}, capture_output=True, text=True)
                self.assertEqual(result.returncode, 0, result.stderr)
            for _ in range(3):
                run(start_cron)
                text = cron.read_text()
                self.assertEqual(text.count('#nikki proxy schedule'), 1)
                self.assertEqual(text.count('#nikki subscription update'), 1)
                self.assertIn('echo unrelated', text)
                self.assertTrue(flag.exists())
                run(cleanup_cron)
                self.assertNotIn('#nikki', cron.read_text())
                self.assertIn('echo unrelated', cron.read_text())
            self.assertIn('schedule_proxies --force >/dev/null 2>&1 &', source)
            self.assertIn('flock 7', source.split('cleanup() {', 1)[1])
            self.assertIn("procd_add_reload_trigger \"nikki\"", source)
            self.assertNotIn('procd_add_reload_trigger "nikki_schedule"', source)

    def test_package_and_patch_ship_files_and_preserve_config(self):
        makefile = (ROOT / 'nikki/Makefile').read_text()
        installer = (ROOT / 'install-luci-patch.sh').read_text()
        for name in ['proxy_schedule.uc', 'schedule.uc', 'nikki_schedule.conf']:
            self.assertIn(name, makefile)
            self.assertIn(name, installer)
        self.assertIn('if [ ! -f "${DESTDIR}/etc/config/nikki_schedule" ]', installer)
        self.assertIn('flock -n 7', (ROOT / 'nikki/files/nikki.init').read_text())
        for permission in ['read', 'write']:
            acl = json.loads((ROOT / 'luci-app-nikki/root/usr/share/rpcd/acl.d/luci-app-nikki.json').read_text())
            self.assertIn('nikki_schedule', acl['luci-app-nikki'][permission]['uci'])



class IntervalTest(unittest.TestCase):
    def test_interval_gating_recovery_and_changed_settings(self):
        script = '''import { check_due } from ''' + json.dumps(str(MODULE)) + ''';
const previous = {signature:'same', checked_at:1000, rules:[]};
const results = [];
for (let interval in [1,5,10,15,30,60]) {
 push(results, check_due(previous, 'same', 1060, 1, interval, false));
 push(results, check_due(previous, 'same', 1060, 0, interval, false));
}
push(results, check_due(previous, 'changed', 1001, 1, 60, false));
push(results, check_due({}, 'same', 1001, 1, 60, false));
push(results, check_due(previous, 'same', 1001, 1, 60, true));
push(results, check_due(previous, 'same', 999, 1, 60, false));
push(results, check_due(previous, 'same', 4600, 1, 60, false));
previous.rules = [{error:'API failure'}];
push(results, check_due(previous, 'same', 1001, 1, 60, false));
print(sprintf('%J', results));
'''
        result = subprocess.run([UCODE, '-e', script], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout), [True, True] + [False, True] * 5 + [True] * 6)
@unittest.skipUnless(UCODE, 'Set UCODE to run the worker integration tests')
class ScheduleWorkerTest(unittest.TestCase):
    def test_worker_restart_disable_status_and_lock(self):
        import time
        import shlex
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            binary = root / 'bin'; binary.mkdir()
            fixture = root / 'fixture.json'
            selection = root / 'selection'
            trace = root / 'trace'
            started = root / 'started.flag'; started.touch()
            rule = {'.name':'first','enabled':'1','group':'油管','inside':'inside','outside':'outside','start_time':'18:00','end_time':'22:00'}
            fixture.write_text(json.dumps({'enabled':'1','rules':[rule]}))
            selection.write_text('outside')
            module = MODULE.read_text().replace('/var/run/nikki/proxy_schedule.json', str(root / 'status.json')).replace('/var/log/nikki/app.log', str(root / 'app.log'))
            (root / 'proxy_schedule.uc').write_text(module)
            shutil.copy(ROOT / 'nikki/files/ucode/include.uc', root / 'include.uc')
            runner = (ROOT / 'nikki/files/ucode/schedule.uc').read_text().replace("from 'uci'", "from './uci.uc'").replace('/var/run/nikki/started.flag', str(started))
            runner = runner.replace('const now = localtime();', 'const now = {year:2026,mon:10,mday:7,hour:18,min:0,sec:0};')
            (root / 'run.uc').write_text(runner)
            (root / 'uci.uc').write_text('''import { readfile } from 'fs';
export function cursor() {
 let config = json(readfile(getenv('FIXTURE')));
 return { foreach: (name, section, callback) => { for (let rule in config.rules) callback(rule); },
 get: (name) => name == 'nikki' ? config.enabled : '1' };
}
''')
            stubs = {
                'flock': '''#!/usr/bin/env python3
import fcntl,sys
try: fcntl.flock(int(sys.argv[-1]), fcntl.LOCK_EX | (fcntl.LOCK_NB if '-n' in sys.argv else 0))
except BlockingIOError: sys.exit(1)
''',
                'yq': '#!/bin/sh\nprintf \'%s\' \'{"external-controller":"127.0.0.1:9090","secret":"mock"}\'\n',
                'ucode': '#!/bin/sh\nexec ' + shlex.quote(UCODE) + ' -S ' + shlex.quote(str(root / 'run.uc')) + '\n',
                'curl': '''#!/usr/bin/env python3
import json,os,sys,time
from pathlib import Path
args=sys.argv; root=Path(os.environ['TEST_ROOT'])
if os.environ.get('HOLD'):
 (root/'holding').touch()
 deadline=time.monotonic()+5
 while not (root/'release').exists() and time.monotonic()<deadline: time.sleep(.01)
method=args[args.index('--request')+1]
with (root/'trace').open('a') as f: f.write(method+'\\n')
if method=='GET': print(json.dumps({'proxies': {'油管': {'type':'Selector','all':['inside','outside'],'now':(root/'selection').read_text()}}}))
else: (root/'selection').write_text(json.loads(args[args.index('--data-binary')+1])['name'])
print('\\n204' if method=='PUT' else '\\n200',end='')
'''
            }
            for name, content in stubs.items():
                (binary / name).write_text(content); (binary / name).chmod(0o755)
            source = (ROOT / 'nikki/files/nikki.init').read_text()
            wrapper = source.split('schedule_proxies() (',1)[1].split('\n)\n',1)[0]
            wrapper = 'TEMP_DIR=' + shlex.quote(str(root)) + '\nSTARTED_FLAG_PATH=' + shlex.quote(str(started)) + '\nUCODE_DIR=/etc/nikki/ucode\nschedule_proxies() (' + wrapper + '\n)\nschedule_proxies\n'
            env = {**os.environ,'PATH':str(binary)+':'+os.environ['PATH'],'TEST_ROOT':str(root),'FIXTURE':str(fixture)}
            def run():
                result = subprocess.run(['/bin/sh','-c',wrapper],env=env,capture_output=True,text=True)
                self.assertEqual(result.returncode,0,result.stderr)
                rules = json.loads((root/'status.json').read_text())['rules']
                return 'disabled' if not rules else 'switched' if rules[0]['changed'] else 'matched'
            self.assertEqual(run(),'switched')
            self.assertEqual(selection.read_text(),'inside')
            self.assertEqual(run(),'matched')
            self.assertEqual(trace.read_text().splitlines(),['GET','PUT','GET'])
            selection.write_text('outside')
            self.assertEqual(run(),'switched')
            # Stop prevents all API requests; disabling a rule leaves selection alone.
            started.unlink(); before=trace.read_text()
            self.assertEqual(run(),'switched'); self.assertEqual(trace.read_text(),before)
            started.touch(); rule['enabled']='0'
            fixture.write_text(json.dumps({'enabled':'1','rules':[rule]}))
            self.assertEqual(run(),'disabled'); self.assertEqual(trace.read_text(),before)
            rule['enabled']='1'; fixture.write_text(json.dumps({'enabled':'1','rules':[rule]}))
            first = subprocess.Popen(['/bin/sh','-c',wrapper],env={**env,'HOLD':'1'},stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
            try:
                deadline=time.monotonic()+5
                while not (root/'holding').exists() and time.monotonic()<deadline: time.sleep(.01)
                self.assertTrue((root/'holding').exists())
                self.assertEqual(run(),'disabled')  # Overlap exits without overwriting status.
                self.assertEqual(trace.read_text(),before)
                cleanup = source.split('cleanup() {',1)[1].split('\t# load config',1)[0].replace('proxy_schedule.json', 'status.json')
                stopping = subprocess.Popen(['/bin/sh','-c', 'TEMP_DIR=' + shlex.quote(str(root)) + '\nSTARTED_FLAG_PATH=' + shlex.quote(str(started)) + '\n' + cleanup], env=env)
                deadline=time.monotonic()+5
                while started.exists() and time.monotonic()<deadline: time.sleep(.01)
                self.assertFalse(started.exists())
                self.assertIsNone(stopping.poll())
                self.assertEqual(run(),'disabled')
                (root/'release').touch()
                _,errors=first.communicate(timeout=5)
                self.assertEqual(first.returncode,0,errors)
                self.assertEqual(stopping.wait(timeout=5),0)
                self.assertFalse((root/'status.json').exists())
                started.touch()
            finally:
                if first.poll() is None: first.kill(); first.communicate()
            self.assertEqual(run(),'matched')  # Lock is released on process exit.
            log=(root/'app.log').read_text()
            self.assertEqual(len(log.splitlines()),2)
            self.assertNotIn('mock',log)


@unittest.skipUnless(UCODE, 'Set UCODE to test status and logs')
class StatusTest(unittest.TestCase):
    def test_errors_are_deduplicated_and_switches_logged(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            status, log = root / 'status.json', root / 'app.log'
            module = MODULE.read_text().replace('/var/run/nikki/proxy_schedule.json', str(status)).replace('/var/log/nikki/app.log', str(log))
            path = root / 'proxy_schedule.uc'; path.write_text(module)
            script = 'import {save_schedule_status} from ' + json.dumps(str(path)) + ';' + """
const state = {local_time:'2026-10-07 18:00:00', rules:[{section:'one', error:'Mihomo API request failed.'}]};
save_schedule_status(state);
save_schedule_status(state);
state.rules = [{section:'one',changed:false,current:'outside'}];
save_schedule_status(state);
state.rules = [{section:'one',changed:true,group:'line\\nbreak',target:'inside'}];
save_schedule_status(state);
"""
            result = subprocess.run([UCODE, '-e', script], capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(len(log.read_text().splitlines()), 2)
            self.assertEqual(json.loads(status.read_text())['rules'][0]['target'], 'inside')
            self.assertFalse(Path(str(status) + '.new').exists())
