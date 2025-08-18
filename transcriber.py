import os
import logging
import openai
from pydub import AudioSegment
import tempfile
from telegram.ext import ContextTypes

# Настройка логирования
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

# Настройка клиента OpenAI
# Ключ API будет загружен из переменных окружения при запуске bot.py
if os.getenv("OPENAI_API_KEY"):
    openai.api_key = os.getenv("OPENAI_API_KEY")
else:
    logger.warning("OPENAI_API_KEY не найден. Модуль транскрипции не будет работать.")
    openai.api_key = None


async def transcribe_voice(voice_file_id: str, context: ContextTypes.DEFAULT_TYPE) -> str | None:
    """
    Скачивает голосовое сообщение, конвертирует его в mp3 и транскрибирует с помощью OpenAI Whisper.
    Возвращает текст транскрипции или строку с описанием ошибки.
    """
    if not openai.api_key:
        return "Ошибка: Ключ OpenAI API не настроен."

    ogg_path = None
    mp3_path = None

    try:
        voice_file = await context.bot.get_file(voice_file_id)

        with tempfile.NamedTemporaryFile(delete=False, suffix='.ogg') as ogg_file:
            await voice_file.download_to_drive(ogg_file.name)
            ogg_path = ogg_file.name

        mp3_path = ogg_path.replace(".ogg", ".mp3")

        try:
            audio = AudioSegment.from_ogg(ogg_path)
            audio.export(mp3_path, format="mp3")
        except Exception as e:
            logger.error(f"Ошибка конвертации аудио (убедитесь, что ffmpeg установлен): {e}")
            return "Ошибка: Не удалось обработать аудиофайл. Убедитесь, что на сервере установлен ffmpeg."

        with open(mp3_path, "rb") as audio_file:
            response = await openai.audio.transcriptions.acreate(
                model="whisper-1",
                file=audio_file
            )

        return response.text

    except openai.APIError as e:
        logger.error(f"Ошибка OpenAI API: {e}")
        return "Ошибка: Не удалось связаться с сервисом транскрипции."
    except Exception as e:
        logger.error(f"Неожиданная ошибка при транскрипции: {e}")
        return "Ошибка: Произошла внутренняя ошибка при обработке вашего сообщения."
    finally:
        # Гарантированное удаление временных файлов
        if ogg_path and os.path.exists(ogg_path):
            os.remove(ogg_path)
        if mp3_path and os.path.exists(mp3_path):
            os.remove(mp3_path)
