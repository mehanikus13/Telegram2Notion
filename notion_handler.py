import os
import logging
import asyncio
from typing import Dict, Optional

import notion_client

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def get_notion_client() -> Optional[notion_client.Client]:
    """Инициализирует и возвращает клиент Notion."""
    notion_token = os.getenv("NOTION_TOKEN")
    if not notion_token:
        logger.error("NOTION_TOKEN не найден в переменных окружения.")
        return None
    return notion_client.Client(auth=notion_token)


async def get_database_properties(database_id: str) -> Optional[Dict[str, Dict]]:
    """Возвращает карту свойств БД (только select/multi_select) с их опциями."""
    def _retrieve() -> Optional[Dict[str, Dict]]:
        notion = get_notion_client()
        if not notion:
            return None
        try:
            response = notion.databases.retrieve(database_id=database_id)
            properties: Dict[str, Dict] = {}
            for name, prop_data in response.get("properties", {}).items():
                prop_type = prop_data.get("type")
                if prop_type in ["select", "multi_select"]:
                    options = [opt["name"] for opt in prop_data[prop_type].get("options", [])]
                    properties[name] = {"type": prop_type, "options": options}
            return properties
        except Exception as exc:
            logger.error(f"Ошибка при получении свойств базы данных {database_id}: {exc}")
            return None

    return await asyncio.to_thread(_retrieve)


async def create_notion_page(database_id: str, title_property_name: str, title_value: str) -> Optional[Dict]:
    """Создает страницу в Notion в заданной БД, устанавливая значение title-свойства."""
    def _create() -> Optional[Dict]:
        notion = get_notion_client()
        if not notion:
            return None
        try:
            title_prop = title_property_name or "Name"
            new_page_data = {
                "parent": {"database_id": database_id},
                "properties": {
                    title_prop: {
                        "title": [
                            {"type": "text", "text": {"content": title_value or ""}}
                        ]
                    }
                },
            }
            response = notion.pages.create(**new_page_data)
            logger.info("Успешно создана новая страница в Notion.")
            return response
        except Exception as exc:
            logger.error(f"Ошибка при создании страницы Notion: {exc}")
            return None

    return await asyncio.to_thread(_create)


async def update_page_properties(page_id: str, properties_to_update: Dict) -> Optional[Dict]:
    """Обновляет свойства существующей страницы Notion."""
    def _update() -> Optional[Dict]:
        notion = get_notion_client()
        if not notion:
            return None
        try:
            response = notion.pages.update(page_id=page_id, properties=properties_to_update)
            logger.info(f"Свойства страницы {page_id} обновлены.")
            return response
        except Exception as exc:
            logger.error(f"Ошибка при обновлении свойств страницы {page_id}: {exc}")
            return None

    return await asyncio.to_thread(_update)


async def create_link_page(
    database_id: str,
    title_prop: str,
    url_prop: str,
    tags_prop: str,
    data: Dict,
) -> Optional[Dict]:
    """Создает страницу в БД ссылок с заголовком, URL, тегами и саммари (как блоки)."""
    def _create() -> Optional[Dict]:
        notion = get_notion_client()
        if not notion:
            return None

        title_value = data.get("title") or "Ссылка"
        url_value = data.get("url")
        tags_value = data.get("tags") or []
        summary = data.get("summary") or ""

        page_properties = {
            (title_prop or "Name"): {
                "title": [{"type": "text", "text": {"content": title_value}}]
            },
        }
        if url_value:
            page_properties[url_prop or "URL"] = {"url": url_value}
        if tags_value:
            page_properties[tags_prop or "Tags"] = {
                "multi_select": [{"name": tag} for tag in tags_value if tag]
            }

        try:
            new_page_response = notion.pages.create(
                parent={"database_id": database_id}, properties=page_properties
            )
            page_id = new_page_response["id"]
            logger.info(f"Успешно создана страница для ссылки с ID: {page_id}")

            # Добавляем саммари в виде параграфов
            if summary:
                summary_blocks = []
                for p in summary.split("\n"):
                    if p:
                        summary_blocks.append(
                            {
                                "object": "block",
                                "type": "paragraph",
                                "paragraph": {
                                    "rich_text": [
                                        {"type": "text", "text": {"content": p}}
                                    ]
                                },
                            }
                        )

                if summary_blocks:
                    notion.blocks.children.append(
                        block_id=page_id, children=summary_blocks
                    )
                    logger.info(f"Успешно добавлено саммари на страницу {page_id}")

            return new_page_response
        except Exception as exc:
            logger.error(f"Ошибка при создании страницы для ссылки: {exc}")
            return None

    return await asyncio.to_thread(_create)
