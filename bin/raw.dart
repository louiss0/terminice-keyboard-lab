import 'dart:convert';
import 'dart:io';

/// Inspect actual delivered bytes, before Terminice classifies them.
/// WARNING: prints typed data. Use only synthetic input, never passwords.
Future<void> main() async {
  if (!stdin.hasTerminal) {
    stderr.writeln('This probe requires a real terminal or pseudo-terminal.');
    exitCode = 64;
    return;
  }
  final echo = stdin.echoMode;
  final line = stdin.lineMode;
  try {
    stdin.echoMode = false;
    stdin.lineMode = false;
    stdout.writeln('RAW_READY (q quits; only use synthetic input)');
    await stdout.flush();
    while (true) {
      final byte = stdin.readByteSync();
      stdout.writeln('RAW_BYTE=${jsonEncode(byte)}');
      await stdout.flush();
      if (byte == 113 || byte < 0) break;
    }
  } finally {
    stdin.echoMode = echo;
    stdin.lineMode = line;
  }
}
