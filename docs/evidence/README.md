# Preserved measurements

These JSON files are observations, not fixtures that the tests read back as
an oracle. The tests invoke the real public components and compare separately
specified intended/pinned outcomes.

## Local Windows

- `raw-windows-default.json`, `raw-windows-virtual.json`: actual delivered bytes.
- `windows-default.json`, `windows-virtual.json`: 27 prompt experiments per mode.
- Platform: Windows build 26200; Dart 3.13.2; Windows ConPTY.
- Default: 7 intended outcomes / 20 known defective outcomes.
- VT input: 18 intended outcomes / 9 known defective outcomes.

## Linux and macOS CI

- `raw-linux.json`, `terminal-linux.json`.
- `raw-macos.json`, `terminal-macos.json`.
- Source: [CI run 37536083091](https://github.com/louiss0/terminice-keyboard-lab/actions/runs/37536083091),
  lab commit `68c2d9a`, all three jobs successful.
- Downloaded from `keyboard-evidence-ubuntu-latest` and
  `keyboard-evidence-macos-latest`, without altering their contents.
- Both: 27 prompt experiments, 18 intended / 9 known defective outcomes.
- Windows Server 2025 evidence is preserved in the same run's
  `keyboard-evidence-windows-latest` artifact, including both input modes.

All reports distinguish a returned value (including JSON null) from a timeout.
The shared nine failures are six byte-8 editing cases and three lone-Escape
waits. `baseline_matches: true` is **not** a claim of correct component behavior.

Regenerate with `scripts/raw_probe.py` and `scripts/terminal_probe.py`; reports
are written to ignored `results/`. The report includes runtime/transport
metadata and, for component runs, the lockfile hash. Windows and POSIX transport
representations must not be assumed identical merely because injection is the
same.
