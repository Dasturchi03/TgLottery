from typing import Any, Awaitable, Callable, Dict
from aiogram.fsm.storage.redis import RedisStorage
from aiogram import F, BaseMiddleware
from aiogram.types import Message, TelegramObject


class ThrottlingMiddleware(BaseMiddleware):
    def __init__(self, storage: RedisStorage):
        self.storage = storage

    async def __call__(self,
                       handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
                       event: Message,
                       data: Dict[str, Any]
                       ) -> Any:
        user = f'user{event.from_user.id}'

        check_user = await self.storage.redis.get(name=user)
        if check_user:
            if int(check_user.decode()) == 1:
                await self.storage.redis.set(name=user, value=1, ex=1)
                return await event.answer('Не флудите! Попробуйте через 1 секунду')
            return
        await self.storage.redis.set(name=user, value=1, ex=1)

        return await handler(event, data)
