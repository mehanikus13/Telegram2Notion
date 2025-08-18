import os
import logging
from dotenv import load_dotenv

# Загружаем переменные окружения в первую очередь!
load_dotenv()

from telegram import ReplyKeyboardMarkup, ReplyKeyboardRemove, Update
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    ConversationHandler,
    MessageHandler,
    filters,
)
from notion_handler import (
    create_notion_page,
    create_link_page,
    get_property_options,
    create_task_page,
)
from transcriber import transcribe_voice
from url_processor import process_url

# Настройка логирования
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

# Определяем состояния для ConversationHandler
CHOOSING, TYPING_REPLY, AWAITING_LINK, AWAITING_TASK_TYPE, AWAITING_TASK_IMPORTANCE, AWAITING_TASK_SPEED, AWAITING_TASK_INTEREST = range(7)

# Кнопки меню
reply_keyboard = [
    ["Идея", "Задача", "Ссылка"],
]
markup = ReplyKeyboardMarkup(reply_keyboard, one_time_keyboard=True, resize_keyboard=True)

# Словарь для сопоставления выбора с суффиксом переменной в .env
CHOICE_TO_DB_SUFFIX = {
    "Идея": "IDEA",
    "Задача": "TASK",
}


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
    db_suffix = CHOICE_TO_DB_SUFFIX.get(choice)
    if not db_suffix:
        await update.message.reply_text("Произошла ошибка выбора. Пожалуйста, начните заново с /start.")
        user_data.clear()
        return ConversationHandler.END

    database_id = os.getenv(f"NOTION_DATABASE_ID_{db_suffix}")

    if not database_id:
        await update.message.reply_text(f"ID базы данных для '{choice}' не найден. Проверьте .env файл (NOTION_DATABASE_ID_{db_suffix}).")
        user_data.clear()
        return ConversationHandler.END

    # Если пользователь выбрал Задачу — запускаем сбор свойств перед сохранением
    if choice == "Задача":
        user_data["task_title"] = text
        user_data["task_db_id"] = database_id
        user_data["task_props"] = {}
        user_data["task_prop_order"] = [
            ("NOTION_TASK_TYPE_PROP", "ТИП", AWAITING_TASK_TYPE),
            ("NOTION_TASK_IMPORTANCE_PROP", "ВАЖНОСТЬ", AWAITING_TASK_IMPORTANCE),
            ("NOTION_TASK_SPEED_PROP", "СКОРОСТЬ", AWAITING_TASK_SPEED),
            ("NOTION_TASK_INTEREST_PROP", "ИНТЕРЕС", AWAITING_TASK_INTEREST),
        ]
        user_data["task_prop_index"] = 0
        return await prompt_next_task_property(update, context)

    # Идея — создаем страницу сразу, с учетом настраиваемого имени title-поля
    idea_title_prop = os.getenv("NOTION_IDEA_TITLE_PROP", "Name")
    result = create_notion_page(database_id, text, title_property_name=idea_title_prop)

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

    db_suffix = CHOICE_TO_DB_SUFFIX.get(choice)
    if not db_suffix:
        await update.message.reply_text("Произошла ошибка выбора. Пожалуйста, начните заново с /start.")
        user_data.clear()
        return ConversationHandler.END

    database_id = os.getenv(f"NOTION_DATABASE_ID_{db_suffix}")
    if not database_id:
        await update.message.reply_text(f"ID базы данных для '{choice}' не найден. Проверьте .env файл (NOTION_DATABASE_ID_{db_suffix}).")
        user_data.clear()
        return ConversationHandler.END

    if choice == "Задача":
        user_data["task_title"] = transcribed_text
        user_data["task_db_id"] = database_id
        user_data["task_props"] = {}
        user_data["task_prop_order"] = [
            ("NOTION_TASK_TYPE_PROP", "ТИП", AWAITING_TASK_TYPE),
            ("NOTION_TASK_IMPORTANCE_PROP", "ВАЖНОСТЬ", AWAITING_TASK_IMPORTANCE),
            ("NOTION_TASK_SPEED_PROP", "СКОРОСТЬ", AWAITING_TASK_SPEED),
            ("NOTION_TASK_INTEREST_PROP", "ИНТЕРЕС", AWAITING_TASK_INTEREST),
        ]
        user_data["task_prop_index"] = 0
        return await prompt_next_task_property(update, context)

    idea_title_prop = os.getenv("NOTION_IDEA_TITLE_PROP", "Name")
    result = create_notion_page(database_id, transcribed_text, title_property_name=idea_title_prop)

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


def _build_options_keyboard(options):
    rows = []
    row = []
    for opt in options:
        row.append(opt)
        if len(row) == 3:
            rows.append(row)
            row = []
    if row:
        rows.append(row)
    rows.append(["Пропустить"])  # возможность пропустить свойство
    return ReplyKeyboardMarkup(rows, one_time_keyboard=True, resize_keyboard=True)


async def prompt_next_task_property(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Показывает следующий шаг выбора свойства задачи или создает задачу, если все свойства пройдены."""
    user_data = context.user_data
    index = user_data.get("task_prop_index", 0)
    order = user_data.get("task_prop_order", [])

    while index < len(order):
        env_key, human_label, state = order[index]
        prop_name = os.getenv(env_key)
        if not prop_name:
            index += 1
            user_data["task_prop_index"] = index
            continue

        db_id = user_data.get("task_db_id")
        options, prop_type = get_property_options(db_id, prop_name)
        if not options:
            index += 1
            user_data["task_prop_index"] = index
            continue

        # Нашли свойство с опциями — спрашиваем пользователя
        user_data["current_prop_env_key"] = env_key
        user_data["current_prop_name"] = prop_name
        user_data["current_prop_options"] = options
        user_data["current_prop_label"] = human_label
        user_data["current_state"] = state

        keyboard = _build_options_keyboard(options)
        await update.message.reply_text(
            f"Выберите {human_label}:", reply_markup=keyboard
        )
        return state

    # Все свойства пройдены — создаем задачу
    title = user_data.get("task_title", "Без названия")
    db_id = user_data.get("task_db_id")
    props = user_data.get("task_props", {})
    task_title_prop = os.getenv("NOTION_TASK_TITLE_PROP", "Name")

    result = create_task_page(
        database_id=db_id,
        title=title,
        properties=props,
        title_property_name=task_title_prop,
    )

    if result:
        await update.message.reply_text(
            "Задача успешно сохранена в Notion!", reply_markup=ReplyKeyboardRemove()
        )
    else:
        await update.message.reply_text(
            "Не удалось сохранить задачу в Notion. Проверьте логи.",
            reply_markup=ReplyKeyboardRemove(),
        )

    user_data.clear()
    return ConversationHandler.END


async def handle_task_property_choice(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Обрабатывает выбор значения для текущего свойства задачи."""
    user_data = context.user_data
    text = update.message.text.strip()

    options = user_data.get("current_prop_options", [])
    prop_name = user_data.get("current_prop_name")
    human_label = user_data.get("current_prop_label")

    if text == "Пропустить":
        # просто идем дальше, не записывая значение
        user_data["task_prop_index"] = user_data.get("task_prop_index", 0) + 1
        return await prompt_next_task_property(update, context)

    if text not in options:
        keyboard = _build_options_keyboard(options)
        await update.message.reply_text(
            f"Пожалуйста, выберите одно из значений для {human_label}.",
            reply_markup=keyboard,
        )
        return user_data.get("current_state", CHOOSING)

    # Сохраняем выбор
    task_props = user_data.get("task_props", {})
    task_props[prop_name] = text
    user_data["task_props"] = task_props

    # Переходим к следующему свойству
    user_data["task_prop_index"] = user_data.get("task_prop_index", 0) + 1
    return await prompt_next_task_property(update, context)


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
            AWAITING_TASK_TYPE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_task_property_choice)
            ],
            AWAITING_TASK_IMPORTANCE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_task_property_choice)
            ],
            AWAITING_TASK_SPEED: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_task_property_choice)
            ],
            AWAITING_TASK_INTEREST: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_task_property_choice)
            ],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )

    application.add_handler(conv_handler)

    # Запуск бота
    application.run_polling()


if __name__ == "__main__":
    main()

