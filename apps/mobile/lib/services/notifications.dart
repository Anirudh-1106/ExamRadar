import 'dart:ui' show Color;

import 'package:firebase_core/firebase_core.dart';
import 'package:firebase_messaging/firebase_messaging.dart';
import 'package:flutter_local_notifications/flutter_local_notifications.dart';
import 'package:timezone/data/latest.dart' as tzdata;
import 'package:timezone/timezone.dart' as tz;

import '../api/models.g.dart';

typedef OpenLink = void Function(String deepLink);

/// Local reminders (always available) and push (only when a Firebase project is configured).
class AlertService {
  AlertService._();
  static final instance = AlertService._();

  final _plugin = FlutterLocalNotificationsPlugin();
  OpenLink? onOpen;
  bool pushReady = false;
  String? fcmToken;

  static const _brand = Color(0xFF0B5D4B);
  static const _updates = AndroidNotificationDetails(
    'exam_updates',
    'Exam updates',
    channelDescription: 'New notices, date changes, admit cards and results',
    importance: Importance.high,
    priority: Priority.high,
    icon: 'ic_stat_notify',
    color: _brand,
  );
  static const _reminders = AndroidNotificationDetails(
    'reminders',
    'Deadline reminders',
    channelDescription: 'Reminders before your saved deadlines',
    importance: Importance.high,
    priority: Priority.high,
    icon: 'ic_stat_notify',
    color: _brand,
  );

  Future<String?> init() async {
    tzdata.initializeTimeZones();
    tz.setLocalLocation(tz.getLocation('Asia/Kolkata'));
    await _plugin.initialize(
      const InitializationSettings(android: AndroidInitializationSettings('ic_stat_notify')),
      onDidReceiveNotificationResponse: (r) {
        if (r.payload != null) onOpen?.call(r.payload!);
      },
    );
    final launch = await _plugin.getNotificationAppLaunchDetails();
    String? initial = launch?.didNotificationLaunchApp == true ? launch?.notificationResponse?.payload : null;
    try {
      // Throws when no google-services.json is bundled. The app then relies on local reminders and the inbox.
      await Firebase.initializeApp();
      final m = FirebaseMessaging.instance;
      // ignore: deprecated_member_use
      fcmToken = await m.getToken();
      pushReady = fcmToken != null;
      FirebaseMessaging.onMessage.listen((msg) {
        final n = msg.notification;
        if (n != null) show(msg.hashCode, n.title ?? '', n.body ?? '', msg.data['deep_link'] as String? ?? 'examradar://alerts');
      });
      FirebaseMessaging.onMessageOpenedApp.listen((msg) => onOpen?.call(msg.data['deep_link'] as String? ?? 'examradar://alerts'));
      final first = await m.getInitialMessage();
      initial ??= first?.data['deep_link'] as String?;
    } catch (_) {
      pushReady = false;
    }
    return initial;
  }

  Future<bool> requestPermission() async {
    final android = _plugin.resolvePlatformSpecificImplementation<AndroidFlutterLocalNotificationsPlugin>();
    return await android?.requestNotificationsPermission() ?? true;
  }

  Future<void> show(int id, String title, String body, String deepLink) =>
      _plugin.show(id & 0x7fffffff, title, body, const NotificationDetails(android: _updates), payload: deepLink);

  /// One reminder at 09:00 IST on [day], e.g. to renew a certificate before a deadline. Returns false if the day has passed.
  Future<bool> remindOn(DateTime day, String title, String body, String deepLink) async {
    final at = tz.TZDateTime(tz.local, day.year, day.month, day.day, 9);
    if (!at.isAfter(tz.TZDateTime.now(tz.local))) return false;
    await _plugin.zonedSchedule(
      Object.hash(title, day.millisecondsSinceEpoch) & 0x7fffffff,
      title,
      body,
      at,
      const NotificationDetails(android: _reminders),
      androidScheduleMode: AndroidScheduleMode.inexactAllowWhileIdle,
      payload: deepLink,
    );
    return true;
  }

  /// Schedules reminders for saved exams: 7, 3 and 1 days before deadlines (09:00 IST), the day admit cards open,
  /// and the evening before an exam. Only official or tentative day-precision dates; estimates never trigger these.
  Future<int> scheduleFor(List<ExamDetail> exams, String Function(String key, Map<String, Object?> args) t) async {
    await _plugin.cancelAll();
    final now = tz.TZDateTime.now(tz.local);
    var count = 0;
    for (final ex in exams) {
      for (final e in ex.events) {
        if (e.status != 'active' || e.dateStart == null || e.precision != 'day' || e.certainty == 'expected') continue;
        final d = e.dateStart!;
        final slots = <(tz.TZDateTime, String)>[];
        if (e.isDeadline) {
          for (final off in const [7, 3, 1]) {
            slots.add((tz.TZDateTime(tz.local, d.year, d.month, d.day - off, 9), off == 1 ? t('dayLeft', {}) : t('daysLeft', {'n': off})));
          }
        } else if (e.eventType == 'admit_card') {
          slots.add((tz.TZDateTime(tz.local, d.year, d.month, d.day, 9), e.title));
        } else if (e.eventType == 'exam') {
          slots.add((tz.TZDateTime(tz.local, d.year, d.month, d.day - 1, 18), e.title));
        }
        for (final (at, label) in slots) {
          if (!at.isAfter(now)) continue;
          final id = Object.hash(ex.id, e.id, at.millisecondsSinceEpoch) & 0x7fffffff;
          await _plugin.zonedSchedule(
            id,
            '${e.title}: $label',
            ex.title,
            at,
            const NotificationDetails(android: _reminders),
            androidScheduleMode: AndroidScheduleMode.inexactAllowWhileIdle,
            payload: 'examradar://exam/${ex.id}',
          );
          count++;
        }
      }
    }
    return count;
  }
}
