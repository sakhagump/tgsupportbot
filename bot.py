import asyncio
import logging
from aiogram import Bot, Dispatcher, F, Router
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode, ChatType
from aiogram.filters import CommandStart
from aiogram.types import Message
from aiogram.utils.keyboard import InlineKeyboardBuilder

# ==== НАСТРОЙКИ ====
BOT_TOKEN = "8746931726:AAGQ-rjPsI3kh9r5ts9he4P-fY2ZVHayxKQ"
SUPPORT_CHAT_ID = -1003947121018

logging.basicConfig(level=logging.INFO)

bot = Bot(BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher()
router = Router()
dp.include_router(router)

# user_id -> thread_id (в каком топике ведётся диалог с пользователем)
user_threads: dict[int, int] = {}
# thread_id -> user_id (обратный маппинг для ответов оператора)
thread_users: dict[int, int] = {}


def topic_title(msg: Message) -> str:
    """Название топика: имя + id пользователя."""
    name = msg.from_user.full_name or "user"
    return f"{name} | id{msg.from_user.id}"[:128]


def user_link(user) -> str:
    name = user.full_name
    if user.username:
        return f'<a href="https://t.me/{user.username}">{name}</a>'
    return f'<a href="tg://user?id={user.id}">{name}</a>'


@router.message(CommandStart(), F.chat.type == ChatType.PRIVATE)
async def cmd_start(msg: Message):
    await msg.answer(
        "👋 Здравствуйте! Опишите ваш вопрос, и оператор ответит вам в ближайшее время.\n"
        "Просто отправьте сообщение — оно попадёт в поддержку."
    )


# ==== Сообщения от пользователя в ЛС ====
@router.message(F.chat.type == ChatType.PRIVATE)
async def from_user(msg: Message):
    user_id = msg.from_user.id

    # Если топика ещё нет — создаём
    thread_id = user_threads.get(user_id)
    if thread_id is None:
        try:
            topic = await bot.create_forum_topic(
                chat_id=SUPPORT_CHAT_ID,
                name=topic_title(msg),
            )
        except Exception as e:
            logging.exception("Не удалось создать топик: %s", e)
            await msg.answer("⚠️ Не удалось создать обращение. Попробуйте позже.")
            return

        thread_id = topic.message_thread_id
        user_threads[user_id] = thread_id
        thread_users[thread_id] = user_id

        # Приветственное сообщение в топике
        kb = InlineKeyboardBuilder()
        kb.button(text="✅ Закрыть тикет", callback_data=f"close:{user_id}")
        await bot.send_message(
            chat_id=SUPPORT_CHAT_ID,
            message_thread_id=thread_id,
            text=(
                f"🆕 <b>Новое обращение</b>\n"
                f"Пользователь: {user_link(msg.from_user)}\n"
                f"ID: <code>{user_id}</code>\n"
                f"Username: @{msg.from_user.username or '—'}"
            ),
            reply_markup=kb.as_markup(),
        )

    # Пересылаем контент пользователя в топик
    await _forward_to_topic(msg, thread_id)
    await msg.answer("✅ Сообщение отправлено в поддержку.")


async def _forward_to_topic(msg: Message, thread_id: int):
    """Копируем сообщение пользователя в топик поддержки (сохраняя контент)."""
    try:
        await bot.copy_message(
            chat_id=SUPPORT_CHAT_ID,
            from_chat_id=msg.chat.id,
            message_id=msg.message_id,
            message_thread_id=thread_id,
        )
    except Exception as e:
        logging.exception("Ошибка копирования: %s", e)


# ==== Сообщения операторов в топике ====
@router.message(F.chat.id == SUPPORT_CHAT_ID, F.message_thread_id)
async def from_operator(msg: Message):
    thread_id = msg.message_thread_id
    user_id = thread_users.get(thread_id)
    if not user_id:
        return  # не наш топик

    # Игнорируем команды-закрытия и служебное
    try:
        await bot.copy_message(
            chat_id=user_id,
            from_chat_id=SUPPORT_CHAT_ID,
            message_id=msg.message_id,
        )
    except Exception as e:
        await msg.reply(f"⚠️ Не удалось доставить пользователю: {e}")


# ==== Закрытие тикета ====
@router.callback_query(F.data.startswith("close:"))
async def close_ticket(cb):
    user_id = int(cb.data.split(":")[1])
    thread_id = user_threads.pop(user_id, None)
    if thread_id:
        thread_users.pop(thread_id, None)

    await cb.message.edit_reply_markup(reply_markup=None)
    await cb.answer("Тикет закрыт")
    await bot.send_message(
        chat_id=SUPPORT_CHAT_ID,
        message_thread_id=thread_id,
        text=f"🔒 Тикет закрыт оператором {cb.from_user.full_name}.",
    )
    try:
        await bot.send_message(
            chat_id=user_id,
            text="🔒 Ваше обращение закрыто. Если нужна помощь снова — напишите /start.",
        )
    except Exception:
        pass


async def main():
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
