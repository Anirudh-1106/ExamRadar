// Widget tests. Fixture JSON in test/fixtures was captured from the ExamRadar API serving data collected from
// keralapsc.gov.in on 2026-11-08; it is real official data, not invented.
import 'dart:convert';
import 'dart:io';

import 'package:drift/drift.dart' show QueryExecutor;
import 'package:examradar/api/models.g.dart';
import 'package:examradar/app.dart';
import 'package:examradar/data/api.dart';
import 'package:examradar/data/local_db.dart';
import 'package:examradar/data/state.dart';
import 'package:examradar/l10n/strings.dart';
import 'package:examradar/screens/exam_detail.dart';
import 'package:examradar/screens/tools.dart';
import 'package:examradar/theme.dart';
import 'package:examradar/widgets/common.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:intl/date_symbol_data_local.dart';
import 'package:shared_preferences/shared_preferences.dart';

Map<String, dynamic> fixture(String name) => jsonDecode(File('test/fixtures/$name').readAsStringSync()) as Map<String, dynamic>;

class _NoExecutor implements QueryExecutor {
  @override
  dynamic noSuchMethod(Invocation i) => throw UnsupportedError('database not used in widget tests');
}

class FakeDb extends LocalDb {
  FakeDb() : super(_NoExecutor());
  final saved = <SavedRow>[];
  @override
  Future<List<SavedRow>> savedRows() async => saved;
  @override
  Future<Set<String>> checked(int examId) async => {};
  @override
  Future<Map<String, dynamic>?> getJson(String key) async => null;
  @override
  Future<void> upsertSaved(int id, {String? status, String? snapshot}) async =>
      saved.add(SavedRow(id, status, DateTime(2026, 11, 8), snapshot));
}

Widget host(Widget child, List overrides) => ProviderScope(
  overrides: [...overrides],
  child: LangScope(lang: 'en', child: MaterialApp(theme: buildTheme(Brightness.light), home: child)),
);

void main() {
  setUpAll(() async {
    await initializeDateFormatting('en_IN');
    SharedPreferences.setMockInitialValues({'onboarded': true});
  });

  test('every English string has a Malayalam translation', () {
    for (final key in ['navHome', 'applyOfficial', 'cert_official', 'disclaimerFull', 'v_suspicious', 'deleteConfirm', 'noSpec']) {
      expect(translate('ml', key), isNot(translate('en', key)), reason: key);
    }
    expect(translate('en', 'daysLeft', {'n': 5}), '5 days left');
  });

  test('deep links map to app routes', () {
    expect(deepLinkToPath('examradar://exam/12?tab=changes'), '/exam/12?tab=changes');
    expect(deepLinkToPath('examradar://alerts'), '/alerts');
    expect(deepLinkToPath('examradar://notice/5'), '/notices');
  });

  test('name and age helpers', () {
    expect(nameDifferences('ANU K', 'Anu K.'), isEmpty);
    expect(nameDifferences('ANU K', 'K ANU'), ['word order']);
    expect(nameDifferences('ANU KRISHNA', 'ANU K'), contains('initials'));
    expect(ageParts(DateTime(2000, 3, 10), DateTime(2026, 1, 1)), (25, 9, 22));
  });

  test('generated models parse real API output', () {
    final d = ExamDetail.fromJson(fixture('exam_detail.json'));
    expect(d.organisation.key, 'kerala_psc');
    final end = d.events.firstWhere((e) => e.eventType == 'application_end');
    expect(end.dateStart, DateTime(2026, 12, 2));
    expect(end.certainty, 'official');
    expect(end.evidence!.sourceUrl, startsWith('https://keralapsc.gov.in/'));
    expect(d.apply!.copyText, '162/2026');
    expect(ExamDetail.fromJson(d.toJson()).title, d.title);
  });

  testWidgets('certainty tags explain themselves', (t) async {
    await t.pumpWidget(host(const Scaffold(body: Row(children: [CertaintyTag('official'), CertaintyTag('expected')])), []));
    expect(find.text('Official'), findsOneWidget);
    expect(find.text('Estimate'), findsOneWidget);
    await t.tap(find.text('Estimate'));
    await t.pumpAndSettle();
    expect(find.textContaining('Not a real deadline'), findsOneWidget);
  });

  testWidgets('exam tile shows deadline with certainty', (t) async {
    final page = PageExamSummary.fromJson(fixture('exams_page.json'));
    await t.pumpWidget(host(Scaffold(body: ExamTile(page.items.first, onTap: () {})), []));
    expect(find.textContaining('Laboratory Assistant'), findsOneWidget);
    expect(find.text('Last date to apply'), findsOneWidget);
    expect(find.text('Official'), findsOneWidget);
  });

  testWidgets('exam detail shows apply link, dated evidence and disclaimer', (t) async {
    final prefs = await SharedPreferences.getInstance();
    final d = ExamDetail.fromJson(fixture('exam_detail.json'));
    final db = FakeDb();
    await t.pumpWidget(
      host(const ExamDetailScreen(id: 1), [
        prefsStoreProvider.overrideWithValue(prefs),
        dbProvider.overrideWithValue(db),
        examDetailProvider.overrideWith((ref, id) async => Fetched(d)),
        checklistProvider.overrideWith(
          (ref, id) async => Fetched(ChecklistOut(items: const [], photoSpecs: const [], certificateRules: const [], note: 'note')),
        ),
      ]),
    );
    await t.pumpAndSettle();
    expect(find.text('Apply on the official website'), findsOneWidget);
    expect(find.text('thulasi.psc.kerala.gov.in'), findsOneWidget);
    expect(find.textContaining('162/2026'), findsWidgets);
    await t.scrollUntilVisible(find.textContaining('Last date to apply'), 300);
    expect(find.textContaining('Last date to apply'), findsWidgets);
    await t.ensureVisible(find.text('Source').first);
    await t.pumpAndSettle();
    await t.tap(find.text('Source').first);
    await t.pumpAndSettle();
    expect(find.textContaining('From the official document'), findsOneWidget);
    await t.scrollUntilVisible(find.textContaining('not affiliated'), 400);
    expect(find.textContaining('not affiliated'), findsOneWidget);
  });
}
