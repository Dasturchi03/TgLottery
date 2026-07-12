import asyncio
from aiogram import Bot, Dispatcher, F
from aiogram.types import Message
from aiogram.enums import ParseMode


BOT_TOKEN = ''


bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()


@dp.message(F.photo)
async def handle_photo(message: Message):
    largest_photo = message.photo[-1]
    file_id = largest_photo.file_id
    file_unique_id = largest_photo.file_unique_id

    await message.answer(
        f"<b>file_id:</b>\n<code>{file_id}</code>\n\n"
        f"<b>file_unique_id:</b>\n<code>{file_unique_id}</code>",
        parse_mode='HTML'
    )


@dp.message()
async def fallback(message: Message):
    await message.answer("Send photo 📷")


async def main():
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())