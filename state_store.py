"""
Guarda en un archivo JSON qué mensajes ya fueron notificados por Discord,
para no avisar dos veces el mismo mensaje en cada ciclo de polling.

No marca nada como leído en MIeL: es solo un registro local del bot.
"""
from __future__ import annotations

import json
import os
from pathlib import Path


class StateStore:
    def __init__(self, path: str = "state.json"):
        self.path = Path(path)
        self._notificados: set[str] = self._cargar()

    def _cargar(self) -> set[str]:
        if not self.path.exists():
            return set()
        try:
            with open(self.path, "r", encoding="utf-8") as f:
                data = json.load(f)
            return set(data.get("notificados", []))
        except (json.JSONDecodeError, OSError):
            return set()

    def _guardar(self) -> None:
        tmp_path = self.path.with_suffix(".tmp")
        with open(tmp_path, "w", encoding="utf-8") as f:
            json.dump({"notificados": sorted(self._notificados)}, f, ensure_ascii=False, indent=2)
        os.replace(tmp_path, self.path)

    def ya_notificado(self, clave: str) -> bool:
        return clave in self._notificados

    def marcar_notificado(self, clave: str) -> None:
        self._notificados.add(clave)
        self._guardar()
