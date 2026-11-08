import 'dart:convert';

import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:shared_preferences/shared_preferences.dart';

import '../api/models.g.dart';
import '../config.dart';
import 'api.dart';
import 'local_db.dart';

final prefsStoreProvider = Provider<SharedPreferences>((ref) => throw UnimplementedError('overridden in main'));
final dbProvider = Provider<LocalDb>((ref) => throw UnimplementedError('overridden in main'));

class Settings {
  const Settings({
    required this.onboarded,
    required this.lang,
    required this.largeText,
    required this.lowData,
    required this.apiBase,
    required this.token,
    required this.groups,
    required this.syncProfile,
  });
  final bool onboarded, largeText, lowData, syncProfile;
  final String lang, apiBase;
  final String? token;
  final List<String> groups;

  Settings copyWith({
    bool? onboarded,
    String? lang,
    bool? largeText,
    bool? lowData,
    String? apiBase,
    String? token,
    List<String>? groups,
    bool? syncProfile,
  }) => Settings(
    onboarded: onboarded ?? this.onboarded,
    lang: lang ?? this.lang,
    largeText: largeText ?? this.largeText,
    lowData: lowData ?? this.lowData,
    apiBase: apiBase ?? this.apiBase,
    token: token ?? this.token,
    groups: groups ?? this.groups,
    syncProfile: syncProfile ?? this.syncProfile,
  );
}

class SettingsNotifier extends Notifier<Settings> {
  SharedPreferences get _p => ref.read(prefsStoreProvider);

  @override
  Settings build() {
    final p = ref.read(prefsStoreProvider);
    return Settings(
      onboarded: p.getBool('onboarded') ?? false,
      lang: p.getString('lang') ?? 'en',
      largeText: p.getBool('largeText') ?? false,
      lowData: p.getBool('lowData') ?? false,
      apiBase: p.getString('apiBase') ?? AppConfig.defaultApiBase,
      token: p.getString('token'),
      groups: p.getStringList('groups') ?? const ['central', 'kerala'],
      syncProfile: p.getBool('syncProfile') ?? false,
    );
  }

  Future<void> update(Settings s) async {
    state = s;
    await _p.setBool('onboarded', s.onboarded);
    await _p.setString('lang', s.lang);
    await _p.setBool('largeText', s.largeText);
    await _p.setBool('lowData', s.lowData);
    await _p.setString('apiBase', s.apiBase);
    await _p.setStringList('groups', s.groups);
    await _p.setBool('syncProfile', s.syncProfile);
    if (s.token == null) {
      await _p.remove('token');
    } else {
      await _p.setString('token', s.token!);
    }
  }

  Future<void> clearToken() async {
    await _p.remove('token');
    state = Settings(
      onboarded: state.onboarded,
      lang: state.lang,
      largeText: state.largeText,
      lowData: state.lowData,
      apiBase: state.apiBase,
      token: null,
      groups: state.groups,
      syncProfile: false,
    );
  }
}

final settingsProvider = NotifierProvider<SettingsNotifier, Settings>(SettingsNotifier.new);

final apiProvider = Provider<Api>((ref) {
  final s = ref.watch(settingsProvider);
  return Api(s.apiBase, ref.read(dbProvider), token: s.token);
});

/// Registers this phone anonymously (no personal data) so saved exams sync and push alerts can be sent.
Future<void> ensureRegistered(Ref ref) async {
  final s = ref.read(settingsProvider);
  if (s.token != null) return;
  try {
    final r = await ref.read(apiProvider).register(AppConfig.version);
    await ref.read(settingsProvider.notifier).update(s.copyWith(token: r.token));
    // Push saved exams made while offline.
    final api = ref.read(apiProvider);
    for (final row in await ref.read(dbProvider).savedRows()) {
      await api.saveExam(row.examId);
      if (row.status != null) await api.setStatus(row.examId, row.status!);
    }
  } catch (_) {
    // Offline or server unreachable: the app keeps working locally and retries next launch.
  }
}

typedef ExamQuery = ({String? q, String? group, String? status, String sort});

final examsProvider = FutureProvider.family<Fetched<PageExamSummary>, ExamQuery>((ref, q) {
  return ref.watch(apiProvider).exams(q: q.q, group: q.group, status: q.status, sort: q.sort);
});

final examDetailProvider = FutureProvider.family<Fetched<ExamDetail>, int>((ref, id) async {
  final d = await ref.watch(apiProvider).exam(id);
  final saved = ref.read(savedProvider).value ?? const {};
  if (saved.containsKey(id)) {
    await ref.read(dbProvider).upsertSaved(id, snapshot: jsonEncode(d.data.toJson()));
  }
  return d;
});

final checklistProvider = FutureProvider.family<Fetched<ChecklistOut>, int>((ref, id) => ref.watch(apiProvider).checklist(id));

final metaProvider = FutureProvider<Fetched<MetaOut>>((ref) => ref.watch(apiProvider).meta());
final sourcesProvider = FutureProvider<Fetched<List<SourceStatusOut>>>((ref) => ref.watch(apiProvider).sources());
final newsProvider = FutureProvider<Fetched<List<NewsOut>>>((ref) => ref.watch(apiProvider).news());
final noticesProvider = FutureProvider<Fetched<PageNoticeOut>>((ref) => ref.watch(apiProvider).notices());

typedef CalQuery = ({DateTime start, DateTime end, bool mine});
final calendarProvider = FutureProvider.family<Fetched<List<CalendarEntry>>, CalQuery>((ref, q) async {
  final ids = q.mine ? (ref.watch(savedProvider).value ?? const {}).keys.toList() : null;
  if (ids != null && ids.isEmpty) return const Fetched(<CalendarEntry>[]);
  return ref.watch(apiProvider).calendar(q.start, q.end, ids: ids);
});

class SavedEntry {
  SavedEntry(this.examId, this.status, this.savedAt, this.snapshot);
  final int examId;
  final String? status;
  final DateTime savedAt;
  final ExamDetail? snapshot;
}

/// Saved exams live on the phone first (so they work offline) and are mirrored to the server when possible.
class SavedNotifier extends AsyncNotifier<Map<int, SavedEntry>> {
  @override
  Future<Map<int, SavedEntry>> build() async {
    final rows = await ref.read(dbProvider).savedRows();
    return {
      for (final r in rows)
        r.examId: SavedEntry(
          r.examId,
          r.status,
          r.savedAt,
          r.snapshot == null ? null : ExamDetail.fromJson(jsonDecode(r.snapshot!) as Map<String, dynamic>),
        ),
    };
  }

  Future<void> toggle(int id, {ExamDetail? detail}) async {
    final db = ref.read(dbProvider);
    final api = ref.read(apiProvider);
    final cur = state.value ?? {};
    if (cur.containsKey(id)) {
      await db.removeSaved(id);
      api.unsaveExam(id).ignore();
    } else {
      await db.upsertSaved(id, status: 'interested', snapshot: detail == null ? null : jsonEncode(detail.toJson()));
      api.setStatus(id, 'interested').ignore();
    }
    ref.invalidateSelf();
    await future;
  }

  Future<void> setStatus(int id, String status) async {
    await ref.read(dbProvider).upsertSaved(id, status: status);
    ref.read(apiProvider).setStatus(id, status).ignore();
    ref.invalidateSelf();
    await future;
  }
}

final savedProvider = AsyncNotifierProvider<SavedNotifier, Map<int, SavedEntry>>(SavedNotifier.new);

/// The profile stays on the phone. It is sent only for a one-off check (not stored), unless the user
/// turns on matching alerts, which stores it on the server with consent.
class ProfileNotifier extends AsyncNotifier<ProfileData?> {
  @override
  Future<ProfileData?> build() async {
    final j = await ref.read(dbProvider).getJson('profile');
    return j == null ? null : ProfileData.fromJson(j);
  }

  Future<void> save(ProfileData p) async {
    await ref.read(dbProvider).setKv('profile', jsonEncode(p.toJson()));
    state = AsyncData(p);
    if (ref.read(settingsProvider).syncProfile) {
      await ref.read(apiProvider).putProfile(p);
    }
  }

  Future<void> clear() async {
    await ref.read(dbProvider).setKv('profile', null);
    state = const AsyncData(null);
  }
}

final profileProvider = AsyncNotifierProvider<ProfileNotifier, ProfileData?>(ProfileNotifier.new);

final eligibilityProvider = FutureProvider.family<ExamEligibility?, int>((ref, id) async {
  final p = await ref.watch(profileProvider.future);
  if (p == null) return null;
  final r = await ref.watch(apiProvider).evaluate(p, [id]);
  return r.isEmpty ? null : r.first;
});

final eligibleIdsProvider = FutureProvider.family<Set<int>, List<int>>((ref, ids) async {
  final p = await ref.watch(profileProvider.future);
  if (p == null || ids.isEmpty) return ids.toSet();
  final r = await ref.watch(apiProvider).evaluate(p, ids);
  return r.where((e) => e.status != 'not_eligible').map((e) => e.examId).toSet();
});

final inboxProvider = FutureProvider<List<NotificationOut>>((ref) async {
  if (ref.watch(settingsProvider).token == null) return const [];
  return ref.watch(apiProvider).inbox();
});

final serverPrefsProvider = FutureProvider<PrefsOut?>((ref) async {
  if (ref.watch(settingsProvider).token == null) return null;
  return ref.watch(apiProvider).prefs();
});
