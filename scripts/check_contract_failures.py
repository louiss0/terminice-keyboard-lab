"""Assert precisely the six known contract failures, never blindly accept exit 1."""
import json
import shutil
import subprocess
import sys

COMPONENTS = ['text', 'password', 'form', 'multiline', 'search-filter', 'palette']
command = [shutil.which('dart') or 'dart', 'test', 'contracts/backspace_contract.dart', '--reporter=json']
result = subprocess.run(command, capture_output=True, text=True, timeout=90)
names = {}
failures = []
successes = []
finished = False
for line in result.stdout.splitlines():
    try:
        event = json.loads(line)
    except json.JSONDecodeError:
        continue
    if event.get('type') == 'testStart':
        names[event['test']['id']] = event['test']['name']
    if event.get('type') == 'testDone' and not event.get('hidden', False):
        name = names.get(event['testID'], '<unknown>')
        if event['result'] in ['failure', 'error']:
            failures.append(name)
        elif event['result'] == 'success' and not event.get('skipped', False):
            successes.append(name)
    if event.get('type') == 'done':
        finished = True
expected = sorted(f'{name}: byte-8 Backspace must edit' for name in COMPONENTS)
if result.returncode != 1 or not finished or sorted(failures) != expected or successes:
    print(result.stdout)
    print(result.stderr, file=sys.stderr)
    raise SystemExit('Unexpected contract outcome; inspect dependency or harness changes.')
print(json.dumps({'known_contract_failures': failures}, indent=2))
print('Verified exactly six real contract failures. This is not a dependency health check.')
