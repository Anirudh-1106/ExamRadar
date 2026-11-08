import 'dart:convert';

import 'package:drift/drift.dart';
import 'package:drift_flutter/drift_flutter.dart';

/// On-device storage (Drift over SQLite), used through raw SQL so no code generation is needed.
/// Holds the offline cache, saved exams, the on-device profile, and checklist ticks.
class LocalDb extends GeneratedDatabase {
  LocalDb([QueryExecutor? e]) : super(e ?? driftDatabase(name: 'examradar'));

  @override
  Iterable<TableInfo<Table, Object?>> get allTables => const [];

  @override
  int get schemaVersion => 1;

  @override
  MigrationStrategy get migration => MigrationStrategy(
    onCreate: (m) async {
      await customStatement('CREATE TABLE IF NOT EXISTS cache (key TEXT PRIMARY KEY, body TEXT NOT NULL, saved_at INTEGER NOT NULL)');
      await customStatement(
        'CREATE TABLE IF NOT EXISTS saved (exam_id INTEGER PRIMARY KEY, status TEXT, saved_at INTEGER NOT NULL, snapshot TEXT)',
      );
      await customStatement('CREATE TABLE IF NOT EXISTS kv (key TEXT PRIMARY KEY, value TEXT NOT NULL)');
      await customStatement(
        'CREATE TABLE IF NOT EXISTS checklist (exam_id INTEGER NOT NULL, item TEXT NOT NULL, done INTEGER NOT NULL, PRIMARY KEY (exam_id, item))',
      );
    },
  );

  Future<void> putCache(String key, String body) => customStatement('INSERT OR REPLACE INTO cache (key, body, saved_at) VALUES (?, ?, ?)', [
    key,
    body,
    DateTime.now().millisecondsSinceEpoch,
  ]);

  Future<(String, DateTime)?> getCache(String key) async {
    final r = await customSelect('SELECT body, saved_at FROM cache WHERE key = ?', variables: [Variable.withString(key)]).getSingleOrNull();
    if (r == null) return null;
    return (r.read<String>('body'), DateTime.fromMillisecondsSinceEpoch(r.read<int>('saved_at')));
  }

  Future<List<SavedRow>> savedRows() async {
    final rows = await customSelect('SELECT exam_id, status, saved_at, snapshot FROM saved ORDER BY saved_at DESC').get();
    return rows
        .map(
          (r) => SavedRow(
            r.read<int>('exam_id'),
            r.readNullable<String>('status'),
            DateTime.fromMillisecondsSinceEpoch(r.read<int>('saved_at')),
            r.readNullable<String>('snapshot'),
          ),
        )
        .toList();
  }

  Future<void> upsertSaved(int id, {String? status, String? snapshot}) async {
    await customStatement('INSERT OR IGNORE INTO saved (exam_id, status, saved_at, snapshot) VALUES (?, ?, ?, ?)', [
      id,
      status,
      DateTime.now().millisecondsSinceEpoch,
      snapshot,
    ]);
    if (status != null) await customStatement('UPDATE saved SET status = ? WHERE exam_id = ?', [status, id]);
    if (snapshot != null) await customStatement('UPDATE saved SET snapshot = ? WHERE exam_id = ?', [snapshot, id]);
  }

  Future<void> removeSaved(int id) => customStatement('DELETE FROM saved WHERE exam_id = ?', [id]);

  Future<String?> getKv(String key) async {
    final r = await customSelect('SELECT value FROM kv WHERE key = ?', variables: [Variable.withString(key)]).getSingleOrNull();
    return r?.read<String>('value');
  }

  Future<void> setKv(String key, String? value) =>
      value == null
          ? customStatement('DELETE FROM kv WHERE key = ?', [key])
          : customStatement('INSERT OR REPLACE INTO kv (key, value) VALUES (?, ?)', [key, value]);

  Future<Set<String>> checked(int examId) async {
    final rows =
        await customSelect('SELECT item FROM checklist WHERE exam_id = ? AND done = 1', variables: [Variable.withInt(examId)]).get();
    return rows.map((r) => r.read<String>('item')).toSet();
  }

  Future<void> setChecked(int examId, String item, bool done) =>
      customStatement('INSERT OR REPLACE INTO checklist (exam_id, item, done) VALUES (?, ?, ?)', [examId, item, done ? 1 : 0]);

  Future<void> wipe() async {
    for (final t in ['cache', 'saved', 'kv', 'checklist']) {
      await customStatement('DELETE FROM $t');
    }
  }

  Future<Map<String, dynamic>?> getJson(String key) async {
    final v = await getKv(key);
    return v == null ? null : jsonDecode(v) as Map<String, dynamic>;
  }
}

class SavedRow {
  SavedRow(this.examId, this.status, this.savedAt, this.snapshot);
  final int examId;
  final String? status;
  final DateTime savedAt;
  final String? snapshot;
}
