from __future__ import annotations

from datetime import datetime, timedelta
import secrets

from flask import (
    Blueprint,
    flash,
    g,
    redirect,
    render_template,
    request,
    session,
    url_for,
)
from ..extensions import db
from ..metrics import EVENTS
from ..models import Quest, Referral, User, UserQuest
from ..utils.decorators import login_required
from ..utils.nudges import resolve_opt_out_token
from ..utils.track import track

bp = Blueprint("engagement", __name__, url_prefix="/engage")


def _get_user() -> User | None:
    cached = getattr(g, "_engagement_user", None)
    if cached is not None:
        return cached

    username = session.get("user")
    if not username:
        g._engagement_user = None
        return None

    user = User.query.filter_by(username=username).first()
    g._engagement_user = user
    if user is not None:
        g.user = user
        g.user_id = user.id
    return user


def _today_range() -> tuple[datetime, datetime]:
    now = datetime.utcnow()
    start = datetime(now.year, now.month, now.day)
    return start, start + timedelta(days=1)


@bp.route("/hub")
@login_required
def hub():
    user = _get_user()
    if not user:
        flash("Please login to continue.", "warning")
        return redirect(url_for("auth.login"))

    start, end = _today_range()
    rows = (
        db.session.query(Quest.title, UserQuest.completed_at)
        .join(Quest, Quest.id == UserQuest.quest_id)
        .filter(
            UserQuest.user_id == user.id,
            UserQuest.completed_at >= start,
            UserQuest.completed_at < end,
        )
        .order_by(UserQuest.completed_at.desc())
        .all()
    )
    completed = [
        {"title": title, "completed_at": completed_at} for title, completed_at in rows
    ]

    quests = Quest.query.order_by(Quest.created_at.asc()).all()

    stats = {
        "streak_count": user.streak_count or 0,
        "xp": user.xp or 0,
        "last_active_at": user.last_active_at,
    }

    track(EVENTS["APP_OPEN"], {"surface": "engagement_hub"}, user_id=user.id)
    return render_template(
        "engagement/hub.html",
        user=user,
        last=stats,
        quests=quests,
        completed=completed,
    )


@bp.post("/complete")
@login_required
def complete():
    user = _get_user()
    if not user:
        flash("Please login to continue.", "warning")
        return redirect(url_for("auth.login"))

    quest_code = (request.form.get("code") or "").strip().upper()
    quest = Quest.query.filter_by(code=quest_code).first()
    if not quest:
        flash("Quest not found.", "danger")
        return redirect(url_for("engagement.hub"))

    start, end = _today_range()
    daily_limit = quest.daily_limit or 1
    completed_today = (
        db.session.query(UserQuest.id)
        .filter(
            UserQuest.user_id == user.id,
            UserQuest.quest_id == quest.id,
            UserQuest.completed_at >= start,
            UserQuest.completed_at < end,
        )
        .count()
    )
    if quest.is_recurring and completed_today >= daily_limit:
        flash("Daily limit reached. Come back tomorrow.", "warning")
        return redirect(url_for("engagement.hub"))

    previous_streak = user.streak_count or 0
    now = datetime.utcnow()
    last_active = user.last_active_at.date() if user.last_active_at else None
    today = now.date()
    if last_active is None:
        streak = 1
    else:
        delta = (today - last_active).days
        if delta == 0:
            streak = user.streak_count or 1
        elif delta == 1:
            streak = (user.streak_count or 0) + 1
        else:
            streak = 1

    user_quest = UserQuest(user_id=user.id, quest_id=quest.id, completed_at=now)
    user.last_active_at = now
    user.streak_count = streak
    user.xp = (user.xp or 0) + quest.xp_reward

    db.session.add(user_quest)
    db.session.add(user)
    db.session.commit()

    track(
        EVENTS["QUEST_COMPLETED"],
        {"code": quest.code, "xp": quest.xp_reward},
        user_id=user.id,
    )
    track(
        EVENTS["CORE_ACTION"],
        {"code": quest.code},
        user_id=user.id,
    )
    if streak > previous_streak:
        track(EVENTS["STREAK_EXTENDED"], {"streak": streak}, user_id=user.id)

    flash(f"Nice! +{quest.xp_reward} XP", "success")
    return redirect(url_for("engagement.hub"))


@bp.route("/ref")
@login_required
def referral():
    user = _get_user()
    if not user:
        flash("Please login to continue.", "warning")
        return redirect(url_for("auth.login"))

    referral = Referral.query.filter_by(inviter_id=user.id).first()
    if not referral:
        code = secrets.token_urlsafe(6)
        referral = Referral(inviter_id=user.id, code=code)
        db.session.add(referral)
        db.session.commit()
        track(EVENTS["REFERRAL_CREATED"], {"code": code}, user_id=user.id)
    else:
        code = referral.code

    link = url_for("auth.register", ref=code, _external=True)
    return render_template("engagement/ref.html", link=link, user=user)


@bp.route("/opt-out/<token>")
def opt_out(token: str):
    user_id = resolve_opt_out_token(token)
    if not user_id:
        flash("Opt-out link expired or invalid.", "warning")
        return redirect(url_for("marketing.landing"))

    user = User.query.get(user_id)
    if not user:
        flash("Account not found.", "warning")
        return redirect(url_for("marketing.landing"))

    user.engagement_opt_out = True
    db.session.add(user)
    db.session.commit()
    flash("You will no longer receive WhatsApp nudges. Come back anytime to opt in.", "info")
    return redirect(url_for("marketing.landing"))
