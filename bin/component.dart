import 'dart:io';

import 'package:terminice/terminice.dart';
import 'package:terminice_keyboard_lab/scenarios.dart';

Future<void> main(List<String> arguments) async {
  if (arguments.length != 1 ||
      !(scenarioNames.contains(arguments.single) ||
          arguments.single == 'mamba')) {
    stderr.writeln(
      'Usage: dart run bin/component.dart <${[...scenarioNames, 'mamba'].join('|')}>',
    );
    exitCode = 64;
    return;
  }
  if (arguments.single == 'mamba') {
    await runMamba();
  } else {
    emitResult(runScenario(arguments.single, terminice));
  }
}
