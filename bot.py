import os
import logging
from dotenv import load_dotenv
from telegram import ReplyKeyboardMarkup, ReplyKeyboardRemove, Update
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    ConversationHandler,
    MessageHandler,
    filters,
)
from notion_handler import create_notion_page
from transcriber import transcribe_voice

# Загрузка переменных окружения
load_dotenv()

# Настройка логирования
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

# Определяем состояния для ConversationHandler
CHOOSING, TYPING_REPLY = range(2)

# Кнопки меню
reply_keyboard = [
    ["Идея", "Задача"],
]
markup = ReplyKeyboardMarkup(reply_keyboard, one_time_keyboard=True)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Начинает диалог и предлагает выбрать категорию."""
    await update.message.reply_text(
        "Привет! Я твой бот для записи идей и задач в Notion. "
        "Выбери, что хочешь записать, или отправь /cancel для отмены.",
        reply_markup=markup,
    )
    return CHOOSING


async def choice(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Запоминает выбор пользователя и запрашивает текст."""
    user_choice = update.message.text
    context.user_data["choice"] = user_choice
    await update.message.reply_text(
        f"Отлично! Теперь отправь мне свою '{user_choice.lower()}'. "
        "Это может быть текст или голосовое сообщение.",
        reply_markup=ReplyKeyboardRemove(),
    )
    return TYPING_REPLY


async def received_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Обрабатывает полученное текстовое сообщение и сохраняет в Notion."""
    user_data = context.user_data
    text = update.message.text
    choice = user_data.get("choice")

    if not choice:
        await update.message.reply_text("Что-то пошло не так. Пожалуйста, начните сначала с /start.")
        return ConversationHandler.END

    # Определяем ID базы данных в зависимости от выбора
    database_id = os.getenv(f"NOTION_DATABASE_ID_{choice.upper()}")

    if not database_id:
        await update.message.reply_text(f"ID базы данных для '{choice}' не найден. Проверьте .env файл.")
        user_data.clear()
        return ConversationHandler.END

    # Создаем страницу в Notion
    result = create_notion_page(database_id, text)

    if result:
        await update.message.reply_text(f"Ваша '{choice.lower()}' успешно сохранена в Notion!")
    else:
        await update.message.reply_text("Не удалось сохранить запись в Notion. Проверьте логи для деталей.")

    user_data.clear()
    return ConversationHandler.END


async def received_voice(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Обрабатывает голосовое сообщение, транскрибирует и сохраняет в Notion."""
    user_data = context.user_data
    choice = user_data.get("choice")

    if not choice:
        await update.message.reply_text("Что-то пошло не так. Пожалуйста, начните сначала с /start.")
        return ConversationHandler.END

    await update.message.reply_text("Получил голосовое, начинаю расшифровку... 🎙️")

    voice_file_id = update.message.voice.file_id
    transcribed_text = await transcribe_voice(voice_file_id, context)

    # Проверяем, вернулась ли ошибка из транскрибатора
    if transcribed_text and transcribed_text.startswith("Ошибка:"):
        await update.message.reply_text(transcribed_text)
        user_data.clear()
        return ConversationHandler.END

    if not transcribed_text:
        await update.message.reply_text("Не удалось расшифровать голосовое сообщение.")
        user_data.clear()
        return ConversationHandler.END

    database_id = os.getenv(f"NOTION_DATABASE_ID_{choice.upper()}")
    if not database_id:
        await update.message.reply_text(f"ID базы данных для '{choice}' не найден. Проверьте .env файл.")
        user_data.clear()
        return ConversationHandler.END

    result = create_notion_page(database_id, transcribed_text)

    if result:
        await update.message.reply_text(
            f"Ваша '{choice.lower()}' успешно расшифрована и сохранена в Notion!\n\n"
            f"Текст: \"{transcribed_text}\""
        )
    else:
        await update.message.reply_text("Не удалось сохранить запись в Notion. Проверьте логи для деталей.")

    user_data.clear()
    return ConversationHandler.END


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Отменяет текущий диалог."""
    user_data = context.user_data
    await update.message.reply_text(
        "Действие отменено.", reply_markup=ReplyKeyboardRemove()
    )
    user_data.clear()
    return ConversationHandler.END


def main() -> None:
    """Запускает бота."""
    # Создание Application
    application = Application.builder().token(os.getenv("TELEGRAM_TOKEN")).build()

    # Создание ConversationHandler
    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            CHOOSING: [
                MessageHandler(
                    filters.Regex("^(Идея|Задача)$"), choice
                )
            ],
            TYPING_REPLY: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, received_message),
                MessageHandler(filters.VOICE, received_voice),
            ],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )

    application.add_handler(conv_handler)

    # Запуск бота
    application.run_polling()


if __name__ == "__main__":
    main()
