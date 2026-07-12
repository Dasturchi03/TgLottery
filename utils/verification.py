from utils.models import Payments


def has_deposit(user_id: int) -> bool:
    return Payments.select().where(
        (Payments.user_id == user_id) & (Payments.finished == 1)
    ).exists()
