import os
import logging
from dotenv import load_dotenv

# Загружаем переменные окружения в первую очередь!
load_dotenv()

from telegram import ReplyKeyboardMarkup, ReplyKeyboardRemove, Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    ConversationHandler,
    MessageHandler,
    CallbackQueryHandler,
    filters,
)
from notion_handler import (
    create_notion_page,
    create_link_page,

)
from transcriber import transcribe_voice
from url_processor import process_url

# Настройка логирования
logging.basicConfig(format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO)
logger = logging.getLogger(__name__)



# === Константы состояний ===
# ConversationHandler использует числовые идентификаторы для обозначения этапов диалога.
CHOOSING_ACTION, AWAITING_INPUT, AWAITING_LINK, SELECTING_TASK_PROPERTY = range(4)

# === Клавиатуры ===
main_keyboard = [["Идея", "Задача", "Ссылка"]]
main_markup = ReplyKeyboardMarkup(main_keyboard, one_time_keyboard=True, resize_keyboard=True)

# === Обработчики ===

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Начинает диалог и предлагает выбрать категорию."""
    await update.message.reply_text(
        "Привет! Я твой бот для Notion. Выбери, что хочешь записать, или отправь /cancel для отмены.",
        reply_markup=main_markup,
    )
    return CHOOSING_ACTION

async def choice_action(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Определяет следующее действие на основе выбора пользователя."""
    user_choice = update.message.text
    context.user_data['choice'] = user_choice

    if user_choice == "Ссылка":
        await update.message.reply_text("Пожалуйста, отправь ссылку.", reply_markup=ReplyKeyboardRemove())
        return AWAITING_LINK
    else: # Идея или Задача
        await update.message.reply_text(f"Отлично! Теперь отправь мне свою '{user_choice.lower()}'.", reply_markup=ReplyKeyboardRemove())
        return AWAITING_INPUT

async def received_input(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Обрабатывает текстовое или голосовое сообщение для Идеи или Задачи."""
    choice = context.user_data.get('choice')
    text = ""

    if update.message.voice:
        await update.message.reply_text("Получил голосовое, расшифровываю... 🎙️")
        text = await transcribe_voice(update.message.voice.file_id, context)
        if not text or text.startswith("Ошибка:"):
            await update.message.reply_text(text or "Не удалось расшифровать.")
            return ConversationHandler.END
    else:
        text = update.message.text

    if choice == "Идея":
        return await save_idea(update, context, text)
    elif choice == "Задача":
        return await start_task_process(update, context, text)

async def save_idea(update: Update, context: ContextTypes.DEFAULT_TYPE, text: str) -> int:
    """Сохраняет идею в Notion."""
    db_id = os.getenv("NOTION_DATABASE_ID_IDEA")
    title_prop = os.getenv("NOTION_IDEA_PROPERTY_TITLE", "Name")

    if not db_id:
        await update.message.reply_text("ID базы данных для 'Идей' не найден в .env.")
        return ConversationHandler.END


    if result:
        await update.message.reply_text("Идея успешно сохранена в Notion!")
    else:
        await update.message.reply_text("Не удалось сохранить идею. Проверьте логи.")
    return ConversationHandler.END

async def start_task_process(update: Update, context: ContextTypes.DEFAULT_TYPE, text: str) -> int:
    """Начинает многошаговый процесс создания задачи."""
    db_id = os.getenv("NOTION_DATABASE_ID_TASK")
    title_prop = os.getenv("NOTION_TASK_PROPERTY_TITLE", "Name")

    if not db_id:
        await update.message.reply_text("ID базы данных для 'Задач' не найден в .env.")
        return ConversationHandler.END

    # 1. Создаем страницу с названием
    page = await create_notion_page(db_id, title_prop, text)
    if not page:
        await update.message.reply_text("Не удалось создать задачу в Notion. Проверьте логи.")
        return ConversationHandler.END

    await update.message.reply_text(f"Задача '{text}' создана. Теперь давайте уточним детали.")

    # 2. Получаем список интерактивных полей
    interactive_props_str = os.getenv("NOTION_TASK_INTERACTIVE_PROPERTIES", "")
    properties_to_ask = [p.strip() for p in interactive_props_str.split(',') if p.strip()]

    if not properties_to_ask:
        await update.message.reply_text("Настройка интерактивных полей не найдена. Задача сохранена без деталей.")
        return ConversationHandler.END

    # 3. Сохраняем контекст для диалога
    context.user_data['task_page_id'] = page['id']
    context.user_data['properties_to_ask'] = properties_to_ask
    context.user_data['current_property_index'] = 0
    context.user_data['db_properties'] = await get_database_properties(db_id)

    return await ask_next_task_property(update, context)

async def ask_next_task_property(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Задает вопрос о следующем свойстве задачи."""
    user_data = context.user_data
    idx = user_data['current_property_index']
    properties_to_ask = user_data['properties_to_ask']

    if idx >= len(properties_to_ask):
        await context.bot.send_message(chat_id=update.effective_chat.id, text="Отлично! Все детали задачи заполнены.")
        return ConversationHandler.END



    if not prop_info or not prop_info.get('options'):
        await context.bot.send_message(chat_id=update.effective_chat.id, text=f"Не удалось найти свойство '{prop_name}' или его опции в Notion. Пропускаю...")
        user_data['current_property_index'] += 1
        return await ask_next_task_property(update, context)

    keyboard = [
        [InlineKeyboardButton(option, callback_data=f"taskprop_{prop_name}_{option}")]
        for option in prop_info['options']
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    # Если это не первый вопрос, сначала редактируем предыдущее сообщение
    if update.callback_query:
        await update.callback_query.edit_message_text(text=f"Выберите '{prop_name}':", reply_markup=reply_markup)
    else:
        await context.bot.send_message(chat_id=update.effective_chat.id, text=f"Выберите '{prop_name}':", reply_markup=reply_markup)

    return SELECTING_TASK_PROPERTY

async def received_task_property(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Обрабатывает выбор свойства задачи."""
    query = update.callback_query
    await query.answer()

    _, prop_name, value = query.data.split('_', 2)
    page_id = context.user_data['task_page_id']
    prop_info = context.user_data.get('db_properties', {}).get(prop_name)

    # Формируем payload для обновления
    prop_type = prop_info.get('type')
    update_payload = {}
    if prop_type == 'select':
        update_payload[prop_name] = {'select': {'name': value}}
    elif prop_type == 'multi_select':
        # Для простоты пока добавляем как единственный, для сложной логики нужно будет хранить текущие
        update_payload[prop_name] = {'multi_select': [{'name': value}]}

    # Обновляем страницу в Notion
    await update_page_properties(page_id, update_payload)
    await query.edit_message_text(text=f"Выбрано: {prop_name} -> {value}")

    context.user_data['current_property_index'] += 1
    return await ask_next_task_property(update, context)

async def received_link(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Обрабатывает полученную ссылку, анализирует и сохраняет в Notion."""
    url = update.message.text
    if not url.startswith("http"):
        await update.message.reply_text("Пожалуйста, отправьте корректную ссылку.")
        return AWAITING_LINK

    await update.message.reply_text("Анализирую ссылку... 🧠")
    processed_data = await process_url(url)
    if not processed_data:
        await update.message.reply_text("Не удалось обработать ссылку.")
        return ConversationHandler.END

    db_id = os.getenv("NOTION_DATABASE_ID_LINK")
    title_prop = os.getenv("NOTION_LINK_PROPERTY_TITLE", "Name")
    url_prop = os.getenv("NOTION_LINK_PROPERTY_URL", "URL")
    tags_prop = os.getenv("NOTION_LINK_PROPERTY_TAGS", "Tags")

    if not db_id:
        await update.message.reply_text("ID базы данных для 'Ссылок' не найден в .env.")
        return ConversationHandler.END

    result = await create_link_page(db_id, title_prop, url_prop, tags_prop, processed_data)
    if result:
        await update.message.reply_text(f"Ссылка успешно сохранена в Notion!\n\n**Заголовок:** {processed_data.get('title')}")
    else:
        await update.message.reply_text("Не удалось сохранить ссылку. Проверьте логи.")
    return ConversationHandler.END

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Отменяет любой диалог."""
    await update.message.reply_text("Действие отменено.", reply_markup=ReplyKeyboardRemove())
    context.user_data.clear()
    return ConversationHandler.END


def main() -> None:
    """Запускает бота."""
    application = Application.builder().token(os.getenv("TELEGRAM_TOKEN")).build()

    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            CHOOSING_ACTION: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, choice_action)
            ],
            AWAITING_INPUT: [
                MessageHandler((filters.TEXT & ~filters.COMMAND) | filters.VOICE, received_input)
            ],
            AWAITING_LINK: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, received_link)
            ],
            SELECTING_TASK_PROPERTY: [
                CallbackQueryHandler(received_task_property, pattern=r"^taskprop_")
            ],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )
    application.add_handler(conv_handler)
    application.run_polling()

if __name__ == "__main__":
    main()

