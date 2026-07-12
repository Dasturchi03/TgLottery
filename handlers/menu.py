from aiogram import F, Router
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from utils.keyboards import profile_menu, momentum_ruffle, big_ruffle, admin_kb, bonus_menu, main_menu
from utils.models import Users, Settings, RufflesSettings, Tickets, BigRuffleSettings
from filters.admin import IsAdmin
from config import crypto
from utils.bonus_content import bonus_page_caption

menu_router = Router()


@menu_router.message(F.text.in_({'🙎🏻‍♂️ Профиль', '👤 Профиль'}))
async def profile_handler(message: Message, state: FSMContext):
    await state.clear()
    user = Users.get_or_none(Users.user_id == message.from_user.id)
    if user:
        tickets = [i for i in Tickets.select().where(Tickets.user_id == message.from_user.id)]
        await message.answer_photo(photo='AgACAgIAAxkBAAJqWGmkCWhVje9p6H6v3R7v2astPVJvAALLGWsbh1oQSTyvnrosziZ_AQADAgADeQADOgQ',
                                   caption=f'''👤 {message.from_user.full_name}
🎟 Билетов куплено: {len(tickets)} шт
🤑 Всего получено призовых денег: {user.prize_money} USDt
📈 Заработано на рефералах: {user.ref_money} 💎

💰 Ваш баланс: {user.balance} USDt
🎁 Бонус-баланс: {user.prize_balance} 💎''', reply_markup=profile_menu())
    else:
        await message.answer('⛔ Возникла ошибка, введите /start для того, чтобы '
                             'вернуться в главное меню')


@menu_router.message(F.text.in_({'🎟️ Моментальный розыгрыш', '🎟 Присоединиться'}))
async def momentum_ruffle_handle(message: Message, state: FSMContext):
    await state.clear()
    user = Users.get_or_none(Users.user_id == message.from_user.id)
    if user:
        ruffles = [ruffle for ruffle in RufflesSettings.select() if ruffle.active]
        await message.answer_photo(photo='AgACAgIAAxkBAAJqVmmkCWMevUml0HZk5rzIn1g8CYeIAALMGWsbh1oQSQ2fXIfmRxmPAQADAgADeQADOgQ',
                                   caption='''⭐️ Вы перешли в раздел моментальных розыгрышей\n
🤔 Выберите розыгрыш, в котором хотите участвовать.''',
                             reply_markup=momentum_ruffle(ruffles))
    else:
        await message.answer('⛔ Возникла ошибка, введите /start для того, чтобы '
                             'вернуться в главное меню')


@menu_router.message(F.text == '🎫 Мешок денег')
async def big_ruffle_handle(message: Message, state: FSMContext):
    await state.clear()
    bl_settings: BigRuffleSettings = BigRuffleSettings.get()
    if bl_settings.activity:
        user = Users.get_or_none(Users.user_id == message.from_user.id)
        if user:
            settings: BigRuffleSettings = BigRuffleSettings.get()
            await message.answer(f'''🎰 Вы перешли в раздел «Мешок денег»
    
🧐 Здесь выигрыш зависит от количества участников. Больше участников – больше выигрыш! 
🫵🏻 Ты можешь приобрести неограниченное количество билетов, чем больше, тем выше шанс на победу! 
💸 Победитель будет определён {settings.datetime} Удачи!''', reply_markup=big_ruffle())
        else:
            await message.answer('⛔ Возникла ошибка, введите /start для того, чтобы '
                                 'вернуться в главное меню')
    else:
        await message.answer('⛔ Этот розыгрыш на данный момент не доступен',
                             reply_markup=main_menu(message.from_user.id))


@menu_router.message(F.text.in_({'🎁 Бонусы', '💎 Бонусы'}))
async def bonuses_handler(message: Message, state: FSMContext):
    await state.clear()
    await message.answer_photo(photo='AgACAgIAAxkBAAJqUmmkCVO4yemYBj_89Z3bR4M6DIl3AALNGWsbh1oQSbsELUsoe8v6AQADAgADeQADOgQ',
                               caption=bonus_page_caption(),
                         reply_markup=bonus_menu(),
                         parse_mode='HTML')


@menu_router.message(F.text.in_({'🎫 Мои розыгрыши', '🎫 Мои слоты'}))
async def my_ruffles(message: Message):
    my_tickets = {}
    for i in Tickets.select().where(Tickets.user_id == message.from_user.id):
        my_tickets[i.ruffle_id] = my_tickets[i.ruffle_id] + 1 if i.ruffle_id in my_tickets else 1
    if my_tickets:
        text = '🎫 Мои розыгрыши\nКуплено/Доступно\n'
        for i in my_tickets:
            if i:
                ruffle = RufflesSettings.get_by_id(i)
                text += f'\n{ruffle.name} - {my_tickets[i]}/{ruffle.mfo - my_tickets[i]}'
            else:
                text += f'\n«Мешок денег» - {my_tickets[i]} шт.'
        await message.answer_photo(photo='AgACAgIAAxkBAAJqVGmkCV3FFr972p5khZOXHnTvkFaHAALOGWsbh1oQSezvkEvP-o32AQADAgADeQADOgQ',
                                   caption=text)
    else:
        await message.answer('❌ Вы сейчас не участвуете ни в одном розыгрыше')


@menu_router.callback_query(IsAdmin(), F.data == 'admin_panel')
@menu_router.message(IsAdmin(), F.text == '👑 Админ-панель')
async def admin_panel(message: Message | CallbackQuery, state: FSMContext):
    await state.clear()
    balance = await crypto.get_balance()
    users = [i for i in Users.select().where(Users.inactive == False)]
    inactive_users_count = Users.select().where(Users.inactive == True).count()
    
    # Получаем информацию по всем активным лотереям
    ruffles_info = []
    for ruffle in RufflesSettings.select().where(RufflesSettings.active == True):
        tickets = Tickets.select().where(Tickets.ruffle_id == ruffle.id)
        unique_users = len(set(ticket.user_id for ticket in tickets))
        tickets_count = len(tickets)
        remaining = ruffle.mfa - tickets_count
        ruffles_info.append(f"\n{ruffle.name} - {unique_users} чел | {tickets_count} шт | Осталось {remaining} билетов\n")
    
    text = f'''👑 Вы перешли в административную панель для управления ботом\n
✏️ Здесь Вы можете отредактировать цены и названия билетов, цену рефералов и прочее

💵 Баланс кошелька: {balance.available} USDt
👥 Активных пользователей: {len(users)}
🚫 Недоступных пользователей: {inactive_users_count}

📊 Статистика лотерей:{"".join(ruffles_info)}'''

    if isinstance(message, CallbackQuery):
        await message.message.edit_text(text, reply_markup=admin_kb())
    else:
        await message.answer(text, reply_markup=admin_kb())
