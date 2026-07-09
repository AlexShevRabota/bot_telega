import asyncio
import logging

from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command

from bin.config import API_KEY

bot = Bot(token=API_KEY)
dp = Dispatcher()

@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    user_name = message.from_user.first_name
    await message.answer(f"Привет, {user_name}! Я бот на Alex!")

@dp.message(Command("help"))
async def cmd_help(message: types.Message):
    await message.answer("Чем помочь?")


@dp.message()
async def echo(message: types.Message):
    await message.answer(f"Эхо: {message.text}")

async def main():
    print("Бот запускается...")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())