"""Real terminal evidence on Windows ConPTY and POSIX PTYs, not mocked input.

Default exits nonzero when intended behavior fails. --check-baseline instead
checks EXACT known outcomes of the pinned release; an unexplained failure still
fails CI. --virtual-input changes only a child Windows console and restores it.
"""
import argparse
import ctypes
from datetime import datetime, timezone
import errno
import hashlib
import json
import os
from pathlib import Path
import platform
import re
import shutil
import signal
import subprocess
import sys
import threading
import time

ROOT = Path(__file__).resolve().parents[1]
ANSI = re.compile(r'\x1b\[[0-?]*[ -/]*[@-~]')
TIMEOUT = {'state': 'timeout'}


def returned(value):
    return {'state': 'returned', 'value': value}


def launch_windows(command):
    from ctypes import wintypes
    kernel = ctypes.WinDLL('kernel32', use_last_error=True)
    kernel.GetStdHandle.restype = wintypes.HANDLE
    kernel.GetStdHandle.argtypes = [wintypes.DWORD]
    kernel.GetConsoleMode.argtypes = [wintypes.HANDLE, ctypes.POINTER(wintypes.DWORD)]
    kernel.SetConsoleMode.argtypes = [wintypes.HANDLE, wintypes.DWORD]
    handle = kernel.GetStdHandle(-10 & 0xffffffff)
    mode = wintypes.DWORD()
    if not kernel.GetConsoleMode(handle, ctypes.byref(mode)):
        raise ctypes.WinError(ctypes.get_last_error())
    original = mode.value
    if not kernel.SetConsoleMode(handle, original | 0x0200):
        raise ctypes.WinError(ctypes.get_last_error())
    try:
        return subprocess.call(command)
    finally:
        if not kernel.SetConsoleMode(handle, original):
            raise ctypes.WinError(ctypes.get_last_error())


class Terminal:
    def __init__(self, command, virtual_input):
        self.chunks = []
        self.read_error = None
        environment = os.environ.copy()
        environment['TERM'] = 'xterm-256color'
        if os.name == 'nt':
            from winpty import Backend, PtyProcess
            if virtual_input:
                command = [sys.executable, str(Path(__file__).resolve()), '--launch-virtual-input'] + command
            self.process = PtyProcess.spawn(
                ['cmd.exe', '/d', '/c'] + command, cwd=str(ROOT),
                env=environment, dimensions=(40, 120), backend=Backend.ConPTY,
            )
        else:
            import pty
            import fcntl
            import termios
            self.master, slave = pty.openpty()
            fcntl.ioctl(slave, termios.TIOCSWINSZ, __import__('struct').pack('HHHH', 40, 120, 0, 0))

            def child_session():
                os.setsid()
                fcntl.ioctl(slave, termios.TIOCSCTTY, 0)

            self.process = subprocess.Popen(
                command, cwd=ROOT, env=environment, stdin=slave, stdout=slave,
                stderr=slave, preexec_fn=child_session,
            )
            os.close(slave)
        self.thread = threading.Thread(target=self.read, daemon=True)
        self.thread.start()

    def read(self):
        try:
            while True:
                data = self.process.read(4096) if os.name == 'nt' else os.read(self.master, 4096)
                if not data:
                    return
                self.chunks.append(data if isinstance(data, str) else data.decode('utf-8', errors='replace'))
        except EOFError:
            pass
        except OSError as error:
            if os.name == 'nt' or error.errno in (errno.EIO, errno.EBADF):
                return
            self.read_error = str(error)

    def text(self):
        return ANSI.sub('', ''.join(self.chunks))

    def wait(self, text, seconds=10):
        deadline = time.monotonic() + seconds
        while time.monotonic() < deadline:
            if self.read_error:
                raise RuntimeError(self.read_error)
            if text in self.text():
                return True
            time.sleep(0.02)
        return False

    def send(self, keys):
        if os.name == 'nt':
            self.process.write(keys)
        else:
            os.write(self.master, keys.encode('utf-8'))
        time.sleep(0.06)

    def close(self):
        if os.name == 'nt':
            self.process.close(force=True)
        else:
            if self.process.poll() is None:
                os.killpg(self.process.pid, signal.SIGKILL)
            self.process.wait(timeout=5)
            os.close(self.master)
        self.thread.join(timeout=1)


def cases():
    rows = []
    for component in ['text', 'password', 'form', 'multiline', 'search-filter', 'palette']:
        ending = '\x04' if component == 'multiline' else '\r'
        for byte in [8, 127]:
            desired = ['probe'] if component == 'search-filter' else 'probe'
            defect = ['probeX'] if component == 'search-filter' else 'probeX'
            rows.append(dict(name=f'{component}-bs{byte}', component=component,
                keys=['probeX', chr(byte), ending], correct=returned(desired),
                default_windows=returned(defect if byte == 127 else desired),
                other=returned(defect if byte == 8 else desired)))
    for component, keys, correct, default in [
        ('confirm', ['\x1b[C', '\r'], False, True),
        ('slider', ['\x1b[C', '\r'], 6, 5),
        ('rating', ['\x1b[C', '\r'], 4, 3),
        ('search', ['\x1b[B', '\r'], ['Beta'], ['Alpha']),
        ('checkbox', ['\x1b[B', ' ', '\r'], ['Beta'], ['Alpha']),
        ('grid', ['\x1b[B', '\r'], ['Beta'], ['Alpha']),
        ('tags', ['\x1b[B', ' ', '\r'], ['Beta'], ['Alpha']),
        ('choice', ['\x1b[B', '\r'], ['Beta'], ['Alpha']),
        ('text', ['ac', '\x1b[D', 'b', '\r'], 'abc', 'acb'),
    ]:
        rows.append(dict(name=f'{component}-arrows', component=component, keys=keys,
            correct=returned(correct), default_windows=returned(default), other=returned(correct)))
    for name, ending in [('text-enter-cr', '\r'), ('text-enter-lf', '\n')]:
        rows.append(dict(name=name, component='text', keys=['probe', ending],
            correct=returned('probe'), default_windows=TIMEOUT if ending == '\n' else returned('probe'),
            other=returned('probe')))
    for component in ['text', 'confirm', 'search']:
        desired = {'text': None, 'confirm': True, 'search': []}[component]
        rows.append(dict(name=f'{component}-lone-escape', component=component, keys=['\x1b'],
            correct=returned(desired), default_windows=TIMEOUT, other=TIMEOUT))
    rows.append(dict(name='mamba', component='mamba', keys=[],
        correct=returned({'description': 'probe', 'install': False, 'git': True}),
        default_windows=returned({'description': 'probeX', 'install': True, 'git': False}),
        other=returned({'description': 'probe', 'install': False, 'git': True})))
    return rows


def run_case(case, dart, options):
    command = [dart, str(ROOT / '.dart_tool/component.dill'), case['component']]
    terminal = Terminal(command, options.virtual_input)
    try:
        ready = 'Short description' if case['component'] == 'mamba' else 'Keyboard lab'
        if not terminal.wait(ready, 20):
            raise RuntimeError('No rendered interactive prompt: ' + ascii(terminal.text()[-800:]))
        if case['component'] == 'mamba':
            for key in ['probeX', '\x7f', '\r']:
                terminal.send(key)
            if not terminal.wait('Install dependencies?'):
                raise RuntimeError('Mamba did not advance to installation')
            terminal.send('\x1b[C')
            terminal.send('\r')
            if not terminal.wait('Initialize a Git repository?'):
                raise RuntimeError('Mamba did not advance to Git')
            terminal.send('\x1b[D')
            terminal.send('\r')
        else:
            for keys in case['keys']:
                terminal.send(keys)
        observation = TIMEOUT
        if terminal.wait('LAB_RESULT=', 2):
            line = next(line for line in terminal.text().splitlines() if 'LAB_RESULT=' in line)
            observation = returned(json.loads(line.split('LAB_RESULT=', 1)[1]))
        expected = case['default_windows'] if os.name == 'nt' and not options.virtual_input else case['other']
        baseline_matches = observation == expected
        correct = observation == case['correct']
        verdict = 'correct' if correct else 'known-defect' if baseline_matches else 'unexpected'
        row = dict(case=case['name'], component=case['component'], observation=observation,
            intended=case['correct'], pinned_baseline=expected, verdict=verdict,
            baseline_matches=baseline_matches)
        if not baseline_matches:
            row['output_tail'] = terminal.text()[-1200:]
        return row
    finally:
        terminal.close()


def main():
    if sys.argv[1:2] == ['--launch-virtual-input']:
        if os.name != 'nt':
            raise SystemExit('Virtual-terminal input flag is Windows-only.')
        return launch_windows(sys.argv[2:])
    parser = argparse.ArgumentParser()
    parser.add_argument('--virtual-input', action='store_true')
    parser.add_argument('--check-baseline', action='store_true', help='Verify known outcomes, not library correctness')
    parser.add_argument('--case', action='append', help='Limit to named cases; may repeat')
    parser.add_argument('--report', type=Path, default=Path('results/terminal.json'))
    options = parser.parse_args()
    if options.virtual_input and os.name != 'nt':
        parser.error('--virtual-input is only supported on Windows')
    if not (ROOT / '.dart_tool/package_config.json').is_file():
        raise SystemExit('Run dart pub get first.')
    dart = shutil.which('dart')
    if dart is None:
        raise SystemExit('dart not found on PATH')
    compilation = subprocess.run(
        [dart, 'compile', 'kernel', str(ROOT / 'bin/component.dart'),
         '--output=' + str(ROOT / '.dart_tool/component.dill')],
        cwd=ROOT, capture_output=True, text=True, timeout=90,
    )
    if compilation.returncode != 0:
        print(compilation.stdout)
        print(compilation.stderr, file=sys.stderr)
        raise SystemExit('The terminal probe failed to compile.')
    selected = [case for case in cases() if not options.case or case['name'] in options.case]
    if not selected or (options.case and set(options.case) - {case['name'] for case in selected}):
        parser.error('Unknown or empty case selection')
    results = []
    for case in selected:
        try:
            row = run_case(case, dart, options)
        except (RuntimeError, OSError, ValueError) as error:
            row = dict(case=case['name'], verdict='harness-error', error=str(error), baseline_matches=False)
        results.append(row)
        print(json.dumps(row, ensure_ascii=True), flush=True)
    report = dict(generated_utc=datetime.now(timezone.utc).isoformat(),
        transport='Windows ConPTY' if os.name == 'nt' else 'POSIX PTY',
        package_lock_sha256=hashlib.sha256((ROOT / 'pubspec.lock').read_bytes()).hexdigest(),
        platform=platform.platform(), python=platform.python_version(),
        dart=subprocess.check_output([dart, '--version'], text=True).strip(),
        windows_virtual_input=options.virtual_input, check_baseline=options.check_baseline,
        results=results)
    options.report.parent.mkdir(parents=True, exist_ok=True)
    options.report.write_text(json.dumps(report, indent=2, ensure_ascii=True) + '\n', encoding='utf-8')
    passed = all(row['baseline_matches'] if options.check_baseline else row['verdict'] == 'correct' for row in results)
    print(f"Saved {options.report}; {len(results)} experiments; " + ('baseline verified' if passed and options.check_baseline else 'correct behavior' if passed else 'check failed'))
    return 0 if passed else 1


if __name__ == '__main__':
    sys.exit(main())
