from aiogram import Bot
from aiogram.exceptions import TelegramForbiddenError
from utils.models import Users, Tickets, RufflesSettings, BigRuffleSettings
from random import choice
from config import DISPLAY_CURRENCY


async def start_ruffle(bot: Bot, ruffle: RufflesSettings):
    tickets = [i for i in Tickets.select().where(Tickets.ruffle_id == ruffle.id)]
    winner = choice(tickets)
    user = Users.get_or_none(Users.user_id == winner.user_id)
    while not user:
        winner = choice(tickets)
        user = Users.get_or_none(Users.user_id == winner.user_id)
    user.balance += (ruffle.price * ruffle.ratio)
    user.save()
    try:
        await bot.send_message(user.user_id,
                               f'🎉 Вы выиграли {ruffle.price * ruffle.ratio} {DISPLAY_CURRENCY} в событии {ruffle.name}')
    except Exception as e:
        print(e)
    notified = [user.user_id]
    winner_username = await bot.get_chat(winner.user_id)
    for i in tickets:
        print(i.user_id)
        if i.user_id not in notified:
            try:
                await bot.send_message(i.user_id, f'🎲 Пользователь @{winner_username.username} выиграл '
                                                  f'{ruffle.price * ruffle.ratio} {DISPLAY_CURRENCY} в событии {ruffle.name} - '
                                                  f'Вы ничего не выиграли')
            except Exception as e:
                print(e)
            notified.append(i.user_id)
        i.delete_instance()
    print(f'=========\n{notified}')


async def start_big_ruffle(bot: Bot):
    print('yes')
    tickets = [i for i in Tickets.select().where(Tickets.ruffle_id == 0)]
    winner = choice(tickets)
    user = Users.get_or_none(Users.user_id == winner.user_id)
    while not user:
        winner = choice(tickets)
        user = Users.get_or_none(Users.user_id == winner.user_id)
    bl_settings: BigRuffleSettings = BigRuffleSettings.get()
    amount = (len(tickets) * bl_settings.price) - 10
    win_amount = amount - (amount * bl_settings.profit / 100)
    user.balance += win_amount
    user.save()
    try:
        await bot.send_message(user.user_id, f'🎉 Вы выиграли {win_amount} {DISPLAY_CURRENCY} в событии «Мешок денег»')
    except Exception as e:
        print(e)
    notified = [user.user_id]
    winner_username = await bot.get_chat(winner.user_id)
    for i in tickets:
        print(i.user_id)
        if i.user_id not in notified:
            try:
                await bot.send_message(i.user_id, f'🎲 Пользователь @{winner_username.username} выиграл '
                                                  f'{win_amount} {DISPLAY_CURRENCY} в событии «Мешок денег» - '
                                                  f'Вы ничего не выиграли')
            except Exception as e:
                print(e)
            notified.append(i.user_id)
        i.delete_instance()
    print(f'=========\n{notified}')
    bl_settings.active = False
    bl_settings.save()
