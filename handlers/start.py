from aiogram import F, Router, Bot
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.filters.command import Command
from utils.keyboards import main_menu
from utils.models import Users
from aiogram.utils.deep_linking import decode_payload
from config import DISPLAY_CURRENCY

start_router = Router()


@start_router.callback_query(F.data == 'start')
@start_router.message(Command('start'))
async def start_handler(message: Message, state: FSMContext, bot: Bot, command: Command = None):
    await state.clear()
    user = Users.get_or_none(Users.user_id == message.from_user.id)
    if not user:
        user = Users.create(user_id=message.from_user.id,
                            username=message.from_user.username or '',
                            inactive=False)
        if command and command.args:
            reference = decode_payload(command.args).split('-')
            ref_user = Users.get_by_id(int(reference[0]))
            if ref_user.user_id == int(reference[1]):
                user.ref_user_id = ref_user.user_id
                user.save()
                try:
                    await bot.send_message(ref_user.user_id,
                                           f'✅ @{message.from_user.username} зарегистрировался по Вашей реферальной '
                                           f'ссылке\n🎁 Чтобы получить награду, необходимо чтобы он пополнил баланс')
                except Exception as e:
                    print(e)
    else:
        user.username = message.from_user.username or ''
        user.inactive = False
        user.save()
    from_user = message.from_user
    if isinstance(message, CallbackQuery):
        message = message.message
    await message.answer_photo(photo="AgACAgIAAxkBAAJqUGmkCUU8WjXxNUWpPGWYk4J9dlULAALPGWsbh1oQSY-01htykltqAQADAgADeQADOgQ",
                               caption=f'''👋 Привет, {from_user.first_name}! Перед запуском основные правила:

💥 Доступ в раунды приобретается за игровые очки <b>{DISPLAY_CURRENCY}</b>.

💰 Получить <b>{DISPLAY_CURRENCY}</b> можно играя в мини-игры, выполняя задания или пополнив баланс.

🎫 Принцип работы: Заполняются <b>слоты</b> -> запускается <b>рандом</b> -> определяется <b>победитель</b>.

🎲 <b>Событие</b> начинается автоматически, как только все слоты будут заняты.

🎟️ В каждом раунде только один победитель. <b>Награда</b> зачисляется на основной баланс, где её можно обменять по внутреннему курсу <b>1 к 1</b>.

📌 Один участник может занять несколько слотов в раунде. Больше слотов - выше шанс на главный приз.

🏆 За новостями следи в <a href="https://t.me/TG_Lottery_channel">официальном канале</a>.

👉 Если всё понятно – вперёд!''', parse_mode="HTML", reply_markup=main_menu(from_user.id),
                         disable_web_page_preview=True)
