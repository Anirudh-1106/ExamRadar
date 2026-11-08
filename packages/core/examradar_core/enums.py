"""Controlled vocabularies shared by the pipeline, API, and app."""

EVENT_TYPES = {
    "upcoming_notice": "Upcoming notice",
    "notification": "Notification published",
    "application_start": "Applications open",
    "application_end": "Last date to apply",
    "fee_deadline": "Last date for fee payment",
    "correction_window": "Correction window",
    "confirmation_deadline": "Last date for confirmation",
    "exam_city": "Exam city intimation",
    "admit_card": "Admit card available",
    "exam": "Exam date",
    "answer_key": "Answer key",
    "objection_deadline": "Last date for objections",
    "result": "Result",
    "cut_off": "Cut-off marks",
    "short_list": "Short list published",
    "ranked_list": "Ranked list published",
    "document_verification": "Document verification",
    "interview": "Interview",
    "postponement": "Postponed",
    "cancellation": "Cancelled",
}

# Events whose date is a deadline the user must act before.
DEADLINE_EVENTS = {"application_end", "fee_deadline", "confirmation_deadline", "objection_deadline"}

CERTAINTY = ("official", "tentative", "expected")
# Only these certainties may drive reminders that imply a real deadline.
REMINDER_CERTAINTY = {"official", "tentative"}

NOTIFICATION_TYPES = {
    "new_notice": "New official notice detected",
    "new_matching_exam": "New exam that matches you",
    "application_opening": "Applications opening",
    "deadline_7": "Deadline in 7 days",
    "deadline_3": "Deadline in 3 days",
    "deadline_1": "Deadline tomorrow",
    "confirmation_deadline": "Confirmation deadline",
    "date_change": "Date changed",
    "link_change": "Link changed",
    "correction_window": "Correction window",
    "admit_card": "Admit card",
    "answer_key": "Answer key",
    "objection_deadline": "Objection deadline",
    "result": "Result",
    "correction": "Correction to an earlier update",
}
URGENT_TYPES = {"deadline_1", "confirmation_deadline", "correction"}

TRACKING_STATUSES = ("interested", "applied", "confirmed", "admit_card", "exam_taken", "result_checked")

SECTORS = ("psc", "civil_services", "banking", "railway", "teaching", "devaswom", "defence", "engineering", "other")
