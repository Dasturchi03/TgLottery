import asyncio
from datetime import datetime, date, timedelta
from aiogram import F, Router
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from utils.models import Users, Payments, Settings
from aiogram.utils.deep_linking import create_start_link
from utils.keyboards import channel_kb, dice_kb, bonus_menu, pnmvpn_trial_kb
from utils.verification import has_deposit
from config import redis, PNMVPN_BOT_USERNAME
from utils.bonus_content import bonus_page_caption, referral_caption


bonus_router = Router()


@bonus_router.callback_query(F.data == 'invite_friend')
async def invite_friend(callback: CallbackQuery):
    user = Users.get_or_none(Users.user_id == callback.from_user.id)
    if user:
        settings = Settings.get()
        link = await create_start_link(callback.bot, str(f'{user.id}-{user.user_id}'), encode=True)
        await callback.message.edit_caption(caption=referral_caption(link, settings))
    else:
        await callback.message.edit_caption(caption='⛔ Возникла ошибка, введите /start для того, чтобы '
                                         'вернуться в главное меню')


@bonus_router.callback_query(F.data == 'follow_channel')
async def follow_channel(callback: CallbackQuery):
    user = Users.get_or_none(Users.user_id == callback.from_user.id)
    if not user.channel_payed:
        settings = Settings.get()
        await callback.message.edit_caption(
            caption=f'🌐 Подпишись на канал, нажав на «Подписаться», чтобы получить бонус в размере '
            f'{settings.prize_follow} 💎\n'
            '✅ Чтобы получить бонус после того, как подписались - нажмите на кнопку «Проверить»',
            reply_markup=channel_kb())
    else:
        await callback.answer('✅ Вы уже получали бонус за подписку на канал', show_alert=True)


@bonus_router.callback_query(F.data == 'check follow_channel')
async def check_follow_channel(callback: CallbackQuery):
    user = Users.get_or_none(Users.user_id == callback.from_user.id)
    if not user.channel_payed:
        user_channel_status = await callback.bot.get_chat_member(chat_id=-1001967035849,
                                                                 user_id=callback.from_user.id)
        if user_channel_status.status != 'left':
            settings = Settings.get()
            await callback.message.edit_caption(caption=f'✅ Вы успешно получили бонус за подписку на канал в размере '
                                             f'{settings.prize_follow} 💎')
            user.prize_balance += settings.prize_follow
            user.channel_payed = True
            user.save()
        else:
            await callback.answer('❌ Вы не подписаны на канал')
    else:
        await callback.answer('✅ Вы уже получали бонус за подписку на канал', show_alert=True)


# =========================
# NEW: 🎲 Dice game
# =========================

NOT_VERIFIED_TEXT = (
    "Эти мини-игры доступны только верифицированным пользователям. "
    "Для верификации необходимо пополнить баланс 1 раз"
)

def _seconds_until_tomorrow() -> int:
    now = datetime.now()
    tomorrow = (now + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
    return max(60, int((tomorrow - now).total_seconds()))


async def _attempts_used_today(game: str, user_id: int) -> tuple[str, int]:
    today = date.today().isoformat()
    key = f"game:attempts:{game}:{user_id}:{today}"
    raw = await redis.get(key)
    used = int(raw) if raw and raw.isdigit() else 0
    return key, used


async def _play_game(
    callback: CallbackQuery,
    *,
    game: str,
    emoji: str,
    call_data_throw: str,
    daily_attempts: int,
    reward: int,
    requires_verified: bool,
    win_predicate,
):
    user = Users.get_or_none(Users.user_id == callback.from_user.id)
    if not user:
        return await callback.answer("⛔ Ошибка. Нажмите /start", show_alert=True)

    if requires_verified and not has_deposit(user_id=callback.from_user.id):
        return await callback.answer(NOT_VERIFIED_TEXT, show_alert=True)

    if daily_attempts <= 0:
        return await callback.answer("🎮 Игра временно недоступна (K=0).", show_alert=True)

    key, used = await _attempts_used_today(game, callback.from_user.id)
    if used >= daily_attempts:
        return await callback.answer("❌ Попытки на сегодня закончились. Приходите завтра.", show_alert=True)

    used_after = await redis.incr(key)
    if used_after == 1:
        await redis.expire(key, _seconds_until_tomorrow())

    remaining = max(0, daily_attempts - int(used_after))
    await callback.answer()

    msg = await callback.message.answer_dice(emoji=emoji.split()[0])
    await asyncio.sleep(4.5)

    value = msg.dice.value if msg.dice else None
    if value is None:
        return await callback.message.answer("⚠️ Не удалось получить результат. Попробуйте ещё раз.")

    if win_predicate(value):
        user.prize_balance += reward
        user.save()
        await callback.message.edit_caption(
            caption=f"✅ Вам начислен бонус {reward} 💎.\nОсталось попыток: {remaining}",
            reply_markup=dice_kb(emoji, call_data_throw),
        )
    else:
        await callback.message.edit_caption(
            caption=f"❌ Попробуйте ещё.\nОсталось попыток: {remaining}",
            reply_markup=dice_kb(emoji, call_data_throw),
        )


async def _play_two_dice_double_game(
    callback: CallbackQuery,
    *,
    game: str,
    emoji: str,
    call_data_throw: str,
    daily_attempts: int,
    reward: int,
    requires_verified: bool,
):
    user = Users.get_or_none(Users.user_id == callback.from_user.id)
    if not user:
        return await callback.answer("⛔ Ошибка. Нажмите /start", show_alert=True)

    if requires_verified and not has_deposit(user_id=callback.from_user.id):
        return await callback.answer(NOT_VERIFIED_TEXT, show_alert=True)

    if daily_attempts <= 0:
        return await callback.answer("🎲 Игра временно недоступна (K=0).", show_alert=True)

    key, used = await _attempts_used_today(game, callback.from_user.id)
    if used >= daily_attempts:
        return await callback.answer("❌ Попытки на сегодня закончились. Приходите завтра.", show_alert=True)

    used_after = await redis.incr(key)
    if used_after == 1:
        await redis.expire(key, _seconds_until_tomorrow())

    remaining = max(0, daily_attempts - int(used_after))
    await callback.answer()

    msg1 = await callback.message.answer_dice(emoji=emoji.split()[0])
    msg2 = await callback.message.answer_dice(emoji=emoji.split()[0])

    await asyncio.sleep(4.5)

    v1 = msg1.dice.value if msg1.dice else None
    v2 = msg2.dice.value if msg2.dice else None
    if v1 is None or v2 is None:
        return await callback.message.answer("⚠️ Не удалось получить результат. Попробуйте ещё раз.")

    if v1 == v2:
        user.prize_balance += reward
        user.save()
        await callback.message.edit_caption(
            caption=f"✅ Вам начислен бонус {reward} 💎.\nОсталось попыток: {remaining}",
            reply_markup=dice_kb(emoji, call_data_throw),
        )
    else:
        await callback.message.edit_caption(
            caption=f"❌ Попробуй еще.\nОсталось попыток: {remaining}",
            reply_markup=dice_kb(emoji, call_data_throw),
        )


@bonus_router.callback_query(F.data == 'bonuses_back')
async def bonuses_back(callback: CallbackQuery):
    await callback.message.edit_caption(
        caption=bonus_page_caption(),
        reply_markup=bonus_menu(),
        parse_mode='HTML',
    )


@bonus_router.callback_query(F.data == 'dice_game')
async def dice_game_rules(callback: CallbackQuery):
    settings = Settings.get()
    k = int(getattr(settings, "dice_daily_attempts", 0) or 0)
    n = int(getattr(settings, "dice_double_reward", 0) or 0)

    await callback.message.edit_caption(
        caption=f'🎲 Игра в кости\n\n'
        f'При выпадении дубля Вы получите {n} 💎! Всего {k} попыток в день. Удачи!',
        reply_markup=dice_kb(emoji="🎲 Подбросить", call_data='dice_throw')
    )


@bonus_router.callback_query(F.data == 'dice_throw')
async def dice_throw(callback: CallbackQuery):
    settings = Settings.get()
    k = int(getattr(settings, "dice_daily_attempts", 0) or 0)
    n = int(getattr(settings, "dice_double_reward", 0) or 0)

    await _play_two_dice_double_game(
        callback,
        game="dice",
        emoji="🎲 Подбросить",
        call_data_throw="dice_throw",
        daily_attempts=k,
        reward=n,
        requires_verified=False
    )


@bonus_router.callback_query(F.data == "casino_game")
async def casino_game_rules(callback: CallbackQuery):
    s = Settings.get()
    k = int(getattr(s, "casino_daily_attempts", 0) or 0)
    n = float(getattr(s, "casino_reward", 0) or 0)

    await callback.message.edit_caption(
        caption="🎰 777\n\n"
        f"Бонус {n} 💎 — только если выпали 3 одинаковых символа.\n"
        f"Всего {k} попыток в день. Удачи!",
        reply_markup=dice_kb(emoji='🎰 Играть', call_data='casino_throw')
    )

@bonus_router.callback_query(F.data == "casino_throw")
async def casino_throw(callback: CallbackQuery):
    s = Settings.get()
    k = int(getattr(s, "casino_daily_attempts", 0) or 0)
    n = float(getattr(s, "casino_reward", 0) or 0)

    await _play_game(
        callback,
        game="casino",
        emoji="🎰 Играть",
        call_data_throw='casino_throw',
        daily_attempts=k,
        reward=n,
        requires_verified=True,
        win_predicate=lambda v: v in (1, 22, 43, 64)
    )


@bonus_router.callback_query(F.data == "bowling_game")
async def bowling_game_rules(callback: CallbackQuery):
    s = Settings.get()
    k = int(getattr(s, "bowling_daily_attempts", 0) or 0)
    n = float(getattr(s, "bowling_reward", 0) or 0)

    await callback.message.edit_caption(
        caption="🎳 Боулинг\n\n"
        f"Бонус {n} 💎 — только если выбили страйк.\n"
        f"Всего {k} попыток в день. Удачи!",
        reply_markup=dice_kb(emoji='🎳 Играть', call_data='bowling_throw')
    )

@bonus_router.callback_query(F.data == "bowling_throw")
async def bowling_throw(callback: CallbackQuery):
    s = Settings.get()
    k = int(getattr(s, "bowling_daily_attempts", 0) or 0)
    n = float(getattr(s, "bowling_reward", 0) or 0)

    await _play_game(
        callback,
        game="bowling",
        emoji="🎳 Играть",
        call_data_throw='bowling_throw',
        daily_attempts=k,
        reward=n,
        requires_verified=True,
        win_predicate=lambda v: v == 6
    )


@bonus_router.callback_query(F.data == "darts_game")
async def darts_game_rules(callback: CallbackQuery):
    s = Settings.get()
    k = int(getattr(s, "darts_daily_attempts", 0) or 0)
    n = float(getattr(s, "darts_reward", 0) or 0)

    await callback.message.edit_caption(
        caption="🎯 Дартс\n\n"
        f"Бонус {n} 💎 — только если попали в «яблочко».\n"
        f"Всего {k} попыток в день. Удачи!",
        reply_markup=dice_kb(emoji='🎯 Играть', call_data='darts_throw')
    )

@bonus_router.callback_query(F.data == "darts_throw")
async def darts_throw(callback: CallbackQuery):
    s = Settings.get()
    k = int(getattr(s, "darts_daily_attempts", 0) or 0)
    n = float(getattr(s, "darts_reward", 0) or 0)

    await _play_game(
        callback,
        game="darts",
        emoji="🎯 Играть",
        call_data_throw='darts_throw',
        daily_attempts=k,
        reward=n,
        requires_verified=True,
        win_predicate=lambda v: v == 6
    )


@bonus_router.callback_query(F.data == 'pnmvpn_trial')
async def pnmvpn_trial_bonus(callback: CallbackQuery):
    settings = Settings.get()
    await callback.message.edit_caption(
        caption=f'💎 {settings.pnmvpn_trial_reward} за ₽1\n\n'
        f'Оформи пробную подписку за 1 руб. и получи бонус {settings.pnmvpn_trial_reward} 💎.\n\n'
        'После успешного оформления бонус будет начислен автоматически ✅',
        reply_markup=pnmvpn_trial_kb(PNMVPN_BOT_USERNAME)
    )
