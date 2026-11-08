import 'dart:convert';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:intl/date_symbol_data_local.dart';
import 'package:shared_preferences/shared_preferences.dart';

import 'api/models.g.dart';
import 'app.dart';
import 'config.dart';
import 'data/local_db.dart';
import 'data/state.dart';
import 'l10n/strings.dart';
import 'services/notifications.dart';

Future<void> main() async {
  WidgetsFlutterBinding.ensureInitialized();
  await initializeDateFormatting('en_IN');
  await initializeDateFormatting('ml');
  final prefs = await SharedPreferences.getInstance();
  final db = LocalDb();
  final initialLink = await AlertService.instance.init();

  late final ProviderContainer container;
  container = ProviderContainer(
    overrides: [
      prefsStoreProvider.overrideWithValue(prefs),
      dbProvider.overrideWithValue(db),
      routerProvider.overrideWith((ref) => buildRouter(ref, initial: initialLink)),
    ],
  );
  AlertService.instance.onOpen = (link) => container.read(routerProvider).push(deepLinkToPath(link));

  runApp(UncontrolledProviderScope(container: container, child: const ExamRadarApp()));
  _background(container);
}

/// After the first frame: register anonymously, send the push token, refresh saved exams, and reschedule reminders.
Future<void> _background(ProviderContainer c) async {
  final ref = c.read(_refProvider);
  await ensureRegistered(ref);
  final api = c.read(apiProvider);
  if (c.read(settingsProvider).token != null) {
    api.updateDevice(AlertService.instance.fcmToken, AppConfig.version).ignore();
  }
  final saved = await c.read(savedProvider.future);
  final details = <ExamDetail>[];
  for (final id in saved.keys) {
    try {
      final d = await api.exam(id);
      details.add(d.data);
      await c.read(dbProvider).upsertSaved(id, snapshot: jsonEncode(d.data.toJson()));
    } catch (_) {
      final snap = saved[id]?.snapshot;
      if (snap != null) details.add(snap);
    }
  }
  c.invalidate(savedProvider);
  final lang = c.read(settingsProvider).lang;
  await AlertService.instance.scheduleFor(details, (k, a) => translate(lang, k, a));
}

final _refProvider = Provider<Ref>((ref) => ref);
