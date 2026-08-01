"""Кнопочный интерфейс и визуальные сцены D&D-бота."""

from __future__ import annotations

from typing import Any


def build_button_router(database: Any, store: Any) -> Any:
    """Лениво загружает aiogram-роутеры и упрощает импорт тестовых модулей."""
    from app.button_ui.router import build_button_router as router_factory

    return router_factory(database, store)


__all__ = ["build_button_router"]
