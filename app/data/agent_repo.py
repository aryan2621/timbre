from __future__ import annotations

import json
import sqlite3
from typing import Any

import app.data.database as db_mod
from app.data.models import utc_now_iso


class AgentRepository:
    @staticmethod
    def _row(row: sqlite3.Row) -> dict[str, Any]:
        agent = dict(row)
        agent["mcp_servers"] = json.loads(agent["mcp_servers"])
        return agent

    def list_all(self) -> list[dict[str, Any]]:
        with db_mod.db_manager.get_cursor() as cursor:
            cursor.execute("SELECT * FROM agents ORDER BY created_at DESC")
            return [self._row(row) for row in cursor.fetchall()]

    def get(self, agent_id: int) -> dict[str, Any] | None:
        with db_mod.db_manager.get_cursor() as cursor:
            cursor.execute("SELECT * FROM agents WHERE id = ?", (agent_id,))
            row = cursor.fetchone()
            return self._row(row) if row else None

    def create(
        self, name: str, voice_id: int | None, system_prompt: str, icon: str,
        mcp_servers: list[dict[str, str]],
        llm_model: str,
    ) -> dict[str, Any]:
        with db_mod.db_manager.get_cursor() as cursor:
            cursor.execute(
                "INSERT INTO agents (name, voice_id, system_prompt, icon, mcp_servers, llm_model, created_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                (name, voice_id, system_prompt, icon, json.dumps(mcp_servers), llm_model, utc_now_iso()),
            )
            agent_id = cursor.lastrowid
        created = self.get(agent_id)
        assert created is not None
        return created

    def delete(self, agent_id: int) -> bool:
        with db_mod.db_manager.get_cursor() as cursor:
            cursor.execute("DELETE FROM agents WHERE id = ?", (agent_id,))
            return cursor.rowcount > 0


DuplicateAgent = sqlite3.IntegrityError
agent_repo = AgentRepository()
