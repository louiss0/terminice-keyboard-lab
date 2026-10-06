import 'dart:convert';
import 'dart:io';

import 'package:mamba/executor.dart';
import 'package:mamba/mamba_cli.dart';
import 'package:terminice/terminice.dart';
import 'package:terminice_core/terminice_core.dart' show FormFieldConfig;

const labTitle = 'Keyboard lab';
const scenarioNames = [
  'text',
  'password',
  'form',
  'multiline',
  'search-filter',
  'palette',
  'confirm',
  'slider',
  'rating',
  'search',
  'checkbox',
  'grid',
  'tags',
  'choice',
];

/// Only synthetic data: never enter real credentials into this learning lab.
Object? runScenario(String name, Terminice prompt) => switch (name) {
  'text' => prompt.text(labTitle, required: false),
  'password' => prompt.password(labTitle),
  'form' => prompt.form(
    labTitle,
    fields: [FormFieldConfig(label: 'Synthetic value', required: true)],
  )?[0],
  'multiline' => prompt.multiline(labTitle),
  'search-filter' => prompt.searchSelector(
    prompt: labTitle,
    options: ['probe', 'probeX'],
    showSearch: true,
  ),
  'palette' =>
    prompt
        .commandPalette(
          labTitle,
          commands: [
            CommandEntry(id: 'probe', title: 'probe'),
            CommandEntry(id: 'probeX', title: 'probeX'),
          ],
        )
        ?.id,
  'confirm' => prompt.confirm(
    prompt: labTitle,
    message: 'Choose No',
    defaultYes: true,
  ),
  'slider' => prompt.slider(labTitle, min: 0, max: 10, initial: 5, step: 1),
  'rating' => prompt.rating(labTitle, initial: 3),
  'search' => prompt.searchSelector(
    prompt: labTitle,
    options: ['Alpha', 'Beta'],
  ),
  'checkbox' => prompt.checkboxSelector(labTitle, options: ['Alpha', 'Beta']),
  'grid' => prompt.gridSelector(
    prompt: labTitle,
    options: ['Alpha', 'Beta'],
    columns: 1,
  ),
  'tags' => prompt.tagSelector(
    prompt: labTitle,
    tags: ['Alpha', 'Beta'],
    maxContentWidth: 32,
    minColumnWidth: 24,
  ),
  'choice' => prompt.choiceSelector(
    labTitle,
    items: [ChoiceItem('Alpha'), ChoiceItem('Beta')],
    columns: 1,
  ),
  _ => throw ArgumentError.value(name, 'name', 'unknown scenario'),
};

final class RecordingScaffolder implements ProjectScaffolder {
  @override
  void scaffold(
    String packageName,
    String shortDescription, {
    required bool installDependencies,
    required bool initializeGitRepository,
  }) {
    emitResult({
      'description': shortDescription,
      'install': installDependencies,
      'git': initializeGitRepository,
    });
  }
}

/// Real Mamba prompt adapters; the only replaced boundary is project effects.
Future<void> runMamba() async {
  final result = await Executor('probe', 'Keyboard probe.', '1.0.0', [
    CreateProjectCommand(
      Directory.current,
      projectScaffolder: RecordingScaffolder(),
    ),
  ]).fake().execute(['create', 'keyboard_probe']);
  if (result is MambaFailureResult) throw StateError(result.message);
}

void emitResult(Object? value) =>
    stdout.writeln('LAB_RESULT=${jsonEncode(value)}');
