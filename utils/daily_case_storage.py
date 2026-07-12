from datetime import date, datetime, timedelta
from uuid import uuid4


def extra_dice_attempts_key(user_id: int, day: date | None = None) -> str:
    return f'game:extra_attempts:dice:{user_id}:{(day or date.today()).isoformat()}'


def daily_case_lock_key(user_id: int) -> str:
    return f'daily_case:lock:{user_id}'


def seconds_until_tomorrow(now: datetime | None = None) -> int:
    now = now or datetime.now()
    tomorrow = (now + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
    return max(60, int((tomorrow - now).total_seconds()))


async def get_extra_dice_attempts(redis, user_id: int) -> int:
    raw = await redis.get(extra_dice_attempts_key(user_id))
    if isinstance(raw, bytes):
        raw = raw.decode()
    return int(raw) if raw and str(raw).isdigit() else 0


async def add_extra_dice_attempts(redis, user_id: int, amount: int) -> int:
    if amount <= 0:
        return await get_extra_dice_attempts(redis, user_id)
    key = extra_dice_attempts_key(user_id)
    value = await redis.incrby(key, amount)
    await redis.expire(key, seconds_until_tomorrow())
    return int(value)


async def remove_extra_dice_attempts(redis, user_id: int, amount: int) -> None:
    key = extra_dice_attempts_key(user_id)
    value = await redis.decrby(key, amount)
    if int(value) <= 0:
        await redis.delete(key)


async def acquire_daily_case_lock(redis, user_id: int, ttl: int = 30) -> str | None:
    token = uuid4().hex
    acquired = await redis.set(daily_case_lock_key(user_id), token, ex=ttl, nx=True)
    return token if acquired else None


async def release_daily_case_lock(redis, user_id: int, token: str) -> None:
    script = '''
    if redis.call("get", KEYS[1]) == ARGV[1] then
        return redis.call("del", KEYS[1])
    end
    return 0
    '''
    await redis.eval(script, 1, daily_case_lock_key(user_id), token)
