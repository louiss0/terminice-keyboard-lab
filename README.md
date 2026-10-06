# Terminice keyboard lab

An executable reproduction and learning lab for keyboard failures observed while
scaffolding projects with Mamba in Windows Terminal / PowerShell.

**This is a diagnostic repository, not a fixed fork.** It pins Mamba **0.16.0**,
Terminice **1.3.1**, and terminice_core **1.2.1**, including `pubspec.lock`.
It changes neither the installed packages nor Mamba's production code.

## What you learn

A key passes through several independent layers:

```text
key / escape sequence
  → terminal host and console input mode
  → bytes read by Dart
  → Terminice key-event decoder
  → component bindings and state
  → returned value
  → Mamba's project scaffolder
```

A successful process exit does not prove a key worked. This lab checks the
**returned text, boolean, number, or selected item** at the public boundary.

### Findings so far

| Problem | Scope | Evidence |
| --- | --- | --- |
| Missing Windows virtual-terminal input mode | Windows console byte delivery | Real ConPTY input loses arrows; enabling `0x0200` restores them |
| Byte `8` becomes generic Ctrl+H before the Backspace branch | Shared decoder, not Windows-specific | Six component contracts fail with actual byte `8` supplied |
| Standalone Escape waits for more input | Shared decoder when ESC is delivered | Real Linux, macOS, and Windows virtual-input prompts time out |
| Delete / modified-arrow sequences become Escape | Shared decoder limitation | Decoder characterization tests, not a promise that every component supports Delete |

**Verified on Windows, Linux, and macOS:** all three jobs in the
[first CI run](https://github.com/louiss0/terminice-keyboard-lab/actions/runs/37536083091)
passed, checking exact known outcomes through real pseudo-terminals. Linux/macOS
also reproduce the six byte-8 failures and three standalone-Escape waits; their
arrows and Mamba scaffolder fixture work. This does not imply identical physical
key mappings in every desktop terminal.

See [the full investigation](docs/investigation.md) for source links, caveats,
and component impact.

## Start here

Requires **Dart 3.13.2** and **Python 3.13**. Use a real terminal for manual prompts.
Python needs `pywinpty` only on Windows; POSIX probes use the standard library.

```sh
dart pub get --enforce-lockfile
python -m venv .venv
```

Install into the virtual environment, without changing global Python packages:

```powershell
# Windows / PowerShell
.\.venv\Scripts\python.exe -m pip install -r scripts/requirements.txt
```

```sh
# Linux / macOS
.venv/bin/python -m pip install -r scripts/requirements.txt
```

The following examples use `python` for brevity. Substitute your virtual
environment's interpreter above, or activate that environment first.

### 1. Understand the decoder independently of your OS

```sh
dart test --reporter expanded
```

The **30 green characterization tests** describe the pinned release, including
its bugs. Their names explicitly identify incorrect behavior. They do **not**
assert that the dependency is healthy.

Now run the desired contracts:

```sh
dart test contracts/backspace_contract.dart --reporter expanded
```

**Expected: six failures**, one each for text, password, form, multiline, search,
and command-palette input. `probeX + byte 8 + confirm` should return `probe`, but
returns `probeX`. This reproduction does not depend on your terminal keyboard.

CI verifies *exactly* those failures rather than swallowing an arbitrary exit 1:

```sh
python scripts/check_contract_failures.py
```

### 2. Measure what actually reaches Dart

```sh
python scripts/raw_probe.py --report results/raw-default.json
```

On Windows, compare an isolated console with virtual-terminal input enabled:

```sh
python scripts/raw_probe.py --virtual-input --report results/raw-virtual.json
```

Each report separates **injected** bytes from **delivered** bytes. On a legacy
Windows console path they are not necessarily identical. This is why a mocked
byte test alone cannot reproduce missing arrow delivery.

For manual observation:

```sh
dart run bin/raw.dart
```

Try Backspace, arrows, Enter, and Escape; press `q` to leave. **Never type real
passwords or secrets: the raw probe prints every received byte.**

### 3. Check components through a real pseudo-terminal

```sh
python scripts/terminal_probe.py --check-baseline --report results/terminal-default.json
```

On Windows:

```sh
python scripts/terminal_probe.py --virtual-input --check-baseline --report results/terminal-virtual.json
```

These run **27 experiments spanning 13 Terminice component APIs**, plus Mamba's
real description/install/Git prompt adapters. For Mamba, only the scaffolder is
replaced with a recorder: **no project files, dependency installs, or Git
initialization occur**.

`--check-baseline` checks the exact known correct/defective outcomes. Omitting it
instead checks intended behavior and **returns a nonzero exit code for bugs**:

```sh
# Windows default: wrong description and booleans, despite a successful prompt run.
python scripts/terminal_probe.py --case mamba

# Shared byte-8 bug, even with Windows arrow delivery corrected.
python scripts/terminal_probe.py --virtual-input --case text-bs8
```

The second command is Windows-only. On Linux/macOS, use the same case without
`--virtual-input`. Use `--case` repeatedly to select several experiments.

### 4. Try a component yourself

```sh
dart run bin/component.dart text
dart run bin/component.dart confirm
dart run bin/component.dart palette
dart run bin/component.dart mamba
```

The program emits `LAB_RESULT=<json>` after the prompt. Do not use the process
exit code alone as your observation. If Escape leaves a prompt waiting, close
that isolated session; automated probes apply a timeout and clean up the child.

## Reading path

1. [Terminal concepts and exercises](docs/concepts.md)
2. [Investigation, impact matrix, source evidence, and limits](docs/investigation.md)
3. [`test/characterization_test.dart`](test/characterization_test.dart)
4. [`contracts/backspace_contract.dart`](contracts/backspace_contract.dart)
5. [`scripts/terminal_probe.py`](scripts/terminal_probe.py)
6. [Checked-in Windows, Linux, and macOS evidence](docs/evidence/)

## Safety and interpretation

- Tests and probes use synthetic strings and read-only component fixtures.
- Virtual-input comparisons set and restore the original mode inside a child
  console. They are an experiment, **not a production workaround**.
- The CI matrix uses ConPTY on Windows and controlling POSIX PTYs on Linux/macOS.
  These are genuine terminal paths, but not physical key presses in every
  possible terminal emulator.
- Full prompt output can contain typed data. Keep fixtures synthetic.
- CI green means the **reproductions remain reproducible**, not that these
  upstream releases have been repaired.
- No upstream issue/PR is published by this repository's scripts.
