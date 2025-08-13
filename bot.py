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
from notion_handler import create_notion_page, create_link_page
from transcriber import transcribe_voice
from url_processor import process_url

# Загрузка переменных окружения
load_dotenv()

# Настройка логирования
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

# Определяем состояния для ConversationHandler
CHOOSING, TYPING_REPLY, AWAITING_LINK = range(3)

# Кнопки меню
reply_keyboard = [
    ["Идея", "Задача", "Ссылка"],
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
    """Запоминает выбор пользователя и запрашивает соответствующий ввод."""
    user_choice = update.message.text
    context.user_data["choice"] = user_choice

    if user_choice == "Ссылка":
        await update.message.reply_text(
            "Пожалуйста, отправь мне ссылку, которую нужно сохранить.",
            reply_markup=ReplyKeyboardRemove(),
        )
        return AWAITING_LINK
    else:
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


async def received_link(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Обрабатывает полученную ссылку, анализирует и сохраняет в Notion."""
    url = update.message.text
    if not url.startswith("http"):
        await update.message.reply_text("Пожалуйста, отправьте корректную ссылку (должна начинаться с http или https).")
        return AWAITING_LINK # Остаемся в том же состоянии, ждем корректную ссылку

    await update.message.reply_text("Получил ссылку. Начинаю анализ, это может занять до минуты... 🧠")

    processed_data = await process_url(url)

    if not processed_data:
        await update.message.reply_text("Не удалось обработать ссылку. Пожалуйста, попробуйте другую.")
        context.user_data.clear()
        return ConversationHandler.END

    database_id = os.getenv("NOTION_DATABASE_ID_LINK")
    if not database_id:
        await update.message.reply_text("ID базы данных для ссылок не найден. Проверьте .env файл (NOTION_DATABASE_ID_LINK).")
        context.user_data.clear()
        return ConversationHandler.END

    result = create_link_page(
        database_id=database_id,
        title=processed_data.get('title', 'Без заголовка'),
        summary=processed_data.get('summary', ''),
        url=processed_data.get('url', url),
        tags=processed_data.get('tags', [])
    )

    if result:
        await update.message.reply_text(
            f"Ссылка успешно проанализирована и сохранена в Notion!\n\n"
            f"**Заголовок:** {processed_data.get('title')}"
        )
    else:
        await update.message.reply_text("Не удалось сохранить запись о ссылке в Notion. Проверьте логи для деталей.")

    context.user_data.clear()
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
                    filters.Regex("^(Идея|Задача|Ссылка)$"), choice
                )
            ],
            TYPING_REPLY: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, received_message),
                MessageHandler(filters.VOICE, received_voice),
            ],
            AWAITING_LINK: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, received_link)
            ],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )

    application.add_handler(conv_handler)

    # Запуск бота
    application.run_polling()


if __name__ == "__main__":
    main()
