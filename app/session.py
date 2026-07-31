from __future__ import annotations

from typing import Any

from app.database import Database


class SessionStore:
    """Runtime dict cache backed by SQLite persistence."""

    def __init__(self, database: Database) -> None:
        self.database = database
        self.sessions: dict[int, dict[str, Any]] = {}

    async def _ensure(self, chat_id: int) -> dict[str, Any]:
        if chat_id not in self.sessions:
            self.sessions[chat_id] = {
                "campaign": await self.database.get_campaign(chat_id),
                "journal": await self.database.get_journal(chat_id, limit=50),
                "combat": await self.database.get_combat(chat_id),
            }
        return self.sessions[chat_id]

    async def get_campaign(self, chat_id: int) -> dict[str, Any] | None:
        return (await self._ensure(chat_id))["campaign"]

    async def set_campaign(self, chat_id: int, campaign: dict[str, Any]) -> None:
        session = await self._ensure(chat_id)
        session["campaign"] = campaign
        await self.database.save_campaign(chat_id, campaign)

    async def log(
        self,
        chat_id: int,
        event_type: str,
        content: str,
        payload: dict[str, Any] | None = None,
    ) -> None:
        session = await self._ensure(chat_id)
        campaign = session["campaign"]
        entry = {
            "event_type": event_type,
            "content": content,
            "payload": payload or {},
            "created_at": "сейчас",
        }
        session["journal"].append(entry)
        session["journal"] = session["journal"][-100:]
        await self.database.add_journal(
            chat_id,
            campaign["name"] if campaign else None,
            event_type,
            content,
        )

    async def get_journal(self, chat_id: int, limit: int = 30) -> list[dict[str, str]]:
        session = await self._ensure(chat_id)
        return session["journal"][-limit:]

    async def get_combat(self, chat_id: int) -> dict[str, Any] | None:
        return (await self._ensure(chat_id))["combat"]

    async def set_combat(self, chat_id: int, state: dict[str, Any]) -> None:
        session = await self._ensure(chat_id)
        session["combat"] = state
        await self.database.save_combat(chat_id, state)

    async def clear_combat(self, chat_id: int) -> None:
        session = await self._ensure(chat_id)
        session["combat"] = None
        await self.database.clear_combat(chat_id)
