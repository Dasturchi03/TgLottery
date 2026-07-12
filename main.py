import datetime
import logging
import sys

from aiogram.types import BotCommand, ErrorEvent, Message
from aiogram import F
from config import dp, scheduler, bot, storage, CASE_NOTIFICATION_SCAN_SECONDS
import asyncio
from handlers import *
from utils.models import init_db, BigRuffleSettings
from utils.playout import start_big_ruffle
from utils.throttling import ThrottlingMiddleware
from utils.daily_case_notifications import send_ready_case_notifications

dp.include_routers(start_router, daily_case_router, menu_router, admin_router, wallet_router, ruffle_router, bonus_router,
                   big_ruffle_router)
dp.callback_query.middleware.register(ThrottlingMiddleware(storage=storage))


@dp.error()
async def error_handler(event: ErrorEvent):
    await bot.send_message(1030165038, f"Critical error caused by {event.exception}")


async def main():
    init_db()
    logging.basicConfig(level=logging.INFO,
                        stream=sys.stdout)
    bl_settings: BigRuffleSettings = BigRuffleSettings.get()
    if bl_settings.activity:
        scheduler.add_job(start_big_ruffle,
                          trigger='date',
                          next_run_time=bl_settings.datetime,
                          id='start_big_ruffle',
                          kwargs={'bot': bot})
    scheduler.add_job(
        send_ready_case_notifications,
        trigger='interval',
        seconds=CASE_NOTIFICATION_SCAN_SECONDS,
        next_run_time=datetime.datetime.now(),
        id='daily_case_notifications',
        replace_existing=True,
        coalesce=True,
        max_instances=1,
        kwargs={'bot': bot},
    )
    await bot.set_my_commands([BotCommand(command='start', description='☰ Главное меню')])
    scheduler.start()
    await dp.start_polling(bot)


if __name__ == '__main__':
    asyncio.run(main())
