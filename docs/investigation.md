# Keyboard investigation

## Question and pinned subject

Are Mamba's Windows scaffolding keyboard failures Windows-only, and are other
Terminice components affected?

Investigated versions: Mamba **0.16.0**, Terminice **1.3.1**, terminice_core
**1.2.1**, Dart **3.13.2**. The lockfile fixes the transitive graph.

Upstream source anchor: Terminice v1.3.1 commit
[`c52995883247585636a660a025ac5323975799d0`](https://github.com/jozzdart/terminice/tree/c52995883247585636a660a025ac5323975799d0).
The installed `key_events.dart` has Git blob
`1ece1d005b0050548c3e4add8b0d1cbe14d1a72e`, identical to that commit's file.
No dependency source or cache files were modified.

## Answer

**There is a Windows-specific delivery problem and independent shared decoder
problems. They must not be collapsed into one 'Windows bug'.**

1. **Windows mode setup:** rich mode disables echo/line input but does not enable
   virtual-terminal input. Basic arrows do not reach Dart as the sequences the
   dependency expects in the tested default ConPTY configuration.[S1][S2]
2. **Byte-8 Backspace:** shared branch ordering returns generic Ctrl+H instead
   of Backspace. This is independent of platform once byte `8` reaches the
   reader.[S3] Six public component contracts reproduce it.
3. **Lone Escape:** the shared decoder performs blocking lookahead, not a timed
   peek. Real Linux, macOS, and Windows VT-enabled input reproduce the wait;
   scripted EOF-based input conceals it.[S1][S3][S4]
4. **Unsupported sequence grammar:** Delete (`ESC [ 3 ~`) and modified Right
   (`ESC [ 1 ; 5 C`) return an Escape event in decoder tests. This is a shared
   limitation, not evidence that every widget advertises Delete support.[S3]

All three CI jobs passed, with real-terminal evidence confirming both shared
failures on Linux/macOS as well as Windows. See the runtime evidence below.
A universal physical Backspace or Enter mapping cannot be inferred from these
tests.

## Local runtime evidence: Windows

Environment: Windows build **26200**, Dart **3.13.2**, real **ConPTY** input,
40 rows × 120 columns. Each experiment uses a new child pseudo-console, with
actual production stdin/terminal control and public prompt APIs.

### Transport observations

| Injected input | Default delivered bytes | With Windows VT input |
| --- | --- | --- |
| BS `8` | `127` | `8` |
| DEL `127` | `8` | `127` |
| Right `27,91,67` | none | `27,91,67` |
| Left `27,91,68` | none | `27,91,68` |
| Down `27,91,66` | none | `27,91,66` |
| Delete `27,91,51,126` | none | `27,91,51,126` |
| CR `13` | `13` | `13` |
| LF `10` | none | `10` |
| Lone Esc `27` | none | `27` |

These are **measurements of the selected ConPTY injection path**, not a promise
that pressing a physical key always sends the injected representation.
Microsoft documents that `ENABLE_VIRTUAL_TERMINAL_INPUT` enables conversion to
sequences readable through ReadFile/ReadConsole; output ANSI processing is a
separate mode.[S2]

The inversion of injected `8` and `127` on the default path explains why a
scripted Backspace can disagree with the real console. Track both sides of the
transport boundary rather than assuming injection equals delivery.

### Public results

- **27 real-terminal experiments in default Windows input:** 7 intended outcomes,
  20 known defective outcomes; all matched the explicit pinned baseline.
- **27 with isolated Windows virtual input enabled:** 18 intended outcomes,
  9 known defective outcomes (six byte-8 cases plus three lone-Escape waits).
- **30 characterization tests pass.**
- **Six desired Backspace contracts fail**, independently of console mode.
- Baseline Mamba returns `{"description":"probeX","install":true,"git":false}`
  where the intended result is `{"description":"probe","install":false,"git":true}`.
- Enabling virtual input makes that same Mamba sequence return the intended
  values. It does **not** repair the separate byte-8 or Escape defects.

Mamba runs its real `TerminiceDescriptionPrompt`, `TerminiceInstallPrompt`, and
`TerminiceGitPrompt`. A recording `ProjectScaffolder` replaces only file-system,
package-install, and Git side effects.[S5]

Checked-in measurements are under [evidence/](evidence/); regenerable reports
are written to ignored `results/`. Reports distinguish returned JSON null from
a timeout, and compare values rather than process exit success.

## Component impact

**Measured** means exercised through public component APIs in this repository.
**Source-predicted** means its rich path shares the implicated infrastructure,
but a component-specific runtime assertion is not included. Do not turn the
second category into a claim of exhaustive end-to-end coverage.

| API / component | Byte-8 editing | Arrow delivery | Evidence level |
| --- | --- | --- | --- |
| `text` | Ignored | Cursor movement lost on default Windows | Measured |
| `password` | Ignored | Uses shared text bindings | Editing measured; cursor effect source-predicted |
| `form` | Ignored | Field/cursor navigation uses shared events | Editing measured; navigation source-predicted |
| `multiline` | Ignored | Uses shared events for line/cursor movement | Editing measured; navigation source-predicted |
| `searchSelector` | Query editing ignored | Selection movement lost | Both measured |
| `commandPalette` | Query editing ignored | Ranked-list movement uses shared events | Editing measured; arrows source-predicted |
| `confirm` | Not an editing control | Choice remains default | Measured |
| `slider` | Not an editing control | Value remains initial | Measured |
| `rating` | Not an editing control | Value remains initial | Measured |
| `checkboxSelector` | Not an editing control | Wrong focused option toggled | Measured |
| `gridSelector` | Not an editing control | Selection remains first item | Measured |
| `tagSelector` | Not an editing control | Wrong focused tag toggled | Measured |
| `choiceSelector` | Not an editing control | Selection remains first card | Measured |
| `toggleGroup` | Not an editing control | Focus navigation implicated | Source-predicted [S6] |
| `range` | Not an editing control | RangeValuePrompt movement implicated | Source-predicted [S6] |
| `date`, `datePicker` | Not general text inputs | Date-field/calendar adjustment implicated | Source-predicted [S6] |
| `colorPicker` | Hex entry uses a text buffer | Color-grid movement implicated | Source-predicted [S6] |
| `pathPicker` | Not a general text input | DynamicListPrompt movement implicated | Source-predicted [S6] |
| `filePicker` | Delegated searchable-list query editing implicated | Delegated searchable-list navigation implicated | Source-predicted [S6] |
| `configEditor` and nested editor fields | Search/text editors implicated | Main loop directly uses KeyEventReader | Source-predicted [S6] |
| Flow/custom-component wrappers | Depends on invoked component | Depends on implementation | No independent blanket claim |
| Output-only indicators, spinners, progress rendering | No key reads needed | No key reads needed | These input defects do not establish an output defect |
| Line-mode fallback / unattended execution | Avoids rich event decoder | Different/no interaction contract | Line fallback tested; not a rich-mode repair [S7] |

Shared Escape/CSI limitations apply when a component receives that event through
the core reader, but cancellation semantics vary by component. The real terminal
Escape assertions here cover text, confirmation, and searchable selection only.

## Why mocks hid important parts

The official mock Backspace helper queues `127`, which takes the working decoder
branch. An explicit `.text('\x08')` reaches the faulty branch.[S4]

For exhausted mock input, a synchronous byte read returns EOF. Production input
from an open terminal waits. `sleep(30 ms)` followed by blocking reads does not
bound that wait, so a mock lone-Escape test can pass without verifying the
real-terminal behavior.[S1][S3][S4]

## Enter: what is and is not established

CR `13` successfully submitted all normal local prompt fixtures. LF `10` was
not delivered through the default Windows input path, but worked with VT input.
The decoder itself recognizes both.[S3]

**The original report of physical Enter failing everywhere is not fully
explained.** The user may have a distinct key mapping, inherited mode, or
terminal interaction; none has been proven. Do not state that fixing the
confirmed arrow/Backspace bugs necessarily fixes every Enter complaint.
Capturing the actual terminal's delivered bytes is the next discriminating
experiment.

## Cross-platform runtime evidence

The workflow runs the same byte/component tests and real terminal probe on
`ubuntu-latest`, `macos-latest`, and `windows-latest`, plus Windows VT comparison.
Each job uploads JSON evidence even on failure.

Verified by [run 37536083091](https://github.com/louiss0/terminice-keyboard-lab/actions/runs/37536083091)
at lab commit `68c2d9a`: **all three jobs passed**, with no unexpected outcomes.

| Runtime/input mode | Experiments | Intended outcomes | Known defective outcomes |
| --- | --- | --- | --- |
| Linux PTY (kernel 6.17, glibc 2.39) | 27 | 18 | 9 |
| macOS 26.6.2 arm64 PTY | 27 | 18 | 9 |
| Windows Server 2025 ConPTY, default | 27 | 7 | 20 |
| Windows Server 2025 ConPTY, VT input | 27 | 18 | 9 |

Across these four paths, **108 real prompt experiments** matched their explicit
baselines. Each OS also passed 30 characterization tests and verified exactly
six failing desired contracts. Green CI means the diagnosis reproduced, not
that the pinned dependency is fixed.

Linux/macOS's nine known failures are the six byte-8 editing cases and three
lone-Escape waits. All basic-arrow fixtures work, as does the Mamba fixture
using DEL `127`. Both CR and LF fixtures submit successfully. Raw measurements
show injected CR `13` arriving as LF `10` on those POSIX PTYs; disabling line
mode does not eliminate every inherited input translation.

The checked-in [Linux raw](evidence/raw-linux.json), [Linux prompts](evidence/terminal-linux.json),
[macOS raw](evidence/raw-macos.json), and [macOS prompts](evidence/terminal-macos.json)
reports preserve the actual CI observations. Windows runner evidence is also
available in the run's uploaded artifacts; local Windows comparisons are
checked in separately.

The physical frequency of byte `8` on different emulators remains outside the
claim. A common DEL-producing Backspace can work on Unix while Ctrl+H/BS still
exercises the shared defect. Missing Windows virtual-input setup is specific to
the Windows console API path; the core byte-8 and Escape faults are not.

## Proposed repair boundaries (not implemented)

- Establish/restore required Windows console input mode with checked errors and
  capability detection; do not overwrite unrelated flags.[S2]
- Recognize BS `8` before generic Ctrl letters, with permanent `8`/`127` tests.
- Replace blocking escape lookahead with bounded incremental parsing that
  tolerates fragmented input and handles unknown CSI sequences deliberately.
- Retain real terminal tests: returned values and cancellation latency matter.
- If chosen instead, make a Windows line fallback explicit to callers. It trades
  rich interaction for OS-managed line editing; this lab does not change Mamba
  to use it.

No dependency fork, FFI adapter, upstream issue, or production fallback is
created automatically by this lab.

## Primary sources

[S1] [Pinned core terminal control](https://github.com/jozzdart/terminice/blob/c52995883247585636a660a025ac5323975799d0/terminice_core/lib/src/io/terminal_control.dart): `enterRaw`, `TerminalModeState.restore`, `tryReadNextByte`.

[S2] [Microsoft SetConsoleMode](https://learn.microsoft.com/en-us/windows/console/setconsolemode): separate line, echo, processed, and VT input flags; return/error handling.

[S3] [Pinned core key decoder](https://github.com/jozzdart/terminice/blob/c52995883247585636a660a025ac5323975799d0/terminice_core/lib/src/io/key_events.dart): Enter classification, generic Ctrl precedence, Backspace, and two-byte escape lookahead.

[S4] [Pinned official mock terminal](https://github.com/jozzdart/terminice/blob/c52995883247585636a660a025ac5323975799d0/terminice_core/lib/src/testing/mock_terminal.dart) and [terminal script](https://github.com/jozzdart/terminice/blob/c52995883247585636a660a025ac5323975799d0/terminice_core/lib/src/testing/terminal_script.dart): injected bytes, Backspace helper, exhausted input.

[S5] [Mamba v0.16.0 prompt adapters and create command](https://github.com/louiss0/mamba/blob/v0.16.0/lib/mamba_cli.dart): direct library calls and injectable scaffolder.

[S6] [Pinned prompt sources](https://github.com/jozzdart/terminice/tree/c52995883247585636a660a025ac5323975799d0/terminice/lib/src/prompts), [selectors](https://github.com/jozzdart/terminice/tree/c52995883247585636a660a025ac5323975799d0/terminice/lib/src/selectors), [pickers](https://github.com/jozzdart/terminice/tree/c52995883247585636a660a025ac5323975799d0/terminice/lib/src/pickers), [editor loop](https://github.com/jozzdart/terminice/blob/c52995883247585636a660a025ac5323975799d0/terminice/lib/src/config_editor/editor_loop.dart), [core prompts](https://github.com/jozzdart/terminice/tree/c52995883247585636a660a025ac5323975799d0/terminice_core/lib/src/prompt), and [PromptRunner](https://github.com/jozzdart/terminice/blob/c52995883247585636a660a025ac5323975799d0/terminice_core/lib/src/rendering/prompt_runner.dart): component delegation and shared event consumption.

[S7] [Execution-mode policy](https://github.com/jozzdart/terminice/blob/c52995883247585636a660a025ac5323975799d0/terminice/lib/src/core/terminice_config.dart) and [fallback selection](https://github.com/jozzdart/terminice/blob/c52995883247585636a660a025ac5323975799d0/terminice/lib/src/core/fallback_selection.dart).

[S8] [Dart Stdin.lineMode](https://api.dart.dev/dart-io/Stdin/lineMode.html), [POSIX terminal interface](https://pubs.opengroup.org/onlinepubs/9799919799/basedefs/V1_chap11.html), [RFC 20 ASCII](https://www.rfc-editor.org/rfc/rfc20): terminal mode semantics and byte names, not emulator-specific key guarantees.
