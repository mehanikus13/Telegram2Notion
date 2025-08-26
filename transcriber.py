import os
import logging
import tempfile
from telegram.ext import ContextTypes
from openai import AsyncOpenAI

# Настройка логирования
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

# Настройка клиента OpenAI
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
if OPENAI_API_KEY:
    openai_client = AsyncOpenAI(api_key=OPENAI_API_KEY)
else:
    logger.warning("OPENAI_API_KEY не найден. Модуль транскрипции не будет работать.")
    openai_client = None


async def transcribe_voice(voice_file_id: str, context: ContextTypes.DEFAULT_TYPE) -> str | None:
    """
    Скачивает голосовое сообщение, конвертирует его в mp3 и транскрибирует с помощью OpenAI Whisper.
    Возвращает текст транскрипции или строку с описанием ошибки.
    """
    if not openai_client:
        return "Ошибка: Ключ OpenAI API не настроен."

    ogg_path = None

    try:
        voice_file = await context.bot.get_file(voice_file_id)

        with tempfile.NamedTemporaryFile(delete=False, suffix='.ogg') as ogg_file:
            await voice_file.download_to_drive(ogg_file.name)
            ogg_path = ogg_file.name

        # Whisper поддерживает формат OGG напрямую, конвертация не требуется
        with open(ogg_path, "rb") as audio_file:
            response = await openai_client.audio.transcriptions.create(
                model="whisper-1",
                file=audio_file
            )

        return response.text

    except Exception as e:
        logger.error(f"Неожиданная ошибка при транскрипции: {e}")
        return "Ошибка: Произошла внутренняя ошибка при обработке вашего сообщения."
    finally:
        # Гарантированное удаление временных файлов
        if ogg_path and os.path.exists(ogg_path):
            os.remove(ogg_path)
