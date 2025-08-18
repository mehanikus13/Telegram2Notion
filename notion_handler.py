import os
import logging
import notion_client
from typing import Dict, List, Optional, Tuple

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def _get_notion_client() -> notion_client.Client:
    notion_token = os.getenv("NOTION_TOKEN")
    if not notion_token:
        logger.error("NOTION_TOKEN не найден в переменных окружения.")
        raise RuntimeError("NOTION_TOKEN is missing")
    return notion_client.Client(auth=notion_token)


def get_property_meta(database_id: str, property_name: str) -> Optional[Dict]:
    """
    Возвращает метаданные свойства базы данных по имени (тип, опции и т.д.).
    Возвращает None, если свойство не найдено.
    """
    try:
        notion = _get_notion_client()
        db = notion.databases.retrieve(database_id=database_id)
        properties: Dict = db.get("properties", {})
        return properties.get(property_name)
    except notion_client.APIResponseError as e:
        logger.error(f"Не удалось получить метаданные базы данных Notion: {e}")
        return None


def get_property_options(database_id: str, property_name: str) -> Tuple[List[str], Optional[str]]:
    """
    Возвращает список доступных опций для select/multi_select свойства
    и тип свойства ('select' | 'multi_select'). Если свойство не select-подобное,
    вернет ([], None).
    """
    meta = get_property_meta(database_id, property_name)
    if not meta:
        return [], None

    prop_type: str = meta.get("type")
    if prop_type not in ("select", "multi_select"):
        return [], None

    options = meta.get(prop_type, {}).get("options", [])
    option_names: List[str] = [opt.get("name") for opt in options if opt.get("name")]
    return option_names, prop_type


def create_notion_page(database_id: str, text: str, title_property_name: Optional[str] = None):
    """
    Создает новую запись в указанной базе данных Notion.

    Args:
        database_id: ID базы данных Notion.
        text: Текст для заголовка новой страницы.
    """
    notion = _get_notion_client()

    try:
        title_prop = title_property_name or "Name"
        new_page_data = {
            "parent": {"database_id": database_id},
            "properties": {
                title_prop: {  # Название основного столбца Title может быть переопределено
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


def create_link_page(database_id: str, title: str, summary: str, url: str, tags: list):
    """
    Создает новую страницу для ссылки в Notion с заголовком, URL, тегами и саммари.
    """
    notion = _get_notion_client()

    # 1. Создаем страницу с основными свойствами
    try:
        title_prop = os.getenv("NOTION_LINK_TITLE_PROP", "Name")
        url_prop = os.getenv("NOTION_LINK_URL_PROP", "URL")
        tags_prop = os.getenv("NOTION_LINK_TAGS_PROP", "Tags")

        page_properties = {
            title_prop: {"title": [{"text": {"content": title}}]},
            url_prop: {"url": url},
            tags_prop: {"multi_select": [{"name": tag} for tag in tags]}
        }

        new_page_response = notion.pages.create(
            parent={"database_id": database_id},
            properties=page_properties
        )
        page_id = new_page_response['id']
        logger.info(f"Успешно создана страница Notion с ID: {page_id}")

    except notion_client.APIResponseError as e:
        logger.error(f"Ошибка при создании страницы Notion: {e}")
        logger.error("Убедитесь, что в базе данных заданы корректные имена свойств (NOTION_LINK_TITLE_PROP, NOTION_LINK_URL_PROP, NOTION_LINK_TAGS_PROP).")
        return None

    # 2. Добавляем саммари как контент на страницу
    try:
        if summary:
            # Разделяем саммари на параграфы
            summary_blocks = []
            for paragraph in summary.split('\n'):
                if paragraph: # Пропускаем пустые строки
                    summary_blocks.append({
                        "object": "block",
                        "type": "paragraph",
                        "paragraph": {
                            "rich_text": [{"type": "text", "text": {"content": paragraph}}]
                        }
                    })

            if summary_blocks:
                notion.blocks.children.append(
                    block_id=page_id,
                    children=summary_blocks
                )
                logger.info(f"Успешно добавлено саммари на страницу {page_id}")

    except notion_client.APIResponseError as e:
        logger.error(f"Ошибка при добавлении контента на страницу Notion: {e}")
        # Страница уже создана, так что не возвращаем ошибку, а просто логируем

    return new_page_response


def create_task_page(
    database_id: str,
    title: str,
    properties: Dict[str, object],
    title_property_name: Optional[str] = None,
):
    """
    Создает страницу задачи с заголовком и набором свойств (select/multi_select и др.).

    properties: словарь { NotionPropertyName: value }, где value — либо строка (для select),
    либо список строк (для multi_select). Тип свойства определяется автоматически по базе.
    """
    notion = _get_notion_client()

    try:
        # Базовые свойства - заголовок
        title_prop = title_property_name or "Name"
        page_properties: Dict[str, object] = {
            title_prop: {
                "title": [
                    {
                        "text": {"content": title}
                    }
                ]
            }
        }

        # Подтягиваем метаданные, чтобы корректно сформировать payload по типу свойств
        db = notion.databases.retrieve(database_id=database_id)
        db_props: Dict = db.get("properties", {})

        for prop_name, raw_value in properties.items():
            meta = db_props.get(prop_name)
            if not meta:
                logger.warning(f"Свойство '{prop_name}' не найдено в базе данных. Пропускаю.")
                continue

            prop_type = meta.get("type")
            if prop_type == "select" and isinstance(raw_value, str):
                page_properties[prop_name] = {"select": {"name": raw_value}}
            elif prop_type == "multi_select":
                values: List[str] = raw_value if isinstance(raw_value, list) else [str(raw_value)]
                page_properties[prop_name] = {"multi_select": [{"name": v} for v in values]}
            else:
                # На случай других типов — пытаемся положить как есть, если Notion поддержит
                page_properties[prop_name] = {prop_type: raw_value}

        new_page_response = notion.pages.create(
            parent={"database_id": database_id},
            properties=page_properties,
        )
        logger.info("Задача успешно создана в Notion.")
        return new_page_response

    except notion_client.APIResponseError as e:
        logger.error(f"Ошибка при создании страницы задачи в Notion: {e}")
        return None
