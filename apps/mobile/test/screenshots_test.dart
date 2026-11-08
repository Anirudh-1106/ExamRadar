// Renders real screens with real fonts to PNG files for design review (docs/screenshots).
// Run: flutter test --update-goldens --tags screenshots test/screenshots_test.dart
// Data comes from the ExamRadar API serving information collected from official sites on 2026-11-08.
@Tags(['screenshots'])
library;

import 'dart:convert';
import 'dart:io';

import 'package:examradar/api/models.g.dart';
import 'package:examradar/data/api.dart';
import 'package:examradar/data/state.dart';
import 'package:examradar/l10n/strings.dart';
import 'package:examradar/screens/calendar.dart';
import 'package:examradar/screens/exam_detail.dart';
import 'package:examradar/screens/exams.dart';
import 'package:examradar/screens/home.dart';
import 'package:examradar/screens/onboarding.dart';
import 'package:examradar/theme.dart';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:intl/date_symbol_data_local.dart';
import 'package:shared_preferences/shared_preferences.dart';

import 'widgets_test.dart' show FakeDb;

const fonts = 'C:/Users/HP/Downloads/flutter_windows_3.27.3-stable/flutter/bin/cache/artifacts/material_fonts';

Future<void> loadFonts() async {
  final roboto = FontLoader('Roboto');
  for (final f in ['roboto-regular.ttf', 'roboto-medium.ttf', 'roboto-bold.ttf', 'roboto-italic.ttf', 'roboto-black.ttf']) {
    roboto.addFont(Future.value(ByteData.sublistView(File('$fonts/$f').readAsBytesSync())));
  }
  await roboto.load();
  final icons = FontLoader('MaterialIcons')
    ..addFont(Future.value(ByteData.sublistView(File('$fonts/materialicons-regular.otf').readAsBytesSync())));
  await icons.load();
}

dynamic fx(String n) => jsonDecode(File('test/fixtures/$n').readAsStringSync());

class FakeSaved extends SavedNotifier {
  FakeSaved(this.m);
  final Map<int, SavedEntry> m;
  @override
  Future<Map<int, SavedEntry>> build() async => m;
}

void main() {
  late SharedPreferences prefs;
  final detail = ExamDetail.fromJson(fx('exam_detail.json') as Map<String, dynamic>);
  final open = PageExamSummary.fromJson(fx('exams_open.json') as Map<String, dynamic>);
  final notices = PageNoticeOut.fromJson(fx('notices.json') as Map<String, dynamic>);
  final calendar = (fx('calendar_nov.json') as List).map((e) => CalendarEntry.fromJson(e as Map<String, dynamic>)).toList();

  setUpAll(() async {
    await loadFonts();
    await initializeDateFormatting('en_IN');
    SharedPreferences.setMockInitialValues({'onboarded': true});
    prefs = await SharedPreferences.getInstance();
  });

  Future<void> shoot(WidgetTester t, Widget screen, String name, {Brightness b = Brightness.light, bool large = false}) async {
    t.view.physicalSize = const Size(1080, 2340);
    t.view.devicePixelRatio = 2.625;
    addTearDown(t.view.reset);
    await t.pumpWidget(
      ProviderScope(
        overrides: [
          prefsStoreProvider.overrideWithValue(prefs),
          dbProvider.overrideWithValue(FakeDb()),
          savedProvider.overrideWith(() => FakeSaved({detail.id: SavedEntry(detail.id, 'interested', DateTime(2026, 11, 8), detail)})),
          examsProvider.overrideWith((ref, q) async => Fetched(open)),
          noticesProvider.overrideWith((ref) async => Fetched(notices)),
          examDetailProvider.overrideWith((ref, id) async => Fetched(detail)),
          checklistProvider.overrideWith(
            (ref, id) async => Fetched(
              ChecklistOut(
                items: [
                  ChecklistItemOut(
                    key: 'read',
                    text: 'Read the official notification fully, including eligibility and instructions.',
                    done: true,
                  ),
                  ChecklistItemOut(
                    key: 'otr',
                    text: 'Check your One Time Registration profile on Thulasi (name, date of birth, photo, signature).',
                    done: false,
                  ),
                  ChecklistItemOut(
                    key: 'apply',
                    text: 'Apply before the last date (02 Dec 2026).',
                    due: DateTime(2026, 12, 2),
                    certainty: 'official',
                    done: false,
                  ),
                ],
                photoSpecs: const [],
                certificateRules: const [],
                note: 'Steps come from the official dates we have verified.',
              ),
            ),
          ),
          calendarProvider.overrideWith((ref, q) async => Fetched(calendar)),
          profileProvider.overrideWith(() => _NoProfile()),
        ],
        child: LangScope(
          lang: 'en',
          child: MaterialApp(
            debugShowCheckedModeBanner: false,
            theme: buildTheme(Brightness.light, fontFamily: 'Roboto'),
            darkTheme: buildTheme(Brightness.dark, fontFamily: 'Roboto'),
            themeMode: b == Brightness.dark ? ThemeMode.dark : ThemeMode.light,
            builder:
                (c, child) => MediaQuery(data: MediaQuery.of(c).copyWith(textScaler: TextScaler.linear(large ? 1.3 : 1)), child: child!),
            home: screen,
          ),
        ),
      ),
    );
    await t.pumpAndSettle();
    await expectLater(find.byType(MaterialApp), matchesGoldenFile('../../../docs/screenshots/$name.png'));
  }

  testWidgets('home', (t) => shoot(t, const HomeScreen(), 'home'));
  testWidgets('exams', (t) => shoot(t, const ExamsScreen(), 'exams'));
  testWidgets('detail', (t) => shoot(t, const ExamDetailScreen(id: 1), 'exam_detail'));
  testWidgets('detail dark', (t) => shoot(t, const ExamDetailScreen(id: 1), 'exam_detail_dark', b: Brightness.dark));
  testWidgets('calendar', (t) => shoot(t, const CalendarScreen(), 'calendar'));
  testWidgets('onboarding large text', (t) => shoot(t, const OnboardingScreen(), 'onboarding_large_text', large: true));
}

class _NoProfile extends ProfileNotifier {
  @override
  Future<ProfileData?> build() async => null;
}
