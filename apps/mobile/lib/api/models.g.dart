// GENERATED from docs/openapi.json by tools/gen_dart_models.py. Do not edit by hand.
// ignore_for_file: non_constant_identifier_names, prefer_null_aware_operators

class ApplyOut {
  final String url;
  final String host;
  final String? note;
  final String? copyText;
  final String? copyLabel;
  const ApplyOut({required this.url, required this.host, this.note, this.copyText, this.copyLabel});
  factory ApplyOut.fromJson(Map<String, dynamic> j) => ApplyOut(
    url: j['url'] == null ? '' : j['url'] as String,
    host: j['host'] == null ? '' : j['host'] as String,
    note: j['note'] == null ? null : j['note'] as String,
    copyText: j['copy_text'] == null ? null : j['copy_text'] as String,
    copyLabel: j['copy_label'] == null ? null : j['copy_label'] as String,
  );
  Map<String, dynamic> toJson() => {'url': url, 'host': host, 'note': note, 'copy_text': copyText, 'copy_label': copyLabel};
}

class BodyScamCheckPdfV1ScamCheckPdfPost {
  final String file;
  const BodyScamCheckPdfV1ScamCheckPdfPost({required this.file});
  factory BodyScamCheckPdfV1ScamCheckPdfPost.fromJson(Map<String, dynamic> j) =>
      BodyScamCheckPdfV1ScamCheckPdfPost(file: j['file'] == null ? '' : j['file'] as String);
  Map<String, dynamic> toJson() => {'file': file};
}

class CalendarEntry {
  final DateTime date;
  final DateTime? dateEnd;
  final int examId;
  final String examTitle;
  final String organisationKey;
  final String eventType;
  final String title;
  final String certainty;
  final String precision;
  final bool isDeadline;
  const CalendarEntry({
    required this.date,
    this.dateEnd,
    required this.examId,
    required this.examTitle,
    required this.organisationKey,
    required this.eventType,
    required this.title,
    required this.certainty,
    required this.precision,
    required this.isDeadline,
  });
  factory CalendarEntry.fromJson(Map<String, dynamic> j) => CalendarEntry(
    date: DateTime.parse(j['date'] as String),
    dateEnd: j['date_end'] == null ? null : DateTime.parse(j['date_end'] as String),
    examId: j['exam_id'] == null ? 0 : (j['exam_id'] as num).toInt(),
    examTitle: j['exam_title'] == null ? '' : j['exam_title'] as String,
    organisationKey: j['organisation_key'] == null ? '' : j['organisation_key'] as String,
    eventType: j['event_type'] == null ? '' : j['event_type'] as String,
    title: j['title'] == null ? '' : j['title'] as String,
    certainty: j['certainty'] == null ? '' : j['certainty'] as String,
    precision: j['precision'] == null ? '' : j['precision'] as String,
    isDeadline: j['is_deadline'] == null ? false : j['is_deadline'] as bool,
  );
  Map<String, dynamic> toJson() => {
    'date': date.toIso8601String().substring(0, 10),
    'date_end': dateEnd?.toIso8601String().substring(0, 10),
    'exam_id': examId,
    'exam_title': examTitle,
    'organisation_key': organisationKey,
    'event_type': eventType,
    'title': title,
    'certainty': certainty,
    'precision': precision,
    'is_deadline': isDeadline,
  };
}

class ChangeOut {
  final int eventId;
  final String eventTitle;
  final int revisionNo;
  final String kind;
  final Map<String, dynamic>? oldValue;
  final Map<String, dynamic>? newValue;
  final String? reason;
  final String? sourceUrl;
  final DateTime createdAt;
  const ChangeOut({
    required this.eventId,
    required this.eventTitle,
    required this.revisionNo,
    required this.kind,
    this.oldValue,
    this.newValue,
    this.reason,
    this.sourceUrl,
    required this.createdAt,
  });
  factory ChangeOut.fromJson(Map<String, dynamic> j) => ChangeOut(
    eventId: j['event_id'] == null ? 0 : (j['event_id'] as num).toInt(),
    eventTitle: j['event_title'] == null ? '' : j['event_title'] as String,
    revisionNo: j['revision_no'] == null ? 0 : (j['revision_no'] as num).toInt(),
    kind: j['kind'] == null ? '' : j['kind'] as String,
    oldValue: j['old_value'] == null ? null : Map<String, dynamic>.from(j['old_value'] as Map),
    newValue: j['new_value'] == null ? null : Map<String, dynamic>.from(j['new_value'] as Map),
    reason: j['reason'] == null ? null : j['reason'] as String,
    sourceUrl: j['source_url'] == null ? null : j['source_url'] as String,
    createdAt: DateTime.parse(j['created_at'] as String),
  );
  Map<String, dynamic> toJson() => {
    'event_id': eventId,
    'event_title': eventTitle,
    'revision_no': revisionNo,
    'kind': kind,
    'old_value': oldValue,
    'new_value': newValue,
    'reason': reason,
    'source_url': sourceUrl,
    'created_at': createdAt.toIso8601String(),
  };
}

class ChecklistItemOut {
  final String key;
  final String text;
  final DateTime? due;
  final String? certainty;
  final String? sourceUrl;
  final bool done;
  const ChecklistItemOut({required this.key, required this.text, this.due, this.certainty, this.sourceUrl, required this.done});
  factory ChecklistItemOut.fromJson(Map<String, dynamic> j) => ChecklistItemOut(
    key: j['key'] == null ? '' : j['key'] as String,
    text: j['text'] == null ? '' : j['text'] as String,
    due: j['due'] == null ? null : DateTime.parse(j['due'] as String),
    certainty: j['certainty'] == null ? null : j['certainty'] as String,
    sourceUrl: j['source_url'] == null ? null : j['source_url'] as String,
    done: j['done'] == null ? false : j['done'] as bool,
  );
  Map<String, dynamic> toJson() => {
    'key': key,
    'text': text,
    'due': due?.toIso8601String().substring(0, 10),
    'certainty': certainty,
    'source_url': sourceUrl,
    'done': done,
  };
}

class ChecklistOut {
  final List<ChecklistItemOut> items;
  final List<PhotoSpecOut> photoSpecs;
  final List<Map<String, dynamic>> certificateRules;
  final String note;
  const ChecklistOut({required this.items, required this.photoSpecs, required this.certificateRules, required this.note});
  factory ChecklistOut.fromJson(Map<String, dynamic> j) => ChecklistOut(
    items:
        j['items'] == null ? const [] : ((j['items']) as List).map((e) => ChecklistItemOut.fromJson((e) as Map<String, dynamic>)).toList(),
    photoSpecs:
        j['photo_specs'] == null
            ? const []
            : ((j['photo_specs']) as List).map((e) => PhotoSpecOut.fromJson((e) as Map<String, dynamic>)).toList(),
    certificateRules:
        j['certificate_rules'] == null
            ? const []
            : ((j['certificate_rules']) as List).map((e) => Map<String, dynamic>.from(e as Map)).toList(),
    note: j['note'] == null ? '' : j['note'] as String,
  );
  Map<String, dynamic> toJson() => {
    'items': items.map((e) => e.toJson()).toList(),
    'photo_specs': photoSpecs.map((e) => e.toJson()).toList(),
    'certificate_rules': certificateRules,
    'note': note,
  };
}

class DeviceIn {
  final String? fcmToken;
  final String? appVersion;
  const DeviceIn({this.fcmToken, this.appVersion});
  factory DeviceIn.fromJson(Map<String, dynamic> j) => DeviceIn(
    fcmToken: j['fcm_token'] == null ? null : j['fcm_token'] as String,
    appVersion: j['app_version'] == null ? null : j['app_version'] as String,
  );
  Map<String, dynamic> toJson() => {'fcm_token': fcmToken, 'app_version': appVersion};
}

class EvaluateIn {
  final ProfileData profile;
  final List<int> examIds;
  const EvaluateIn({required this.profile, required this.examIds});
  factory EvaluateIn.fromJson(Map<String, dynamic> j) => EvaluateIn(
    profile: ProfileData.fromJson((j['profile']) as Map<String, dynamic>),
    examIds: j['exam_ids'] == null ? const [] : ((j['exam_ids']) as List).map((e) => (e as num).toInt()).toList(),
  );
  Map<String, dynamic> toJson() => {'profile': profile.toJson(), 'exam_ids': examIds};
}

class EventOut {
  final int id;
  final String eventType;
  final String title;
  final String? label;
  final DateTime? dateStart;
  final DateTime? dateEnd;
  final String precision;
  final String certainty;
  final String status;
  final String? categoryNumber;
  final int revisionCount;
  final bool isDeadline;
  final EvidenceOut? evidence;
  const EventOut({
    required this.id,
    required this.eventType,
    required this.title,
    this.label,
    this.dateStart,
    this.dateEnd,
    required this.precision,
    required this.certainty,
    required this.status,
    this.categoryNumber,
    required this.revisionCount,
    required this.isDeadline,
    this.evidence,
  });
  factory EventOut.fromJson(Map<String, dynamic> j) => EventOut(
    id: j['id'] == null ? 0 : (j['id'] as num).toInt(),
    eventType: j['event_type'] == null ? '' : j['event_type'] as String,
    title: j['title'] == null ? '' : j['title'] as String,
    label: j['label'] == null ? null : j['label'] as String,
    dateStart: j['date_start'] == null ? null : DateTime.parse(j['date_start'] as String),
    dateEnd: j['date_end'] == null ? null : DateTime.parse(j['date_end'] as String),
    precision: j['precision'] == null ? '' : j['precision'] as String,
    certainty: j['certainty'] == null ? '' : j['certainty'] as String,
    status: j['status'] == null ? '' : j['status'] as String,
    categoryNumber: j['category_number'] == null ? null : j['category_number'] as String,
    revisionCount: j['revision_count'] == null ? 0 : (j['revision_count'] as num).toInt(),
    isDeadline: j['is_deadline'] == null ? false : j['is_deadline'] as bool,
    evidence: j['evidence'] == null ? null : EvidenceOut.fromJson((j['evidence']) as Map<String, dynamic>),
  );
  Map<String, dynamic> toJson() => {
    'id': id,
    'event_type': eventType,
    'title': title,
    'label': label,
    'date_start': dateStart?.toIso8601String().substring(0, 10),
    'date_end': dateEnd?.toIso8601String().substring(0, 10),
    'precision': precision,
    'certainty': certainty,
    'status': status,
    'category_number': categoryNumber,
    'revision_count': revisionCount,
    'is_deadline': isDeadline,
    'evidence': evidence?.toJson(),
  };
}

class EvidenceOut {
  final String quote;
  final int? page;
  final String sourceUrl;
  final String? documentHash;
  final DateTime? retrievedAt;
  final DateTime? publishedOn;
  const EvidenceOut({required this.quote, this.page, required this.sourceUrl, this.documentHash, this.retrievedAt, this.publishedOn});
  factory EvidenceOut.fromJson(Map<String, dynamic> j) => EvidenceOut(
    quote: j['quote'] == null ? '' : j['quote'] as String,
    page: j['page'] == null ? null : (j['page'] as num).toInt(),
    sourceUrl: j['source_url'] == null ? '' : j['source_url'] as String,
    documentHash: j['document_hash'] == null ? null : j['document_hash'] as String,
    retrievedAt: j['retrieved_at'] == null ? null : DateTime.parse(j['retrieved_at'] as String),
    publishedOn: j['published_on'] == null ? null : DateTime.parse(j['published_on'] as String),
  );
  Map<String, dynamic> toJson() => {
    'quote': quote,
    'page': page,
    'source_url': sourceUrl,
    'document_hash': documentHash,
    'retrieved_at': retrievedAt?.toIso8601String(),
    'published_on': publishedOn?.toIso8601String().substring(0, 10),
  };
}

class ExamDetail {
  final int id;
  final String title;
  final String examName;
  final OrgOut organisation;
  final String? sector;
  final String status;
  final bool isFastAlert;
  final EventOut? nextEvent;
  final EventOut? applicationEnd;
  final EventOut? examDate;
  final List<String> categoryNumbers;
  final int? vacanciesTotal;
  final bool hasChanges;
  final String officialUrl;
  final DateTime lastCheckedAt;
  final DateTime updatedAt;
  final List<EventOut> events;
  final List<PostOut> posts;
  final List<LinkOut> links;
  final ApplyOut? apply;
  final String? notificationPdf;
  final List<FeeOut> fees;
  final String? qualificationText;
  final List<String> confirmationNotes;
  final List<PhotoSpecOut> photoSpecs;
  final List<String> combinedWith;
  final List<ChangeOut> changes;
  final List<NewsOut> news;
  final String? summary;
  final bool summaryIsMachine;
  final String? sourceStatus;
  final String disclaimer;
  const ExamDetail({
    required this.id,
    required this.title,
    required this.examName,
    required this.organisation,
    this.sector,
    required this.status,
    required this.isFastAlert,
    this.nextEvent,
    this.applicationEnd,
    this.examDate,
    required this.categoryNumbers,
    this.vacanciesTotal,
    required this.hasChanges,
    required this.officialUrl,
    required this.lastCheckedAt,
    required this.updatedAt,
    required this.events,
    required this.posts,
    required this.links,
    this.apply,
    this.notificationPdf,
    required this.fees,
    this.qualificationText,
    required this.confirmationNotes,
    required this.photoSpecs,
    required this.combinedWith,
    required this.changes,
    required this.news,
    this.summary,
    required this.summaryIsMachine,
    this.sourceStatus,
    required this.disclaimer,
  });
  factory ExamDetail.fromJson(Map<String, dynamic> j) => ExamDetail(
    id: j['id'] == null ? 0 : (j['id'] as num).toInt(),
    title: j['title'] == null ? '' : j['title'] as String,
    examName: j['exam_name'] == null ? '' : j['exam_name'] as String,
    organisation: OrgOut.fromJson((j['organisation']) as Map<String, dynamic>),
    sector: j['sector'] == null ? null : j['sector'] as String,
    status: j['status'] == null ? '' : j['status'] as String,
    isFastAlert: j['is_fast_alert'] == null ? false : j['is_fast_alert'] as bool,
    nextEvent: j['next_event'] == null ? null : EventOut.fromJson((j['next_event']) as Map<String, dynamic>),
    applicationEnd: j['application_end'] == null ? null : EventOut.fromJson((j['application_end']) as Map<String, dynamic>),
    examDate: j['exam_date'] == null ? null : EventOut.fromJson((j['exam_date']) as Map<String, dynamic>),
    categoryNumbers: j['category_numbers'] == null ? const [] : ((j['category_numbers']) as List).map((e) => e as String).toList(),
    vacanciesTotal: j['vacancies_total'] == null ? null : (j['vacancies_total'] as num).toInt(),
    hasChanges: j['has_changes'] == null ? false : j['has_changes'] as bool,
    officialUrl: j['official_url'] == null ? '' : j['official_url'] as String,
    lastCheckedAt: DateTime.parse(j['last_checked_at'] as String),
    updatedAt: DateTime.parse(j['updated_at'] as String),
    events: j['events'] == null ? const [] : ((j['events']) as List).map((e) => EventOut.fromJson((e) as Map<String, dynamic>)).toList(),
    posts: j['posts'] == null ? const [] : ((j['posts']) as List).map((e) => PostOut.fromJson((e) as Map<String, dynamic>)).toList(),
    links: j['links'] == null ? const [] : ((j['links']) as List).map((e) => LinkOut.fromJson((e) as Map<String, dynamic>)).toList(),
    apply: j['apply'] == null ? null : ApplyOut.fromJson((j['apply']) as Map<String, dynamic>),
    notificationPdf: j['notification_pdf'] == null ? null : j['notification_pdf'] as String,
    fees: j['fees'] == null ? const [] : ((j['fees']) as List).map((e) => FeeOut.fromJson((e) as Map<String, dynamic>)).toList(),
    qualificationText: j['qualification_text'] == null ? null : j['qualification_text'] as String,
    confirmationNotes: j['confirmation_notes'] == null ? const [] : ((j['confirmation_notes']) as List).map((e) => e as String).toList(),
    photoSpecs:
        j['photo_specs'] == null
            ? const []
            : ((j['photo_specs']) as List).map((e) => PhotoSpecOut.fromJson((e) as Map<String, dynamic>)).toList(),
    combinedWith: j['combined_with'] == null ? const [] : ((j['combined_with']) as List).map((e) => e as String).toList(),
    changes:
        j['changes'] == null ? const [] : ((j['changes']) as List).map((e) => ChangeOut.fromJson((e) as Map<String, dynamic>)).toList(),
    news: j['news'] == null ? const [] : ((j['news']) as List).map((e) => NewsOut.fromJson((e) as Map<String, dynamic>)).toList(),
    summary: j['summary'] == null ? null : j['summary'] as String,
    summaryIsMachine: j['summary_is_machine'] == null ? false : j['summary_is_machine'] as bool,
    sourceStatus: j['source_status'] == null ? null : j['source_status'] as String,
    disclaimer: j['disclaimer'] == null ? '' : j['disclaimer'] as String,
  );
  Map<String, dynamic> toJson() => {
    'id': id,
    'title': title,
    'exam_name': examName,
    'organisation': organisation.toJson(),
    'sector': sector,
    'status': status,
    'is_fast_alert': isFastAlert,
    'next_event': nextEvent?.toJson(),
    'application_end': applicationEnd?.toJson(),
    'exam_date': examDate?.toJson(),
    'category_numbers': categoryNumbers,
    'vacancies_total': vacanciesTotal,
    'has_changes': hasChanges,
    'official_url': officialUrl,
    'last_checked_at': lastCheckedAt.toIso8601String(),
    'updated_at': updatedAt.toIso8601String(),
    'events': events.map((e) => e.toJson()).toList(),
    'posts': posts.map((e) => e.toJson()).toList(),
    'links': links.map((e) => e.toJson()).toList(),
    'apply': apply?.toJson(),
    'notification_pdf': notificationPdf,
    'fees': fees.map((e) => e.toJson()).toList(),
    'qualification_text': qualificationText,
    'confirmation_notes': confirmationNotes,
    'photo_specs': photoSpecs.map((e) => e.toJson()).toList(),
    'combined_with': combinedWith,
    'changes': changes.map((e) => e.toJson()).toList(),
    'news': news.map((e) => e.toJson()).toList(),
    'summary': summary,
    'summary_is_machine': summaryIsMachine,
    'source_status': sourceStatus,
    'disclaimer': disclaimer,
  };
}

class ExamEligibility {
  final int examId;
  final String examTitle;
  final String status;
  final List<PostEligibility> posts;
  final List<Map<String, dynamic>> countdown;
  const ExamEligibility({
    required this.examId,
    required this.examTitle,
    required this.status,
    required this.posts,
    required this.countdown,
  });
  factory ExamEligibility.fromJson(Map<String, dynamic> j) => ExamEligibility(
    examId: j['exam_id'] == null ? 0 : (j['exam_id'] as num).toInt(),
    examTitle: j['exam_title'] == null ? '' : j['exam_title'] as String,
    status: j['status'] == null ? '' : j['status'] as String,
    posts:
        j['posts'] == null ? const [] : ((j['posts']) as List).map((e) => PostEligibility.fromJson((e) as Map<String, dynamic>)).toList(),
    countdown: j['countdown'] == null ? const [] : ((j['countdown']) as List).map((e) => Map<String, dynamic>.from(e as Map)).toList(),
  );
  Map<String, dynamic> toJson() => {
    'exam_id': examId,
    'exam_title': examTitle,
    'status': status,
    'posts': posts.map((e) => e.toJson()).toList(),
    'countdown': countdown,
  };
}

class ExamSummary {
  final int id;
  final String title;
  final String examName;
  final OrgOut organisation;
  final String? sector;
  final String status;
  final bool isFastAlert;
  final EventOut? nextEvent;
  final EventOut? applicationEnd;
  final EventOut? examDate;
  final List<String> categoryNumbers;
  final int? vacanciesTotal;
  final bool hasChanges;
  final String officialUrl;
  final DateTime lastCheckedAt;
  final DateTime updatedAt;
  const ExamSummary({
    required this.id,
    required this.title,
    required this.examName,
    required this.organisation,
    this.sector,
    required this.status,
    required this.isFastAlert,
    this.nextEvent,
    this.applicationEnd,
    this.examDate,
    required this.categoryNumbers,
    this.vacanciesTotal,
    required this.hasChanges,
    required this.officialUrl,
    required this.lastCheckedAt,
    required this.updatedAt,
  });
  factory ExamSummary.fromJson(Map<String, dynamic> j) => ExamSummary(
    id: j['id'] == null ? 0 : (j['id'] as num).toInt(),
    title: j['title'] == null ? '' : j['title'] as String,
    examName: j['exam_name'] == null ? '' : j['exam_name'] as String,
    organisation: OrgOut.fromJson((j['organisation']) as Map<String, dynamic>),
    sector: j['sector'] == null ? null : j['sector'] as String,
    status: j['status'] == null ? '' : j['status'] as String,
    isFastAlert: j['is_fast_alert'] == null ? false : j['is_fast_alert'] as bool,
    nextEvent: j['next_event'] == null ? null : EventOut.fromJson((j['next_event']) as Map<String, dynamic>),
    applicationEnd: j['application_end'] == null ? null : EventOut.fromJson((j['application_end']) as Map<String, dynamic>),
    examDate: j['exam_date'] == null ? null : EventOut.fromJson((j['exam_date']) as Map<String, dynamic>),
    categoryNumbers: j['category_numbers'] == null ? const [] : ((j['category_numbers']) as List).map((e) => e as String).toList(),
    vacanciesTotal: j['vacancies_total'] == null ? null : (j['vacancies_total'] as num).toInt(),
    hasChanges: j['has_changes'] == null ? false : j['has_changes'] as bool,
    officialUrl: j['official_url'] == null ? '' : j['official_url'] as String,
    lastCheckedAt: DateTime.parse(j['last_checked_at'] as String),
    updatedAt: DateTime.parse(j['updated_at'] as String),
  );
  Map<String, dynamic> toJson() => {
    'id': id,
    'title': title,
    'exam_name': examName,
    'organisation': organisation.toJson(),
    'sector': sector,
    'status': status,
    'is_fast_alert': isFastAlert,
    'next_event': nextEvent?.toJson(),
    'application_end': applicationEnd?.toJson(),
    'exam_date': examDate?.toJson(),
    'category_numbers': categoryNumbers,
    'vacancies_total': vacanciesTotal,
    'has_changes': hasChanges,
    'official_url': officialUrl,
    'last_checked_at': lastCheckedAt.toIso8601String(),
    'updated_at': updatedAt.toIso8601String(),
  };
}

class FeeOut {
  final int amount;
  final List<String> categories;
  final String? appliesTo;
  final List<String> exempted;
  const FeeOut({required this.amount, required this.categories, this.appliesTo, required this.exempted});
  factory FeeOut.fromJson(Map<String, dynamic> j) => FeeOut(
    amount: j['amount'] == null ? 0 : (j['amount'] as num).toInt(),
    categories: j['categories'] == null ? const [] : ((j['categories']) as List).map((e) => e as String).toList(),
    appliesTo: j['applies_to'] == null ? null : j['applies_to'] as String,
    exempted: j['exempted'] == null ? const [] : ((j['exempted']) as List).map((e) => e as String).toList(),
  );
  Map<String, dynamic> toJson() => {'amount': amount, 'categories': categories, 'applies_to': appliesTo, 'exempted': exempted};
}

class HTTPValidationError {
  final List<ValidationError>? detail;
  const HTTPValidationError({this.detail});
  factory HTTPValidationError.fromJson(Map<String, dynamic> j) => HTTPValidationError(
    detail: j['detail'] == null ? null : ((j['detail']) as List).map((e) => ValidationError.fromJson((e) as Map<String, dynamic>)).toList(),
  );
  Map<String, dynamic> toJson() => {'detail': detail?.map((e) => e.toJson()).toList()};
}

class LinkOut {
  final String kind;
  final String url;
  final String? label;
  final String host;
  const LinkOut({required this.kind, required this.url, this.label, required this.host});
  factory LinkOut.fromJson(Map<String, dynamic> j) => LinkOut(
    kind: j['kind'] == null ? '' : j['kind'] as String,
    url: j['url'] == null ? '' : j['url'] as String,
    label: j['label'] == null ? null : j['label'] as String,
    host: j['host'] == null ? '' : j['host'] as String,
  );
  Map<String, dynamic> toJson() => {'kind': kind, 'url': url, 'label': label, 'host': host};
}

class MetaOut {
  final String appName;
  final String disclaimer;
  final String privacyUrl;
  final String apiVersion;
  final String minAppVersion;
  final List<OrgOut> organisations;
  final List<Map<String, dynamic>> qualifications;
  final List<Map<String, dynamic>> keralaCommunities;
  final List<String> centralCategories;
  const MetaOut({
    required this.appName,
    required this.disclaimer,
    required this.privacyUrl,
    required this.apiVersion,
    required this.minAppVersion,
    required this.organisations,
    required this.qualifications,
    required this.keralaCommunities,
    required this.centralCategories,
  });
  factory MetaOut.fromJson(Map<String, dynamic> j) => MetaOut(
    appName: j['app_name'] == null ? '' : j['app_name'] as String,
    disclaimer: j['disclaimer'] == null ? '' : j['disclaimer'] as String,
    privacyUrl: j['privacy_url'] == null ? '' : j['privacy_url'] as String,
    apiVersion: j['api_version'] == null ? '' : j['api_version'] as String,
    minAppVersion: j['min_app_version'] == null ? '' : j['min_app_version'] as String,
    organisations:
        j['organisations'] == null
            ? const []
            : ((j['organisations']) as List).map((e) => OrgOut.fromJson((e) as Map<String, dynamic>)).toList(),
    qualifications:
        j['qualifications'] == null ? const [] : ((j['qualifications']) as List).map((e) => Map<String, dynamic>.from(e as Map)).toList(),
    keralaCommunities:
        j['kerala_communities'] == null
            ? const []
            : ((j['kerala_communities']) as List).map((e) => Map<String, dynamic>.from(e as Map)).toList(),
    centralCategories: j['central_categories'] == null ? const [] : ((j['central_categories']) as List).map((e) => e as String).toList(),
  );
  Map<String, dynamic> toJson() => {
    'app_name': appName,
    'disclaimer': disclaimer,
    'privacy_url': privacyUrl,
    'api_version': apiVersion,
    'min_app_version': minAppVersion,
    'organisations': organisations.map((e) => e.toJson()).toList(),
    'qualifications': qualifications,
    'kerala_communities': keralaCommunities,
    'central_categories': centralCategories,
  };
}

class MyExamOut {
  final ExamSummary exam;
  final String? status;
  final DateTime savedAt;
  const MyExamOut({required this.exam, this.status, required this.savedAt});
  factory MyExamOut.fromJson(Map<String, dynamic> j) => MyExamOut(
    exam: ExamSummary.fromJson((j['exam']) as Map<String, dynamic>),
    status: j['status'] == null ? null : j['status'] as String,
    savedAt: DateTime.parse(j['saved_at'] as String),
  );
  Map<String, dynamic> toJson() => {'exam': exam.toJson(), 'status': status, 'saved_at': savedAt.toIso8601String()};
}

class NewsOut {
  final int id;
  final String title;
  final String url;
  final String? publisher;
  final DateTime? publishedAt;
  final String? organisationKey;
  final bool verified;
  final String label;
  const NewsOut({
    required this.id,
    required this.title,
    required this.url,
    this.publisher,
    this.publishedAt,
    this.organisationKey,
    required this.verified,
    required this.label,
  });
  factory NewsOut.fromJson(Map<String, dynamic> j) => NewsOut(
    id: j['id'] == null ? 0 : (j['id'] as num).toInt(),
    title: j['title'] == null ? '' : j['title'] as String,
    url: j['url'] == null ? '' : j['url'] as String,
    publisher: j['publisher'] == null ? null : j['publisher'] as String,
    publishedAt: j['published_at'] == null ? null : DateTime.parse(j['published_at'] as String),
    organisationKey: j['organisation_key'] == null ? null : j['organisation_key'] as String,
    verified: j['verified'] == null ? false : j['verified'] as bool,
    label: j['label'] == null ? '' : j['label'] as String,
  );
  Map<String, dynamic> toJson() => {
    'id': id,
    'title': title,
    'url': url,
    'publisher': publisher,
    'published_at': publishedAt?.toIso8601String(),
    'organisation_key': organisationKey,
    'verified': verified,
    'label': label,
  };
}

class NoticeOut {
  final int id;
  final String title;
  final String? url;
  final String kind;
  final OrgOut organisation;
  final int? examId;
  final DateTime firstSeenAt;
  final String label;
  const NoticeOut({
    required this.id,
    required this.title,
    this.url,
    required this.kind,
    required this.organisation,
    this.examId,
    required this.firstSeenAt,
    required this.label,
  });
  factory NoticeOut.fromJson(Map<String, dynamic> j) => NoticeOut(
    id: j['id'] == null ? 0 : (j['id'] as num).toInt(),
    title: j['title'] == null ? '' : j['title'] as String,
    url: j['url'] == null ? null : j['url'] as String,
    kind: j['kind'] == null ? '' : j['kind'] as String,
    organisation: OrgOut.fromJson((j['organisation']) as Map<String, dynamic>),
    examId: j['exam_id'] == null ? null : (j['exam_id'] as num).toInt(),
    firstSeenAt: DateTime.parse(j['first_seen_at'] as String),
    label: j['label'] == null ? '' : j['label'] as String,
  );
  Map<String, dynamic> toJson() => {
    'id': id,
    'title': title,
    'url': url,
    'kind': kind,
    'organisation': organisation.toJson(),
    'exam_id': examId,
    'first_seen_at': firstSeenAt.toIso8601String(),
    'label': label,
  };
}

class NotificationOut {
  final int id;
  final String type;
  final String title;
  final String body;
  final String deepLink;
  final int? examId;
  final bool urgent;
  final DateTime createdAt;
  final bool read;
  const NotificationOut({
    required this.id,
    required this.type,
    required this.title,
    required this.body,
    required this.deepLink,
    this.examId,
    required this.urgent,
    required this.createdAt,
    required this.read,
  });
  factory NotificationOut.fromJson(Map<String, dynamic> j) => NotificationOut(
    id: j['id'] == null ? 0 : (j['id'] as num).toInt(),
    type: j['type'] == null ? '' : j['type'] as String,
    title: j['title'] == null ? '' : j['title'] as String,
    body: j['body'] == null ? '' : j['body'] as String,
    deepLink: j['deep_link'] == null ? '' : j['deep_link'] as String,
    examId: j['exam_id'] == null ? null : (j['exam_id'] as num).toInt(),
    urgent: j['urgent'] == null ? false : j['urgent'] as bool,
    createdAt: DateTime.parse(j['created_at'] as String),
    read: j['read'] == null ? false : j['read'] as bool,
  );
  Map<String, dynamic> toJson() => {
    'id': id,
    'type': type,
    'title': title,
    'body': body,
    'deep_link': deepLink,
    'exam_id': examId,
    'urgent': urgent,
    'created_at': createdAt.toIso8601String(),
    'read': read,
  };
}

class OrgOut {
  final String key;
  final String name;
  final String group;
  final String collection;
  const OrgOut({required this.key, required this.name, required this.group, required this.collection});
  factory OrgOut.fromJson(Map<String, dynamic> j) => OrgOut(
    key: j['key'] == null ? '' : j['key'] as String,
    name: j['name'] == null ? '' : j['name'] as String,
    group: j['group'] == null ? '' : j['group'] as String,
    collection: j['collection'] == null ? '' : j['collection'] as String,
  );
  Map<String, dynamic> toJson() => {'key': key, 'name': name, 'group': group, 'collection': collection};
}

class PageExamSummary {
  final List<ExamSummary> items;
  final int total;
  final int page;
  final int pageSize;
  const PageExamSummary({required this.items, required this.total, required this.page, required this.pageSize});
  factory PageExamSummary.fromJson(Map<String, dynamic> j) => PageExamSummary(
    items: j['items'] == null ? const [] : ((j['items']) as List).map((e) => ExamSummary.fromJson((e) as Map<String, dynamic>)).toList(),
    total: j['total'] == null ? 0 : (j['total'] as num).toInt(),
    page: j['page'] == null ? 0 : (j['page'] as num).toInt(),
    pageSize: j['page_size'] == null ? 0 : (j['page_size'] as num).toInt(),
  );
  Map<String, dynamic> toJson() => {'items': items.map((e) => e.toJson()).toList(), 'total': total, 'page': page, 'page_size': pageSize};
}

class PageNoticeOut {
  final List<NoticeOut> items;
  final int total;
  final int page;
  final int pageSize;
  const PageNoticeOut({required this.items, required this.total, required this.page, required this.pageSize});
  factory PageNoticeOut.fromJson(Map<String, dynamic> j) => PageNoticeOut(
    items: j['items'] == null ? const [] : ((j['items']) as List).map((e) => NoticeOut.fromJson((e) as Map<String, dynamic>)).toList(),
    total: j['total'] == null ? 0 : (j['total'] as num).toInt(),
    page: j['page'] == null ? 0 : (j['page'] as num).toInt(),
    pageSize: j['page_size'] == null ? 0 : (j['page_size'] as num).toInt(),
  );
  Map<String, dynamic> toJson() => {'items': items.map((e) => e.toJson()).toList(), 'total': total, 'page': page, 'page_size': pageSize};
}

class PhotoSpecOut {
  final int id;
  final String item;
  final int? minKb;
  final int? maxKb;
  final int? width;
  final int? height;
  final List<String> formats;
  final EvidenceOut? evidence;
  const PhotoSpecOut({
    required this.id,
    required this.item,
    this.minKb,
    this.maxKb,
    this.width,
    this.height,
    required this.formats,
    this.evidence,
  });
  factory PhotoSpecOut.fromJson(Map<String, dynamic> j) => PhotoSpecOut(
    id: j['id'] == null ? 0 : (j['id'] as num).toInt(),
    item: j['item'] == null ? '' : j['item'] as String,
    minKb: j['min_kb'] == null ? null : (j['min_kb'] as num).toInt(),
    maxKb: j['max_kb'] == null ? null : (j['max_kb'] as num).toInt(),
    width: j['width'] == null ? null : (j['width'] as num).toInt(),
    height: j['height'] == null ? null : (j['height'] as num).toInt(),
    formats: j['formats'] == null ? const [] : ((j['formats']) as List).map((e) => e as String).toList(),
    evidence: j['evidence'] == null ? null : EvidenceOut.fromJson((j['evidence']) as Map<String, dynamic>),
  );
  Map<String, dynamic> toJson() => {
    'id': id,
    'item': item,
    'min_kb': minKb,
    'max_kb': maxKb,
    'width': width,
    'height': height,
    'formats': formats,
    'evidence': evidence?.toJson(),
  };
}

class PostEligibility {
  final int postId;
  final String postName;
  final String status;
  final List<RuleResultOut> results;
  const PostEligibility({required this.postId, required this.postName, required this.status, required this.results});
  factory PostEligibility.fromJson(Map<String, dynamic> j) => PostEligibility(
    postId: j['post_id'] == null ? 0 : (j['post_id'] as num).toInt(),
    postName: j['post_name'] == null ? '' : j['post_name'] as String,
    status: j['status'] == null ? '' : j['status'] as String,
    results:
        j['results'] == null ? const [] : ((j['results']) as List).map((e) => RuleResultOut.fromJson((e) as Map<String, dynamic>)).toList(),
  );
  Map<String, dynamic> toJson() => {
    'post_id': postId,
    'post_name': postName,
    'status': status,
    'results': results.map((e) => e.toJson()).toList(),
  };
}

class PostOut {
  final int id;
  final String name;
  final String? department;
  final int? vacancies;
  final String? vacanciesText;
  final String? payScale;
  final String? categoryNumber;
  final List<RuleOut> rules;
  const PostOut({
    required this.id,
    required this.name,
    this.department,
    this.vacancies,
    this.vacanciesText,
    this.payScale,
    this.categoryNumber,
    required this.rules,
  });
  factory PostOut.fromJson(Map<String, dynamic> j) => PostOut(
    id: j['id'] == null ? 0 : (j['id'] as num).toInt(),
    name: j['name'] == null ? '' : j['name'] as String,
    department: j['department'] == null ? null : j['department'] as String,
    vacancies: j['vacancies'] == null ? null : (j['vacancies'] as num).toInt(),
    vacanciesText: j['vacancies_text'] == null ? null : j['vacancies_text'] as String,
    payScale: j['pay_scale'] == null ? null : j['pay_scale'] as String,
    categoryNumber: j['category_number'] == null ? null : j['category_number'] as String,
    rules: j['rules'] == null ? const [] : ((j['rules']) as List).map((e) => RuleOut.fromJson((e) as Map<String, dynamic>)).toList(),
  );
  Map<String, dynamic> toJson() => {
    'id': id,
    'name': name,
    'department': department,
    'vacancies': vacancies,
    'vacancies_text': vacanciesText,
    'pay_scale': payScale,
    'category_number': categoryNumber,
    'rules': rules.map((e) => e.toJson()).toList(),
  };
}

class PrefsOut {
  final List<String> enabledTypes;
  final Map<String, dynamic> interests;
  final String quietStart;
  final String quietEnd;
  final int maxPerDay;
  final bool digest;
  const PrefsOut({
    required this.enabledTypes,
    required this.interests,
    required this.quietStart,
    required this.quietEnd,
    required this.maxPerDay,
    required this.digest,
  });
  factory PrefsOut.fromJson(Map<String, dynamic> j) => PrefsOut(
    enabledTypes: j['enabled_types'] == null ? const [] : ((j['enabled_types']) as List).map((e) => e as String).toList(),
    interests: j['interests'] == null ? const {} : Map<String, dynamic>.from(j['interests'] as Map),
    quietStart: j['quiet_start'] == null ? '' : j['quiet_start'] as String,
    quietEnd: j['quiet_end'] == null ? '' : j['quiet_end'] as String,
    maxPerDay: j['max_per_day'] == null ? 0 : (j['max_per_day'] as num).toInt(),
    digest: j['digest'] == null ? false : j['digest'] as bool,
  );
  Map<String, dynamic> toJson() => {
    'enabled_types': enabledTypes,
    'interests': interests,
    'quiet_start': quietStart,
    'quiet_end': quietEnd,
    'max_per_day': maxPerDay,
    'digest': digest,
  };
}

class ProfileData {
  final DateTime? dateOfBirth;
  final String? category;
  final String? keralaCommunity;
  final bool? pwd;
  final bool? exServiceman;
  final String? gender;
  final String? nationality;
  final String? domicileState;
  final List<QualIn> qualifications;
  final List<String> languages;
  final Map<String, dynamic> attempts;
  const ProfileData({
    this.dateOfBirth,
    this.category,
    this.keralaCommunity,
    this.pwd,
    this.exServiceman,
    this.gender,
    this.nationality,
    this.domicileState,
    required this.qualifications,
    required this.languages,
    required this.attempts,
  });
  factory ProfileData.fromJson(Map<String, dynamic> j) => ProfileData(
    dateOfBirth: j['date_of_birth'] == null ? null : DateTime.parse(j['date_of_birth'] as String),
    category: j['category'] == null ? null : j['category'] as String,
    keralaCommunity: j['kerala_community'] == null ? null : j['kerala_community'] as String,
    pwd: j['pwd'] == null ? null : j['pwd'] as bool,
    exServiceman: j['ex_serviceman'] == null ? null : j['ex_serviceman'] as bool,
    gender: j['gender'] == null ? null : j['gender'] as String,
    nationality: j['nationality'] == null ? null : j['nationality'] as String,
    domicileState: j['domicile_state'] == null ? null : j['domicile_state'] as String,
    qualifications:
        j['qualifications'] == null
            ? const []
            : ((j['qualifications']) as List).map((e) => QualIn.fromJson((e) as Map<String, dynamic>)).toList(),
    languages: j['languages'] == null ? const [] : ((j['languages']) as List).map((e) => e as String).toList(),
    attempts: j['attempts'] == null ? const {} : Map<String, dynamic>.from(j['attempts'] as Map),
  );
  Map<String, dynamic> toJson() => {
    'date_of_birth': dateOfBirth?.toIso8601String().substring(0, 10),
    'category': category,
    'kerala_community': keralaCommunity,
    'pwd': pwd,
    'ex_serviceman': exServiceman,
    'gender': gender,
    'nationality': nationality,
    'domicile_state': domicileState,
    'qualifications': qualifications.map((e) => e.toJson()).toList(),
    'languages': languages,
    'attempts': attempts,
  };
}

class ProfileIn {
  final bool consent;
  final ProfileData data;
  const ProfileIn({required this.consent, required this.data});
  factory ProfileIn.fromJson(Map<String, dynamic> j) => ProfileIn(
    consent: j['consent'] == null ? false : j['consent'] as bool,
    data: ProfileData.fromJson((j['data']) as Map<String, dynamic>),
  );
  Map<String, dynamic> toJson() => {'consent': consent, 'data': data.toJson()};
}

class ProfileOut {
  final ProfileData? data;
  final DateTime? consentAt;
  final String purpose;
  const ProfileOut({this.data, this.consentAt, required this.purpose});
  factory ProfileOut.fromJson(Map<String, dynamic> j) => ProfileOut(
    data: j['data'] == null ? null : ProfileData.fromJson((j['data']) as Map<String, dynamic>),
    consentAt: j['consent_at'] == null ? null : DateTime.parse(j['consent_at'] as String),
    purpose: j['purpose'] == null ? '' : j['purpose'] as String,
  );
  Map<String, dynamic> toJson() => {'data': data?.toJson(), 'consent_at': consentAt?.toIso8601String(), 'purpose': purpose};
}

class QualIn {
  final String code;
  final String status;
  final double? percentage;
  const QualIn({required this.code, required this.status, this.percentage});
  factory QualIn.fromJson(Map<String, dynamic> j) => QualIn(
    code: j['code'] == null ? '' : j['code'] as String,
    status: j['status'] == null ? '' : j['status'] as String,
    percentage: j['percentage'] == null ? null : (j['percentage'] as num).toDouble(),
  );
  Map<String, dynamic> toJson() => {'code': code, 'status': status, 'percentage': percentage};
}

class RegisterIn {
  final String platform;
  final String? appVersion;
  final String? fcmToken;
  const RegisterIn({required this.platform, this.appVersion, this.fcmToken});
  factory RegisterIn.fromJson(Map<String, dynamic> j) => RegisterIn(
    platform: j['platform'] == null ? '' : j['platform'] as String,
    appVersion: j['app_version'] == null ? null : j['app_version'] as String,
    fcmToken: j['fcm_token'] == null ? null : j['fcm_token'] as String,
  );
  Map<String, dynamic> toJson() => {'platform': platform, 'app_version': appVersion, 'fcm_token': fcmToken};
}

class RegisterOut {
  final String token;
  final int userId;
  const RegisterOut({required this.token, required this.userId});
  factory RegisterOut.fromJson(Map<String, dynamic> j) =>
      RegisterOut(token: j['token'] == null ? '' : j['token'] as String, userId: j['user_id'] == null ? 0 : (j['user_id'] as num).toInt());
  Map<String, dynamic> toJson() => {'token': token, 'user_id': userId};
}

class RuleOut {
  final String ruleType;
  final Map<String, dynamic> params;
  final String? clause;
  final EvidenceOut? evidence;
  const RuleOut({required this.ruleType, required this.params, this.clause, this.evidence});
  factory RuleOut.fromJson(Map<String, dynamic> j) => RuleOut(
    ruleType: j['rule_type'] == null ? '' : j['rule_type'] as String,
    params: j['params'] == null ? const {} : Map<String, dynamic>.from(j['params'] as Map),
    clause: j['clause'] == null ? null : j['clause'] as String,
    evidence: j['evidence'] == null ? null : EvidenceOut.fromJson((j['evidence']) as Map<String, dynamic>),
  );
  Map<String, dynamic> toJson() => {'rule_type': ruleType, 'params': params, 'clause': clause, 'evidence': evidence?.toJson()};
}

class RuleResultOut {
  final String ruleType;
  final String outcome;
  final String? userValue;
  final String requirement;
  final String explanation;
  final String? clause;
  final String? sourceUrl;
  final int? page;
  const RuleResultOut({
    required this.ruleType,
    required this.outcome,
    this.userValue,
    required this.requirement,
    required this.explanation,
    this.clause,
    this.sourceUrl,
    this.page,
  });
  factory RuleResultOut.fromJson(Map<String, dynamic> j) => RuleResultOut(
    ruleType: j['rule_type'] == null ? '' : j['rule_type'] as String,
    outcome: j['outcome'] == null ? '' : j['outcome'] as String,
    userValue: j['user_value'] == null ? null : j['user_value'] as String,
    requirement: j['requirement'] == null ? '' : j['requirement'] as String,
    explanation: j['explanation'] == null ? '' : j['explanation'] as String,
    clause: j['clause'] == null ? null : j['clause'] as String,
    sourceUrl: j['source_url'] == null ? null : j['source_url'] as String,
    page: j['page'] == null ? null : (j['page'] as num).toInt(),
  );
  Map<String, dynamic> toJson() => {
    'rule_type': ruleType,
    'outcome': outcome,
    'user_value': userValue,
    'requirement': requirement,
    'explanation': explanation,
    'clause': clause,
    'source_url': sourceUrl,
    'page': page,
  };
}

class ScamEvidenceOut {
  final String level;
  final String text;
  final String? url;
  const ScamEvidenceOut({required this.level, required this.text, this.url});
  factory ScamEvidenceOut.fromJson(Map<String, dynamic> j) => ScamEvidenceOut(
    level: j['level'] == null ? '' : j['level'] as String,
    text: j['text'] == null ? '' : j['text'] as String,
    url: j['url'] == null ? null : j['url'] as String,
  );
  Map<String, dynamic> toJson() => {'level': level, 'text': text, 'url': url};
}

class ScamIn {
  final String kind;
  final String value;
  const ScamIn({required this.kind, required this.value});
  factory ScamIn.fromJson(Map<String, dynamic> j) =>
      ScamIn(kind: j['kind'] == null ? '' : j['kind'] as String, value: j['value'] == null ? '' : j['value'] as String);
  Map<String, dynamic> toJson() => {'kind': kind, 'value': value};
}

class ScamOut {
  final int id;
  final String verdict;
  final List<ScamEvidenceOut> evidence;
  final String disclaimer;
  const ScamOut({required this.id, required this.verdict, required this.evidence, required this.disclaimer});
  factory ScamOut.fromJson(Map<String, dynamic> j) => ScamOut(
    id: j['id'] == null ? 0 : (j['id'] as num).toInt(),
    verdict: j['verdict'] == null ? '' : j['verdict'] as String,
    evidence:
        j['evidence'] == null
            ? const []
            : ((j['evidence']) as List).map((e) => ScamEvidenceOut.fromJson((e) as Map<String, dynamic>)).toList(),
    disclaimer: j['disclaimer'] == null ? '' : j['disclaimer'] as String,
  );
  Map<String, dynamic> toJson() => {
    'id': id,
    'verdict': verdict,
    'evidence': evidence.map((e) => e.toJson()).toList(),
    'disclaimer': disclaimer,
  };
}

class SourceStatusOut {
  final String key;
  final String? organisation;
  final String url;
  final String kind;
  final bool isOfficial;
  final String status;
  final String? collection;
  final DateTime? lastSuccessAt;
  final DateTime? lastAttemptAt;
  final DateTime? lastNewItemAt;
  final double? errorRate;
  final int? lastParserYield;
  final String? note;
  const SourceStatusOut({
    required this.key,
    this.organisation,
    required this.url,
    required this.kind,
    required this.isOfficial,
    required this.status,
    this.collection,
    this.lastSuccessAt,
    this.lastAttemptAt,
    this.lastNewItemAt,
    this.errorRate,
    this.lastParserYield,
    this.note,
  });
  factory SourceStatusOut.fromJson(Map<String, dynamic> j) => SourceStatusOut(
    key: j['key'] == null ? '' : j['key'] as String,
    organisation: j['organisation'] == null ? null : j['organisation'] as String,
    url: j['url'] == null ? '' : j['url'] as String,
    kind: j['kind'] == null ? '' : j['kind'] as String,
    isOfficial: j['is_official'] == null ? false : j['is_official'] as bool,
    status: j['status'] == null ? '' : j['status'] as String,
    collection: j['collection'] == null ? null : j['collection'] as String,
    lastSuccessAt: j['last_success_at'] == null ? null : DateTime.parse(j['last_success_at'] as String),
    lastAttemptAt: j['last_attempt_at'] == null ? null : DateTime.parse(j['last_attempt_at'] as String),
    lastNewItemAt: j['last_new_item_at'] == null ? null : DateTime.parse(j['last_new_item_at'] as String),
    errorRate: j['error_rate'] == null ? null : (j['error_rate'] as num).toDouble(),
    lastParserYield: j['last_parser_yield'] == null ? null : (j['last_parser_yield'] as num).toInt(),
    note: j['note'] == null ? null : j['note'] as String,
  );
  Map<String, dynamic> toJson() => {
    'key': key,
    'organisation': organisation,
    'url': url,
    'kind': kind,
    'is_official': isOfficial,
    'status': status,
    'collection': collection,
    'last_success_at': lastSuccessAt?.toIso8601String(),
    'last_attempt_at': lastAttemptAt?.toIso8601String(),
    'last_new_item_at': lastNewItemAt?.toIso8601String(),
    'error_rate': errorRate,
    'last_parser_yield': lastParserYield,
    'note': note,
  };
}

class StatusIn {
  final String status;
  const StatusIn({required this.status});
  factory StatusIn.fromJson(Map<String, dynamic> j) => StatusIn(status: j['status'] == null ? '' : j['status'] as String);
  Map<String, dynamic> toJson() => {'status': status};
}

class ValidationError {
  final List<String> loc;
  final String msg;
  final String type;
  final dynamic input;
  final Map<String, dynamic>? ctx;
  const ValidationError({required this.loc, required this.msg, required this.type, required this.input, this.ctx});
  factory ValidationError.fromJson(Map<String, dynamic> j) => ValidationError(
    loc: j['loc'] == null ? const [] : ((j['loc']) as List).map((e) => e as String).toList(),
    msg: j['msg'] == null ? '' : j['msg'] as String,
    type: j['type'] == null ? '' : j['type'] as String,
    input: j['input'],
    ctx: j['ctx'] == null ? null : Map<String, dynamic>.from(j['ctx'] as Map),
  );
  Map<String, dynamic> toJson() => {'loc': loc, 'msg': msg, 'type': type, 'input': input, 'ctx': ctx};
}
