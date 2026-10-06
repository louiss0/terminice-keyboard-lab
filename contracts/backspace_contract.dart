import 'package:terminice/testing.dart';
import 'package:terminice_keyboard_lab/scenarios.dart';
import 'package:test/test.dart';

/// Desired behavior. These six tests intentionally fail on the pinned release.
/// Outside test/ so normal characterization test discovery stays explicit.
void main() {
  for (final component in [
    'text',
    'password',
    'form',
    'multiline',
    'search-filter',
    'palette',
  ]) {
    test('$component: byte-8 Backspace must edit', () {
      final tester = TerminiceTester.interactive(
        script: TerminalScript.build(
          (script) => script
              .text('probeX')
              .text('\x08')
              .text(component == 'multiline' ? '\x04' : '\r'),
        ),
      );
      expect(
        tester.run((prompt) => runScenario(component, prompt)),
        component == 'search-filter' ? ['probe'] : 'probe',
      );
    });
  }
}
