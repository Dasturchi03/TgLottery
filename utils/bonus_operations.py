from collections.abc import Iterable

from utils.models import Users, db


def credit_bonus(user_ids: Iterable[int], amount: int) -> int:
    ids = list(dict.fromkeys(int(user_id) for user_id in user_ids))
    if amount <= 0 or not ids:
        return 0
    with db.atomic():
        return (Users.update(prize_balance=Users.prize_balance + amount)
                .where(Users.id.in_(ids))
                .execute())


def credit_bonus_to_user(user: Users, amount: int) -> bool:
    return credit_bonus([user.id], amount) == 1
