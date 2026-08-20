"""
Carga y valida la configuración del bot desde variables de entorno (.env).
"""
from __future__ import annotations

import os
from dataclasses import dataclass

from dotenv import load_dotenv

load_dotenv()


def _get_required(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise RuntimeError(
            f"Falta la variable de entorno obligatoria '{name}'. "
            f"Revisá tu archivo .env (podés basarte en .env.example)."
        )
    return value


def _get_bool(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in ("1", "true", "yes", "si", "sí")


@dataclass(frozen=True)
class Settings:
    miel_dni: str
    miel_password: str
    miel_login_url: str
    miel_home_url: str

    discord_token: str
    discord_channel_id: int

    poll_interval_seconds: int
    headless: bool


def load_settings() -> Settings:
    return Settings(
        miel_dni=_get_required("MIEL_DNI"),
        miel_password=_get_required("MIEL_PASSWORD"),
        miel_login_url=os.getenv(
            "MIEL_LOGIN_URL", "https://miel.unlam.edu.ar/principal/home/"
        ),
        miel_home_url=os.getenv(
            "MIEL_HOME_URL", "https://miel.unlam.edu.ar/principal/interno/"
        ),
        discord_token=_get_required("DISCORD_TOKEN"),
        discord_channel_id=int(_get_required("DISCORD_CHANNEL_ID")),
        poll_interval_seconds=int(os.getenv("POLL_INTERVAL_SECONDS", "60")),
        headless=_get_bool("HEADLESS", True),
    )
