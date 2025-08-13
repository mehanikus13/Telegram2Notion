import os
import logging
import notion_client

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def create_notion_page(database_id: str, text: str):
    """
    Создает новую запись в указанной базе данных Notion.

    Args:
        database_id: ID базы данных Notion.
        text: Текст для заголовка новой страницы.
    """
    notion_token = os.getenv("NOTION_TOKEN")
    if not notion_token:
        logger.error("NOTION_TOKEN не найден в переменных окружения.")
        return

    notion = notion_client.Client(auth=notion_token)

    try:
        new_page_data = {
            "parent": {"database_id": database_id},
            "properties": {
                "Name": {  # 'Name' - это стандартное имя для основного столбца Title
                    "title": [
                        {
                            "text": {
                                "content": text
                            }
                        }
                    ]
                }
            }
        }

        response = notion.pages.create(**new_page_data)
        logger.info("Успешно создана новая страница в Notion.")
        return response

    except notion_client.APIResponseError as e:
        logger.error(f"Ошибка при работе с Notion API: {e}")
        return None
