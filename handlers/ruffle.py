from aiogram import F, Router
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from utils.models import Users, Tickets, RufflesSettings
from utils.keyboards import next_kb
from utils.playout import start_ruffle
from utils.verification import has_deposit
from config import DISPLAY_CURRENCY


ruffle_router = Router()


@ruffle_router.callback_query(F.data.startswith('ruffle'))
async def ruffle_handle(callback: CallbackQuery):
    ruffle_id = int(callback.data.split()[1])
    ruffle = RufflesSettings.get_by_id(ruffle_id)
    user_tickets = (Tickets.select().where(Tickets.user_id == callback.from_user.id).
                    where(Tickets.ruffle_id == ruffle_id))
    await callback.message.edit_caption(caption=f'''📑 Условия лотереи
    
1️⃣ Выигрыш = x{ruffle.ratio} от стоимости одного слота ({ruffle.price * ruffle.ratio} {DISPLAY_CURRENCY})
2️⃣ Один участник может занять до {ruffle.mfo} слотов. Больше слотов – больше шансов.

⚠️ Вы уверены что хотите занять слот? Стоимость {ruffle.price} {DISPLAY_CURRENCY} спишется с Вашего баланса в профиле

🎟️ Сейчас у Вас слотов в данном событии: {len(user_tickets)} шт''',
                                     reply_markup=next_kb(f'buy_ruffle {ruffle_id}'))


@ruffle_router.callback_query(F.data.startswith('buy_ruffle'))
async def buy_ruffle_handle(callback: CallbackQuery):
    ruffle_id = int(callback.data.split()[1])
    ruffle: RufflesSettings = RufflesSettings.get_by_id(ruffle_id)

    if not ruffle.active:
        return await callback.message.edit_caption(caption='⛔ Этот розыгрыш на данный момент не доступен')

    tickets = Tickets.select().where(Tickets.ruffle_id == ruffle_id)
    user_tickets = (Tickets
                    .select()
                    .where((Tickets.user_id == callback.from_user.id) & (Tickets.ruffle_id == ruffle_id)))

    user: Users = Users.get_or_none(Users.user_id == callback.from_user.id)
    if not user:
        return await callback.message.edit_caption(caption='⛔ Ошибка профиля. Нажмите /start')

    # =========================
    # NEW: Premium rule checks
    # ruffle_type: 1 - premium, 0 - regular
    # =========================
    if ruffle.ruffle_type == 1:
        # 1) deposit check
        if not has_deposit(callback.from_user.id):
            return await callback.message.edit_caption(caption=
                'Этот розыгрыш доступен только для верифицированных пользователей. '
                'Для верификации необходимо пополнить баланс 1 раз.'
            )

        # 2) only main balance allowed
        if user.balance < ruffle.price:
            return await callback.message.edit_caption(caption=
                'Недостаточно средств. В этом розыгрыше нельзя участвовать за бонусы'
            )

    # =========================
    # Existing limits (same)
    # =========================
    if len(user_tickets) >= ruffle.mfo:
        return await callback.message.edit_caption(caption=
            '❌ Вы уже заняли максимально допустимое количество слотов для этого события'
        )

    if len(tickets) >= ruffle.mfa:
        return await callback.message.edit_caption(caption=
            '❌ Возникла ошибка при занятии слота, достигнут максимум для этого события, '
            'свяжитесь с администратором'
        )

    # =========================
    # Payment logic
    # =========================
    if ruffle.ruffle_type == 1:
        # Premium: already checked user.balance >= price
        user.balance -= ruffle.price
    else:
        # Regular: old behavior (main + bonus mixed)
        if user.balance + user.prize_balance < ruffle.price:
            return await callback.message.edit_caption(caption='❌ У Вас недостаточно средств для покупки данной лотереи')

        if user.balance >= ruffle.price:
            user.balance -= ruffle.price
        elif user.balance:
            difference = ruffle.price - user.balance
            user.prize_balance -= difference
            user.balance = 0
        else:
            user.prize_balance -= ruffle.price

    # Create ticket
    Tickets.create(user_id=callback.from_user.id, ruffle_id=ruffle_id)

    await callback.message.edit_caption(caption=
        f'✅ Вы заняли слот в событии {ruffle.name} за {ruffle.price} {DISPLAY_CURRENCY}. Розыгрыш начнется, когда все слоты '
        f'будут распроданы\n'
        f' - Слотов занято - {len(user_tickets) + 1} шт.\n'
        f' - Вам доступно - {ruffle.mfo - len(user_tickets) - 1} шт.'
    )

    # Cashback (as-is)
    if user.first_buy == 1:
        user.prize_balance += ruffle.price
        user.first_buy = 2
        await callback.message.answer('💶 Кэшбек начислен! Проверь баланс 🤙🏻')

    user.can_withdraw_money = True
    user.save()

    # Start when full
    if (len(tickets) + 1) >= ruffle.mfa:
        await start_ruffle(callback.bot, ruffle)
