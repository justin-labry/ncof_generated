# NCOF 구독 상태를 원자적으로 JSON 파일에 저장하는 저장소

import asyncio
import json
import logging
import os
import time
import uuid
from pathlib import Path
from typing import Any

from fastapi.encoders import jsonable_encoder

logger = logging.getLogger(__name__)


class JsonStateStore:
    """NCOF 런타임 상태를 단일 JSON 파일로 관리한다."""

    def __init__(self, path: str | Path | None = None):
        configured_path = path or os.getenv("NCOF_STATE_FILE")
        self.path = Path(configured_path) if configured_path else Path("data/ncof_state.json")
        self._lock = asyncio.Lock()

    def load(self) -> dict[str, Any]:
        """저장 상태를 읽고, 손상된 파일은 보존한 뒤 빈 상태를 반환한다."""
        if not self.path.exists():
            return {"schema_version": 1, "subscriptions": {}}

        try:
            with self.path.open("r", encoding="utf-8") as state_file:
                state = json.load(state_file)
            if state.get("schema_version") != 1 or not isinstance(
                state.get("subscriptions"), dict
            ):
                raise ValueError("지원하지 않는 상태 파일 형식")
            return state
        except (OSError, ValueError, json.JSONDecodeError) as error:
            backup_path = self.path.with_suffix(self.path.suffix + ".corrupt")
            try:
                self.path.replace(backup_path)
            except OSError:
                logger.exception("손상된 상태 파일을 이동하지 못함: %s", self.path)
            logger.error("상태 파일을 읽지 못해 빈 상태로 시작함: %s", error)
            return {"schema_version": 1, "subscriptions": {}}

    async def save(self, state: dict[str, Any]) -> None:
        """임시 파일을 거쳐 상태 파일을 원자적으로 교체한다."""
        async with self._lock:
            await asyncio.to_thread(self._save_sync, state)

    def _save_sync(self, state: dict[str, Any]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary_path = self.path.with_name(
            f"{self.path.name}.{uuid.uuid4().hex}.tmp"
        )
        try:
            with temporary_path.open("w", encoding="utf-8") as state_file:
                json.dump(
                    jsonable_encoder(state), state_file, ensure_ascii=False, indent=2
                )
                state_file.flush()
                os.fsync(state_file.fileno())

            for attempt in range(3):
                try:
                    os.replace(temporary_path, self.path)
                    return
                except PermissionError:
                    if attempt == 2:
                        raise
                    time.sleep(0.05 * (attempt + 1))
        finally:
            if temporary_path.exists():
                temporary_path.unlink()
