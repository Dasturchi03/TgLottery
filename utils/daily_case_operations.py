from datetime import datetime

from utils.daily_case import CASE_COOLDOWN, CaseOutcome, CasePrize
from utils.models import Users, db


def record_terminal_outcome(user_id: int, outcome: CaseOutcome, opened_at: datetime) -> bool:
    if not outcome.is_terminal:
        raise ValueError('Reroll is not a terminal case outcome')

    values = {
        Users.daily_case_opened_at: opened_at,
        Users.daily_case_notification_claimed_at: None,
        Users.daily_case_notification_sent_at: None,
    }
    if outcome.prize is CasePrize.DIAMONDS:
        values[Users.prize_balance] = Users.prize_balance + outcome.amount

    cooldown_cutoff = opened_at - CASE_COOLDOWN
    availability = (
        Users.daily_case_opened_at.is_null(True)
        | (Users.daily_case_opened_at <= cooldown_cutoff)
    )
    with db.atomic():
        updated = (Users.update(values)
                   .where((Users.user_id == user_id) & availability)
                   .execute())
    return updated == 1
