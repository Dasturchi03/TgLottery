import asyncio
from datetime import datetime

from aiogram import F, Router
from aiogram.types import CallbackQuery, Message

from config import redis
from utils.daily_case import (
    CasePrize,
    case_remaining,
    draw_case_outcome,
    format_remaining,
    is_case_available,
    outcome_text,
    utc_now,
)
from utils.daily_case_operations import record_terminal_outcome
from utils.daily_case_storage import (
    acquire_daily_case_lock,
    add_extra_dice_attempts,
    release_daily_case_lock,
    remove_extra_dice_attempts,
)
from utils.keyboards import main_menu
from utils.models import Users


daily_case_router = Router()

ANIMATION_FRAMES = (
    '🎰 Генерируем призы... [ 🟥 🟥 🟥 🟥 🟥 ]',
    '🎰 Барабан вращается... [ 🟩 🟨 🟥 🟩 🟨 ]',
    '🎰 Лента замедляется... [ 🟩 🟩 🟩 🟨 🟨 ]',
)


async def _animate_case(status_message: Message) -> None:
    for index, frame in enumerate(ANIMATION_FRAMES):
        if index:
            await asyncio.sleep(0.45)
        await status_message.edit_text(frame)


def _cooldown_text(user: Users, now: datetime) -> str:
    remaining = case_remaining(user.daily_case_opened_at, now)
    return f'⏳ Вы уже открывали кейс. Возвращайтесь через {format_remaining(remaining)}.'


async def _open_daily_case(message: Message, user_id: int, callback: CallbackQuery | None = None):
    user = Users.get_or_none(Users.user_id == user_id)
    if not user:
        if callback:
            return await callback.answer('⛔ Пользователь не найден. Нажмите /start.', show_alert=True)
        return await message.answer('⛔ Пользователь не найден. Нажмите /start.')

    now = utc_now()
    if not is_case_available(user.daily_case_opened_at, now):
        if callback:
            return await callback.answer(_cooldown_text(user, now), show_alert=True)
        return await message.answer(
            _cooldown_text(user, now),
            reply_markup=main_menu(user.user_id),
        )

    lock_token = await acquire_daily_case_lock(redis, user.user_id, ttl=120)
    if not lock_token:
        if callback:
            return await callback.answer('🎰 Ваш кейс уже открывается.', show_alert=True)
        return await message.answer('🎰 Ваш кейс уже открывается. Дождитесь результата.')

    if callback:
        await callback.answer()
        try:
            await callback.message.edit_reply_markup(reply_markup=None)
        except Exception:
            pass

    status_message = await message.answer('🎁 Открываем ежедневный кейс...')
    try:
        user = Users.get_by_id(user.id)
        now = utc_now()
        if not is_case_available(user.daily_case_opened_at, now):
            await status_message.edit_text(_cooldown_text(user, now))
            return

        while True:
            await _animate_case(status_message)
            outcome = draw_case_outcome()
            if outcome.prize is CasePrize.REROLL:
                await asyncio.sleep(0.45)
                await status_message.edit_text(outcome_text(outcome))
                await asyncio.sleep(0.45)
                continue

            extra_attempts_added = False
            try:
                if outcome.prize is CasePrize.DICE_ATTEMPTS:
                    await add_extra_dice_attempts(redis, user.user_id, outcome.amount)
                    extra_attempts_added = True

                opened_at = utc_now()
                saved = record_terminal_outcome(user.user_id, outcome, opened_at)
                if not saved:
                    if extra_attempts_added:
                        await remove_extra_dice_attempts(redis, user.user_id, outcome.amount)
                    user = Users.get_by_id(user.id)
                    await status_message.edit_text(_cooldown_text(user, opened_at))
                    return
            except Exception:
                if extra_attempts_added:
                    await remove_extra_dice_attempts(redis, user.user_id, outcome.amount)
                raise

            await asyncio.sleep(0.45)
            await status_message.edit_text(outcome_text(outcome))
            await message.answer(
                '⏳ Следующий кейс будет доступен через 24:00.',
                reply_markup=main_menu(user.user_id),
            )
            return
    except Exception:
        await status_message.edit_text(
            '⚠️ Не удалось открыть кейс. Попробуйте ещё раз — попытка не списана.'
        )
        raise
    finally:
        await release_daily_case_lock(redis, user.user_id, lock_token)


@daily_case_router.message(
    F.text.startswith('🎁 Ежедневный кейс') | F.text.startswith('⏳ Кейс')
)
async def open_daily_case(message: Message):
    await _open_daily_case(message, message.from_user.id)


@daily_case_router.callback_query(F.data == 'daily_case_open')
async def open_daily_case_from_notification(callback: CallbackQuery):
    await _open_daily_case(callback.message, callback.from_user.id, callback)
