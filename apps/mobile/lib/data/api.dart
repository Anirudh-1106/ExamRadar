import 'dart:convert';

import 'package:dio/dio.dart';

import '../api/models.g.dart';
import 'local_db.dart';

/// A response plus whether it came from the offline cache.
class Fetched<T> {
  const Fetched(this.data, {this.stale = false, this.savedAt});
  final T data;
  final bool stale;
  final DateTime? savedAt;
}

class ApiError implements Exception {
  ApiError(this.message, [this.status]);
  final String message;
  final int? status;
  @override
  String toString() => message;
}

/// Typed client for the /v1 API. Models are generated from the OpenAPI spec (lib/api/models.g.dart).
class Api {
  Api(String baseUrl, this.db, {this.token})
    : dio = Dio(
        BaseOptions(
          baseUrl: baseUrl.endsWith('/') ? baseUrl.substring(0, baseUrl.length - 1) : baseUrl,
          connectTimeout: const Duration(seconds: 12),
          receiveTimeout: const Duration(seconds: 25),
          headers: {'Accept': 'application/json'},
        ),
      ) {
    dio.interceptors.add(
      InterceptorsWrapper(
        onRequest: (o, h) {
          if (token != null) o.headers['Authorization'] = 'Bearer $token';
          h.next(o);
        },
      ),
    );
  }

  final Dio dio;
  final LocalDb db;
  final String? token;

  String _key(String path, Map<String, dynamic>? q) =>
      '$path?${q == null ? '' : Uri(queryParameters: q.map((k, v) => MapEntry(k, '$v'))).query}';

  Future<Fetched<T>> _get<T>(String path, T Function(dynamic) parse, {Map<String, dynamic>? query, bool cache = true}) async {
    final key = _key(path, query);
    try {
      final r = await dio.get<String>(path, queryParameters: query, options: Options(responseType: ResponseType.plain));
      final body = r.data ?? 'null';
      if (cache) await db.putCache(key, body);
      return Fetched(parse(jsonDecode(body)));
    } on DioException catch (e) {
      final hit = cache ? await db.getCache(key) : null;
      if (hit != null && (e.response == null || (e.response!.statusCode ?? 0) >= 500)) {
        return Fetched(parse(jsonDecode(hit.$1)), stale: true, savedAt: hit.$2);
      }
      throw _err(e);
    }
  }

  ApiError _err(DioException e) {
    final data = e.response?.data;
    String? detail;
    if (data is Map && data['detail'] is String) detail = data['detail'] as String;
    if (data is String) {
      try {
        final m = jsonDecode(data);
        if (m is Map && m['detail'] is String) detail = m['detail'] as String;
      } catch (_) {}
    }
    return ApiError(detail ?? 'network', e.response?.statusCode);
  }

  Future<T> _send<T>(String method, String path, {Object? body, T Function(dynamic)? parse}) async {
    try {
      final r = await dio.request<dynamic>(path, data: body, options: Options(method: method));
      return parse == null ? (null as T) : parse(r.data);
    } on DioException catch (e) {
      throw _err(e);
    }
  }

  // ---------------------------------------------------------------- public
  Future<Fetched<MetaOut>> meta() => _get('/v1/meta', (j) => MetaOut.fromJson(j as Map<String, dynamic>));

  Future<Fetched<PageExamSummary>> exams({
    String? q,
    String? group,
    String? status,
    String? org,
    List<int>? ids,
    String sort = 'deadline',
    int page = 1,
    int pageSize = 40,
  }) {
    final query = <String, dynamic>{'sort': sort, 'page': page, 'page_size': pageSize};
    if (q != null && q.trim().isNotEmpty) query['q'] = q.trim();
    if (group != null) query['group'] = group;
    if (status != null) query['status'] = status;
    if (org != null) query['org'] = org;
    if (ids != null) query['ids'] = ids.join(',');
    return _get('/v1/exams', (j) => PageExamSummary.fromJson(j as Map<String, dynamic>), query: query);
  }

  Future<Fetched<ExamDetail>> exam(int id) => _get('/v1/exams/$id', (j) => ExamDetail.fromJson(j as Map<String, dynamic>));

  Future<Fetched<ChecklistOut>> checklist(int id) =>
      _get('/v1/exams/$id/checklist', (j) => ChecklistOut.fromJson(j as Map<String, dynamic>));

  Future<Fetched<List<CalendarEntry>>> calendar(DateTime start, DateTime end, {List<int>? ids}) => _get(
    '/v1/calendar',
    (j) => (j as List).map((e) => CalendarEntry.fromJson(e as Map<String, dynamic>)).toList(),
    query: {'start': _d(start), 'end': _d(end), if (ids != null) 'ids': ids.join(',')},
  );

  Future<Fetched<PageNoticeOut>> notices({String? org}) =>
      _get('/v1/notices', (j) => PageNoticeOut.fromJson(j as Map<String, dynamic>), query: {if (org != null) 'org': org});

  Future<Fetched<List<NewsOut>>> news() =>
      _get('/v1/news', (j) => (j as List).map((e) => NewsOut.fromJson(e as Map<String, dynamic>)).toList());

  Future<Fetched<List<SourceStatusOut>>> sources() =>
      _get('/v1/sources', (j) => (j as List).map((e) => SourceStatusOut.fromJson(e as Map<String, dynamic>)).toList());

  Future<List<ExamEligibility>> evaluate(ProfileData profile, List<int> ids) => _send(
    'POST',
    '/v1/eligibility/evaluate',
    body: {'profile': profile.toJson(), 'exam_ids': ids},
    parse: (j) => (j as List).map((e) => ExamEligibility.fromJson(e as Map<String, dynamic>)).toList(),
  );

  Future<ScamOut> scamCheck(String kind, String value) =>
      _send('POST', '/v1/scam-check', body: {'kind': kind, 'value': value}, parse: (j) => ScamOut.fromJson(j as Map<String, dynamic>));

  Future<ScamOut> scamPdf(List<int> bytes, String name) => _send(
    'POST',
    '/v1/scam-check/pdf',
    body: FormData.fromMap({'file': MultipartFile.fromBytes(bytes, filename: name)}),
    parse: (j) => ScamOut.fromJson(j as Map<String, dynamic>),
  );

  // ---------------------------------------------------------------- device and personal
  Future<RegisterOut> register(String appVersion) => _send(
    'POST',
    '/v1/devices/register',
    body: {'platform': 'android', 'app_version': appVersion},
    parse: (j) => RegisterOut.fromJson(j as Map<String, dynamic>),
  );

  Future<void> updateDevice(String? fcmToken, String appVersion) =>
      _send<void>('PUT', '/v1/me/device', body: {'fcm_token': fcmToken, 'app_version': appVersion});

  Future<void> saveExam(int id) => _send<void>('PUT', '/v1/me/exams/$id');
  Future<void> unsaveExam(int id) => _send<void>('DELETE', '/v1/me/exams/$id');
  Future<void> setStatus(int id, String status) => _send<void>('PUT', '/v1/me/exams/$id/status', body: {'status': status});

  Future<List<NotificationOut>> inbox() => _send(
    'GET',
    '/v1/me/notifications',
    parse: (j) => (j as List).map((e) => NotificationOut.fromJson(e as Map<String, dynamic>)).toList(),
  );
  Future<void> markRead(List<int> ids) => _send<void>('POST', '/v1/me/notifications/read', body: ids);

  Future<PrefsOut> prefs() => _send('GET', '/v1/me/preferences', parse: (j) => PrefsOut.fromJson(j as Map<String, dynamic>));
  Future<PrefsOut> putPrefs(PrefsOut p) =>
      _send('PUT', '/v1/me/preferences', body: p.toJson(), parse: (j) => PrefsOut.fromJson(j as Map<String, dynamic>));

  Future<void> putProfile(ProfileData p) => _send<void>('PUT', '/v1/me/profile', body: {'consent': true, 'data': p.toJson()});
  Future<void> deleteProfile() => _send<void>('DELETE', '/v1/me/profile');
  Future<Map<String, dynamic>> export() => _send('GET', '/v1/me/export', parse: (j) => Map<String, dynamic>.from(j as Map));
  Future<void> deleteMe() => _send<void>('DELETE', '/v1/me');

  static String _d(DateTime d) =>
      '${d.year.toString().padLeft(4, '0')}-${d.month.toString().padLeft(2, '0')}-${d.day.toString().padLeft(2, '0')}';
}
