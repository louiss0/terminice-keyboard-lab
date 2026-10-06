import 'package:terminice/testing.dart';
import 'package:terminice_keyboard_lab/scenarios.dart';
import 'package:test/test.dart';

void main() {
  group(
    'Pinned decoder observations (known defects, not desired contracts)',
    () {
      for (final (bytes, expected) in <(String, KeyEventType)>[
        ('\x08', KeyEventType.ctrlGeneric),
        ('\x7f', KeyEventType.backspace),
        ('\r', KeyEventType.enter),
        ('\n', KeyEventType.enter),
        ('\x1b[C', KeyEventType.arrowRight),
        ('\x1b[D', KeyEventType.arrowLeft),
        ('\x1b[3~', KeyEventType.esc),
        ('\x1b[1;5C', KeyEventType.esc),
      ]) {
        test('bytes ${bytes.codeUnits} are classified as ${expected.name}', () {
          final tester = TerminiceTester.interactive(
            script: TerminalScript.build((script) => script.text(bytes)),
          );
          expect(tester.run((_) => KeyEventReader.read().type), expected);
        });
      }
    },
  );

  for (final component in [
    'text',
    'password',
    'form',
    'multiline',
    'search-filter',
    'palette',
  ]) {
    for (final byte in [8, 127]) {
      test(
        '$component: Backspace $byte ${byte == 8 ? 'is ignored (defect)' : 'edits correctly'}',
        () {
          final tester = TerminiceTester.interactive(
            script: TerminalScript.build(
              (script) => script
                  .text('probeX')
                  .text(String.fromCharCode(byte))
                  .text(component == 'multiline' ? '\x04' : '\r'),
            ),
          );
          final expected = byte == 8 ? 'probeX' : 'probe';
          expect(
            tester.run((prompt) => runScenario(component, prompt)),
            component == 'search-filter' ? [expected] : expected,
          );
        },
      );
    }
  }

  for (final (component, keys, expected) in <(String, String, Object)>[
    ('confirm', '\x1b[C\r', false),
    ('slider', '\x1b[C\r', 6),
    ('rating', '\x1b[C\r', 4),
    ('search', '\x1b[B\r', ['Beta']),
    ('checkbox', '\x1b[B \r', ['Beta']),
    ('grid', '\x1b[B\r', ['Beta']),
    ('tags', '\x1b[B \r', ['Beta']),
    ('choice', '\x1b[B\r', ['Beta']),
    ('text', 'ac\x1b[Db\r', 'abc'),
  ]) {
    test('$component: complete ANSI navigation works when delivered', () {
      final tester = TerminiceTester.interactive(
        script: TerminalScript.build((script) => script.text(keys)),
      );
      expect(tester.run((prompt) => runScenario(component, prompt)), expected);
    });
  }

  test('line fallback avoids the key-event decoder', () {
    final tester = TerminiceTester.fallback(lines: ['probe']);
    expect(tester.run((prompt) => prompt.text(labTitle)), 'probe');
  });
}
