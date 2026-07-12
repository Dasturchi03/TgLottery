from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from enum import Enum
from random import Random, SystemRandom


CASE_COOLDOWN = timedelta(hours=24)


def utc_now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


class CasePrize(str, Enum):
    EMPTY = 'empty'
    DICE_ATTEMPTS = 'dice_attempts'
    DIAMONDS = 'diamonds'
    REROLL = 'reroll'


@dataclass(frozen=True)
class CaseOutcome:
    prize: CasePrize
    amount: int
    roll: int

    @property
    def is_terminal(self) -> bool:
        return self.prize is not CasePrize.REROLL


def resolve_case_roll(roll: int) -> CaseOutcome:
    if not isinstance(roll, int) or isinstance(roll, bool) or not 1 <= roll <= 100:
        raise ValueError('Case roll must be an integer from 1 to 100')
    if roll <= 25:
        return CaseOutcome(CasePrize.EMPTY, 0, roll)
    if roll <= 48:
        return CaseOutcome(CasePrize.DICE_ATTEMPTS, 1, roll)
    if roll <= 68:
        return CaseOutcome(CasePrize.DIAMONDS, 1, roll)
    if roll <= 79:
        return CaseOutcome(CasePrize.DICE_ATTEMPTS, 2, roll)
    if roll <= 86:
        return CaseOutcome(CasePrize.DIAMONDS, 2, roll)
    if roll <= 90:
        return CaseOutcome(CasePrize.DICE_ATTEMPTS, 3, roll)
    if roll <= 93:
        return CaseOutcome(CasePrize.DIAMONDS, 3, roll)
    return CaseOutcome(CasePrize.REROLL, 0, roll)


def draw_case_outcome(rng: Random | SystemRandom | None = None) -> CaseOutcome:
    rng = rng or SystemRandom()
    return resolve_case_roll(rng.randint(1, 100))


def normalize_db_datetime(value: datetime | str | None) -> datetime | None:
    if value is None or isinstance(value, datetime):
        return value
    return datetime.fromisoformat(value)


def case_available_at(last_opened_at: datetime | str | None) -> datetime | None:
    last_opened_at = normalize_db_datetime(last_opened_at)
    return last_opened_at + CASE_COOLDOWN if last_opened_at else None


def case_remaining(last_opened_at: datetime | str | None, now: datetime | None = None) -> timedelta:
    available_at = case_available_at(last_opened_at)
    if not available_at:
        return timedelta(0)
    now = now or utc_now()
    return max(timedelta(0), available_at - now)


def is_case_available(last_opened_at: datetime | str | None, now: datetime | None = None) -> bool:
    return case_remaining(last_opened_at, now) <= timedelta(0)


def format_remaining(remaining: timedelta) -> str:
    total_minutes = max(0, int((remaining.total_seconds() + 59) // 60))
    hours, minutes = divmod(total_minutes, 60)
    return f'{hours:02d}:{minutes:02d}'


def daily_case_button_text(last_opened_at: datetime | str | None, now: datetime | None = None) -> str:
    remaining = case_remaining(last_opened_at, now)
    if remaining <= timedelta(0):
        return '🎁 Ежедневный кейс'
    return f'⏳ Кейс ({format_remaining(remaining)})'


def outcome_text(outcome: CaseOutcome) -> str:
    if outcome.prize is CasePrize.EMPTY:
        return '😢 Увы! В этот раз пусто. Возвращайтесь завтра!'
    if outcome.prize is CasePrize.DIAMONDS:
        return f'🎉 Поздравляем! Начислено {outcome.amount} 💎.'
    if outcome.prize is CasePrize.DICE_ATTEMPTS:
        return f'🎉 Поздравляем! Добавлено попыток в игре «Кости»: +{outcome.amount}.'
    return '🔥 ВАУ! ПОВТОРНЫЙ РОЗЫГРЫШ! Сейчас крутим кейс ещё раз...'
