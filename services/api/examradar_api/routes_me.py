"""Personal endpoints. Accounts are anonymous device tokens; nothing is collected until a feature needs it."""

import secrets
from datetime import date

from examradar_core.models import (
    Device,
    ExamCycle,
    Notification,
    NotificationPreference,
    SavedExam,
    User,
    UserChecklistItem,
    UserExamStatus,
    UserProfile,
)
from examradar_core.timeutil import utcnow
from examradar_eligibility import Profile
from examradar_worker.notify import DEFAULT_TYPES, prefs_for
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from . import schemas as S
from . import services as svc
from .deps import current_user, get_db, today, token_hash

router = APIRouter(prefix="/v1", tags=["me"])
CONSENT_VERSION = "2026-11"


@router.post("/devices/register", response_model=S.RegisterOut)
def register(body: S.RegisterIn, s: Session = Depends(get_db)):
    token = secrets.token_urlsafe(32)
    u = User(token_hash=token_hash(token))
    s.add(u)
    s.flush()
    s.add(Device(user_id=u.id, platform=body.platform, fcm_token=body.fcm_token, app_version=body.app_version))
    s.add(NotificationPreference(user_id=u.id, enabled_types=list(DEFAULT_TYPES), interests={}))
    return S.RegisterOut(token=token, user_id=u.id)


@router.put("/me/device", status_code=204)
def update_device(body: S.DeviceIn, u: User = Depends(current_user), s: Session = Depends(get_db)):
    d = s.scalar(select(Device).where(Device.user_id == u.id).order_by(Device.id.desc()))
    if d is None:
        d = Device(user_id=u.id)
        s.add(d)
    d.fcm_token, d.app_version, d.last_seen_at = body.fcm_token, body.app_version or d.app_version, utcnow()


@router.get("/me/profile", response_model=S.ProfileOut)
def get_profile(u: User = Depends(current_user), s: Session = Depends(get_db)):
    p = s.get(UserProfile, u.id)
    return S.ProfileOut(data=S.ProfileData(**p.data) if p else None, consent_at=u.consent_at,
                        purpose="Used only to check eligibility and send alerts that match you. Never sold or shared.")


@router.put("/me/profile", response_model=S.ProfileOut)
def put_profile(body: S.ProfileIn, u: User = Depends(current_user), s: Session = Depends(get_db)):
    if not body.consent:
        raise HTTPException(422, "Consent is required to store your profile. You can keep it on your phone instead.")
    p = s.get(UserProfile, u.id)
    data = body.data.model_dump(mode="json")
    if p is None:
        s.add(UserProfile(user_id=u.id, data=data))
    else:
        p.data, p.updated_at = data, utcnow()
    u.consent_version, u.consent_at = CONSENT_VERSION, utcnow()
    return get_profile(u, s)


@router.delete("/me/profile", status_code=204)
def delete_profile(u: User = Depends(current_user), s: Session = Depends(get_db)):
    s.execute(delete(UserProfile).where(UserProfile.user_id == u.id))
    u.consent_at = None


@router.get("/me/eligibility", response_model=list[S.ExamEligibility])
def my_eligibility(u: User = Depends(current_user), s: Session = Depends(get_db), d: date = Depends(today)):
    p = s.get(UserProfile, u.id)
    if p is None:
        raise HTTPException(404, "No saved profile. Use /v1/eligibility/evaluate to check without saving.")
    profile = Profile.from_dict(p.data)
    ids = set(s.scalars(select(SavedExam.exam_cycle_id).where(SavedExam.user_id == u.id)))
    return [svc.eligibility(s, c, profile) for c in (s.get(ExamCycle, i) for i in ids) if c and not c.retracted]


@router.get("/me/exams", response_model=list[S.MyExamOut])
def my_exams(u: User = Depends(current_user), s: Session = Depends(get_db), d: date = Depends(today)):
    out = []
    for se in s.scalars(select(SavedExam).where(SavedExam.user_id == u.id).order_by(SavedExam.created_at.desc())):
        c = s.get(ExamCycle, se.exam_cycle_id)
        if not c or c.retracted:
            continue
        st = s.scalar(select(UserExamStatus.status).where(UserExamStatus.user_id == u.id, UserExamStatus.exam_cycle_id == c.id))
        out.append(S.MyExamOut(exam=svc.summary(s, c, d), status=st, saved_at=se.created_at))
    return out


@router.put("/me/exams/{exam_id}", status_code=204)
def save_exam(exam_id: int, u: User = Depends(current_user), s: Session = Depends(get_db)):
    if s.get(ExamCycle, exam_id) is None:
        raise HTTPException(404, "Exam not found")
    if not s.scalar(select(SavedExam.id).where(SavedExam.user_id == u.id, SavedExam.exam_cycle_id == exam_id)):
        s.add(SavedExam(user_id=u.id, exam_cycle_id=exam_id))


@router.delete("/me/exams/{exam_id}", status_code=204)
def unsave_exam(exam_id: int, u: User = Depends(current_user), s: Session = Depends(get_db)):
    s.execute(delete(SavedExam).where(SavedExam.user_id == u.id, SavedExam.exam_cycle_id == exam_id))
    s.execute(delete(UserExamStatus).where(UserExamStatus.user_id == u.id, UserExamStatus.exam_cycle_id == exam_id))


@router.put("/me/exams/{exam_id}/status", status_code=204)
def set_status(exam_id: int, body: S.StatusIn, u: User = Depends(current_user), s: Session = Depends(get_db)):
    save_exam(exam_id, u, s)
    row = s.scalar(select(UserExamStatus).where(UserExamStatus.user_id == u.id, UserExamStatus.exam_cycle_id == exam_id))
    if row is None:
        row = UserExamStatus(user_id=u.id, exam_cycle_id=exam_id, status=body.status, history=[])
        s.add(row)
    row.history = (row.history or []) + [{"status": body.status, "at": utcnow().isoformat()}]
    row.status, row.updated_at = body.status, utcnow()


@router.put("/me/exams/{exam_id}/checklist/{key}", status_code=204)
def set_check(exam_id: int, key: str, done: bool = True, u: User = Depends(current_user), s: Session = Depends(get_db)):
    row = s.scalar(select(UserChecklistItem).where(UserChecklistItem.user_id == u.id, UserChecklistItem.exam_cycle_id == exam_id,
                                                   UserChecklistItem.item_key == key[:120]))
    if row is None:
        s.add(UserChecklistItem(user_id=u.id, exam_cycle_id=exam_id, item_key=key[:120], done=done))
    else:
        row.done, row.updated_at = done, utcnow()


@router.get("/me/preferences", response_model=S.PrefsOut)
def get_prefs(u: User = Depends(current_user), s: Session = Depends(get_db)):
    p = prefs_for(s, u.id)
    return S.PrefsOut(enabled_types=p.enabled_types, interests={k: list(v) for k, v in (p.interests or {}).items()},
                      quiet_start=p.quiet_start, quiet_end=p.quiet_end, max_per_day=p.max_per_day, digest=p.digest)


@router.put("/me/preferences", response_model=S.PrefsOut)
def put_prefs(body: S.PrefsOut, u: User = Depends(current_user), s: Session = Depends(get_db)):
    p = prefs_for(s, u.id)
    p.enabled_types = [t for t in body.enabled_types if t in DEFAULT_TYPES]
    p.interests = {k: v[:50] for k, v in body.interests.items() if k in ("organisations", "groups", "sectors")}
    p.quiet_start, p.quiet_end = body.quiet_start[:5], body.quiet_end[:5]
    p.max_per_day, p.digest, p.updated_at = max(1, min(body.max_per_day, 20)), body.digest, utcnow()
    return get_prefs(u, s)


@router.get("/me/notifications", response_model=list[S.NotificationOut])
def inbox(limit: int = 50, u: User = Depends(current_user), s: Session = Depends(get_db)):
    rows = s.scalars(select(Notification).where(Notification.user_id == u.id).order_by(Notification.id.desc()).limit(min(limit, 200)))
    return [S.NotificationOut(id=n.id, type=n.type, title=n.title, body=n.body, deep_link=n.deep_link, exam_id=n.exam_cycle_id,
                              urgent=n.urgent, created_at=n.created_at, read=n.read_at is not None) for n in rows]


@router.post("/me/notifications/read", status_code=204)
def mark_read(ids: list[int], u: User = Depends(current_user), s: Session = Depends(get_db)):
    for n in s.scalars(select(Notification).where(Notification.user_id == u.id, Notification.id.in_(ids[:500]))):
        n.read_at = n.read_at or utcnow()


@router.get("/me/export")
def export(u: User = Depends(current_user), s: Session = Depends(get_db)):
    """Everything we hold about this account, as JSON (DPDP right to access)."""
    p = s.get(UserProfile, u.id)
    pref = prefs_for(s, u.id)
    return {
        "account": {"user_id": u.id, "created_at": u.created_at, "consent_version": u.consent_version, "consent_at": u.consent_at},
        "profile": p.data if p else None,
        "saved_exams": [{"exam_id": x.exam_cycle_id, "saved_at": x.created_at} for x in s.scalars(select(SavedExam).where(SavedExam.user_id == u.id))],
        "statuses": [{"exam_id": x.exam_cycle_id, "status": x.status, "history": x.history}
                     for x in s.scalars(select(UserExamStatus).where(UserExamStatus.user_id == u.id))],
        "checklist": [{"exam_id": x.exam_cycle_id, "item": x.item_key, "done": x.done}
                      for x in s.scalars(select(UserChecklistItem).where(UserChecklistItem.user_id == u.id))],
        "preferences": {"enabled_types": pref.enabled_types, "interests": pref.interests, "quiet_start": pref.quiet_start,
                        "quiet_end": pref.quiet_end, "max_per_day": pref.max_per_day},
        "devices": [{"platform": d.platform, "has_push_token": bool(d.fcm_token), "app_version": d.app_version, "created_at": d.created_at}
                    for d in s.scalars(select(Device).where(Device.user_id == u.id))],
        "notifications": [{"title": n.title, "created_at": n.created_at} for n in s.scalars(select(Notification).where(Notification.user_id == u.id))],
    }


@router.delete("/me", status_code=204)
def delete_account(u: User = Depends(current_user), s: Session = Depends(get_db)):
    """Deletes the account and everything linked to it. Cannot be undone."""
    from examradar_core.models import NotificationDelivery

    nids = list(s.scalars(select(Notification.id).where(Notification.user_id == u.id)))
    if nids:
        s.execute(delete(NotificationDelivery).where(NotificationDelivery.notification_id.in_(nids)))
    for model in (Notification, Device, SavedExam, UserExamStatus, UserChecklistItem):
        s.execute(delete(model).where(model.user_id == u.id))
    s.execute(delete(UserProfile).where(UserProfile.user_id == u.id))
    s.execute(delete(NotificationPreference).where(NotificationPreference.user_id == u.id))
    s.delete(u)
