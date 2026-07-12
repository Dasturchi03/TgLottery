from aiogram.filters import BaseFilter
from aiogram.types import Message
from config import ADMINS


class IsAdmin(BaseFilter):  # [1]
    async def __call__(self, message: Message) -> bool:  # [3]
        return message.from_user.id in ADMINS
