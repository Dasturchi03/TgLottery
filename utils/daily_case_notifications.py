from datetime import datetime, timedelta

from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError

from utils.daily_case import CASE_COOLDOWN, utc_now
from utils.keyboards import daily_case_notification_kb
from utils.models import Users, db


NOTIFICATION_CLAIM_LEASE = timedelta(minutes=10)


def claim_ready_case_notifications(now: datetime, limit: int = 100) -> list[int]:
    ready_cutoff = now - CASE_COOLDOWN
    stale_claim_cutoff = now - NOTIFICATION_CLAIM_LEASE
    candidates = (Users.select(Users.id)
                  .where(
                      (Users.inactive == False)
                      & Users.daily_case_opened_at.is_null(False)
                      & (Users.daily_case_opened_at <= ready_cutoff)
                      & Users.daily_case_notification_sent_at.is_null(True)
                      & (
                          Users.daily_case_notification_claimed_at.is_null(True)
                          | (Users.daily_case_notification_claimed_at <= stale_claim_cutoff)
                      )
                  )
                  .limit(limit))

    claimed_ids = []
    with db.atomic():
        for candidate in candidates:
            claimed = (Users.update(daily_case_notification_claimed_at=now)
                       .where(
                           (Users.id == candidate.id)
                           & Users.daily_case_notification_sent_at.is_null(True)
                           & (
                               Users.daily_case_notification_claimed_at.is_null(True)
                               | (Users.daily_case_notification_claimed_at <= stale_claim_cutoff)
                           )
                       )
                       .execute())
            if claimed:
                claimed_ids.append(candidate.id)
    return claimed_ids


def complete_case_notification(user_id: int, sent_at: datetime, claimed_at: datetime) -> bool:
    updated = (Users.update(
        daily_case_notification_sent_at=sent_at,
        daily_case_notification_claimed_at=None,
    ).where(
        (Users.id == user_id)
        & (Users.daily_case_notification_claimed_at == claimed_at)
    ).execute())
    return updated == 1


def release_case_notification_claim(user_id: int, claimed_at: datetime) -> None:
    (Users.update(daily_case_notification_claimed_at=None)
     .where(
         (Users.id == user_id)
         & Users.daily_case_notification_sent_at.is_null(True)
         & (Users.daily_case_notification_claimed_at == claimed_at)
     ).execute())


async def send_ready_case_notifications(bot, *, now: datetime | None = None, limit: int = 100) -> dict[str, int]:
    now = now or utc_now()
    claimed_ids = claim_ready_case_notifications(now, limit)
    stats = {'claimed': len(claimed_ids), 'sent': 0, 'unavailable': 0, 'failed': 0}

    for user_id in claimed_ids:
        user = Users.get_by_id(user_id)
        try:
            await bot.send_message(
                user.user_id,
                '📦 Кейс снова можно открыть!',
                reply_markup=daily_case_notification_kb(),
                disable_notification=True,
            )
        except (TelegramBadRequest, TelegramForbiddenError):
            user.inactive = True
            user.save(only=[Users.inactive])
            complete_case_notification(user.id, utc_now(), now)
            stats['unavailable'] += 1
        except Exception as error:
            print(f'[{user.user_id}] Daily case notification failed: {error}')
            release_case_notification_claim(user.id, now)
            stats['failed'] += 1
        else:
            complete_case_notification(user.id, utc_now(), now)
            stats['sent'] += 1
    return stats
