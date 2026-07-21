from aiogram import Bot
from aiogram.exceptions import TelegramForbiddenError
from utils.models import Users, Tickets, RufflesSettings, BigRuffleSettings
from random import choice
from config import DISPLAY_CURRENCY


def big_ruffle_real_amount(ticket_count: int, price: int) -> int:
    return max(0, int(ticket_count) * int(price))


def big_ruffle_visible_amount(ticket_count: int, price: int, fake_amount: int) -> int:
    return max(int(fake_amount), big_ruffle_real_amount(ticket_count, price))


def big_ruffle_win_amount(ticket_count: int, price: int, profit: int) -> float:
    amount = big_ruffle_real_amount(ticket_count, price)
    win_amount = amount - (amount * int(profit) / 100)
    return max(0, win_amount)


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
    bl_settings: BigRuffleSettings = BigRuffleSettings.get()
    if not tickets:
        bl_settings.activity = False
        bl_settings.save()
        return
    valid_tickets = []
    for ticket in tickets:
        ticket_user = Users.get_or_none(Users.user_id == ticket.user_id)
        if ticket_user:
            valid_tickets.append((ticket, ticket_user))
    if not valid_tickets:
        for ticket in tickets:
            ticket.delete_instance()
        bl_settings.activity = False
        bl_settings.save()
        return
    winner, user = choice(valid_tickets)
    win_amount = big_ruffle_win_amount(len(tickets), bl_settings.price, bl_settings.profit)
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
    bl_settings.activity = False
    bl_settings.save()
