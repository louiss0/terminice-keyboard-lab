# Terminal concepts, from a key to a result

## 1. The shell is not the terminal host

PowerShell launches the application. Windows Terminal hosts the screen and
input connection. ConPTY is the Windows pseudo-console path used by this lab.
Dart then reads from the application's console input.

Changing shells does not repair a decoder or automatically enable the input
mode that a raw-key application requires. A shell can influence inherited
settings, but the dependency must establish the modes it actually needs.

**Exercise:** run `bin/component.dart confirm` from two shells under the same
terminal. Record the returned boolean, not just whether Enter exits the prompt.

## 2. Canonical/line mode and raw-style input are different contracts

In line mode, the system commonly buffers a whole line and performs editing.
The application may never see Backspace as a byte. On POSIX, disabling `ICANON`
changes to noncanonical input; erase/kill processing no longer performs that
editing. Dart exposes this through `stdin.lineMode`.[1][2] Disabling line mode is not the
same as clearing every input translation: the Linux/macOS raw reports show
injected CR `13` still arriving as LF `10`.

In a rich prompt, the application reads keys as they arrive and owns editing.
Disabling echo stops the system from printing each typed character; it does not
teach an event decoder what a Backspace byte means.

On Windows, disabling line/echo mode also does **not** imply enabling virtual
terminal input. `ENABLE_VIRTUAL_TERMINAL_INPUT` (`0x0200`) is a separate input
flag. ANSI output processing is a different flag on a different handle.[3]

**Exercise:** compare raw-default and raw-virtual reports on Windows. Explain
why perfectly rendered ANSI colors prove nothing about arrow input.

## 3. A key is not necessarily one byte

Typical byte representations:

| Meaning | Bytes | Notation |
| --- | --- | --- |
| Backspace convention A | `8` | BS / Ctrl+H / `0x08` |
| Backspace convention B | `127` | DEL / `0x7f` |
| Enter convention A | `13` | CR / `\r` |
| Enter convention B | `10` | LF / `\n` |
| Right arrow, common CSI form | `27 91 67` | `ESC [ C` |
| Delete, common CSI form | `27 91 51 126` | `ESC [ 3 ~` |
| Modified right arrow example | `27 91 49 59 53 67` | `ESC [ 1 ; 5 C` |

ASCII names describe character codes, not an invariant physical-key mapping.[4]
The key labeled Delete is not the same thing as receiving ASCII DEL. Terminals
can use other encodings or negotiation modes; this table is not exhaustive.

**Exercise:** predict `probeX + BS + Enter`, then compare byte `8` with `127` in
both unit tests and real terminal reports. Explain why enabling Windows VT
input can fix the common injected-DEL path without repairing the byte-8 bug.

## 4. Branch order is observable behavior

The pinned decoder checks generic control codes `1..26` **before** checking
Backspace. Thus byte `8` becomes Ctrl+H; the later `byte == 8` condition is
unreachable.[5]

Several components use the same event decoder. Text, password, multiline,
forms, searchable lists, and ranked palettes all ignore that Ctrl+H event for
editing. This is one shared defect, not six independent prompt implementations.

**Exercise:** run the six red contracts. Find the earliest shared layer that
can explain all six. Why would a Mamba-only parser change be the wrong fix?

## 5. Escape requires a streaming parser, not blocking 'peeks'

A standalone Esc and an arrow sequence both start with `27`. A decoder must
wait briefly for a continuation without blocking indefinitely when it never
arrives. An initial 30 ms sleep is **not** a timeout on later reads.

The pinned decoder calls `tryReadNextByte()` twice. Despite the method name,
the production implementation calls synchronous `readByteSync()`; catching an
exception does not make that read nonblocking.[5][6]

Mock input returns EOF immediately once queued bytes are exhausted. A real,
open terminal waits for future input. That difference hides the lone-Escape
problem in many tests.

A streaming decoder must also handle sequence lengths and fragmentation.
Reading only `ESC [` plus one byte recognizes basic arrows, but misclassifies
`ESC [ 3 ~` and `ESC [ 1 ; 5 C` as Escape. This is distinct from not receiving
those bytes in the first place.

**Exercise:** explain why Delete can appear inert on one input path and cancel
a prompt on another. Identify which observation is about transport and which
is about unsupported decoder grammar. Do not infer a Delete feature contract
from the existence of a physical key.

## 6. Three complementary test layers

1. **Decoder tests:** supply exact bytes and assert event types. Good for branch
   order and grammar; cannot prove OS input delivery.
2. **Public component tests:** supply bytes through Terminice's official testing
   API and assert returned values. Good for impact; mock EOF can hide blocking.
3. **Real terminal tests:** run the actual process inside a pseudo-terminal,
   inject sequences, assert real results, and use a bounded timeout. Good for
   mode setup and blocking; still not every physical emulator/keybinding.

This lab runs all three. Its separate red contracts express desired behavior;
green characterization tests preserve the current diagnosis explicitly.

**Exercise:** remove `--check-baseline` from a terminal command. Why should it
now fail even though the application's own process successfully completed?

## 7. Fix layers separately

A future upstream repair needs at least:

- Windows input mode capability checks, enabling the needed flag, and restoring
  the **entire original mode** on every normal/error exit.
- Correct Backspace classification before generic Ctrl handling, with both
  `8` and `127` in permanent tests.
- Bounded, incremental escape-sequence parsing without blocking pseudo-peeks.
- Explicit behavior for unsupported CSI sequences and modified keys.
- Real terminal regressions, plus scripted component tests.

Line-mode fallback avoids the raw decoder by letting the terminal perform line
editing. It trades away the rich UI; it is an explicit product decision, not a
hidden fix implemented by this lab.

## Primary references

[1] [Dart Stdin.lineMode](https://api.dart.dev/dart-io/Stdin/lineMode.html).
[2] [POSIX General Terminal Interface, canonical/noncanonical input](https://pubs.opengroup.org/onlinepubs/9799919799/basedefs/V1_chap11.html#tag_11_01_06).
[3] [Microsoft SetConsoleMode](https://learn.microsoft.com/en-us/windows/console/setconsolemode).
[4] [RFC 20, ASCII](https://www.rfc-editor.org/rfc/rfc20).
[5] [Pinned Terminice key decoder](https://github.com/jozzdart/terminice/blob/c52995883247585636a660a025ac5323975799d0/terminice_core/lib/src/io/key_events.dart).
[6] [Pinned terminal control and lookahead](https://github.com/jozzdart/terminice/blob/c52995883247585636a660a025ac5323975799d0/terminice_core/lib/src/io/terminal_control.dart).
