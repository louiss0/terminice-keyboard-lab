"""Record delivered bytes before the Terminice decoder. Synthetic input only."""
import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import platform
import shutil
import subprocess
import time

from terminal_probe import ROOT, Terminal

KEYS = {
    'backspace-8': '\x08', 'backspace-127': '\x7f',
    'right': '\x1b[C', 'left': '\x1b[D', 'down': '\x1b[B',
    'delete': '\x1b[3~', 'enter-cr': '\r', 'enter-lf': '\n', 'escape': '\x1b',
}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--virtual-input', action='store_true')
    parser.add_argument('--report', type=Path, default=Path('results/raw.json'))
    options = parser.parse_args()
    if options.virtual_input and os.name != 'nt':
        parser.error('--virtual-input is Windows-only')
    dart = shutil.which('dart')
    if dart is None:
        raise SystemExit('dart not found')
    image = ROOT / '.dart_tool/raw.dill'
    subprocess.run([dart, 'compile', 'kernel', str(ROOT / 'bin/raw.dart'),
        '--output=' + str(image)], cwd=ROOT, check=True, timeout=90)
    results = []
    for name, keys in KEYS.items():
        terminal = Terminal([dart, str(image)], options.virtual_input)
        try:
            if not terminal.wait('RAW_READY', 20):
                raise RuntimeError('Raw terminal did not start: ' + terminal.text()[-800:])
            terminal.send(keys)
            time.sleep(0.2)
            terminal.send('q')
            if not terminal.wait('RAW_BYTE=113', 3):
                raise RuntimeError('Raw terminal did not process sentinel: ' + terminal.text()[-800:])
            received = [int(line.split('RAW_BYTE=', 1)[1])
                for line in terminal.text().splitlines() if 'RAW_BYTE=' in line]
            if not received or received[-1] != 113:
                raise RuntimeError('Sentinel missing or bytes reordered')
            row = dict(key=name, injected_bytes=list(keys.encode('utf-8')),
                delivered_bytes=received[:-1])
            results.append(row)
            print(json.dumps(row), flush=True)
        finally:
            terminal.close()
    report = dict(generated_utc=datetime.now(timezone.utc).isoformat(),
        transport='Windows ConPTY' if os.name == 'nt' else 'POSIX PTY',
        platform=platform.platform(), windows_virtual_input=options.virtual_input, results=results)
    options.report.parent.mkdir(parents=True, exist_ok=True)
    options.report.write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
    print(f'Saved {options.report}; measurements, not a dependency correctness assertion.')


if __name__ == '__main__':
    main()
