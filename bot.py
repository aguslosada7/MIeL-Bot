"""
Bot de Discord que avisa cuando llegan mensajes nuevos en MIeL.

- Cada POLL_INTERVAL_SECONDS revisa las materias con el círculo rojo de
  no leídos y, para las que tengan, entra a la bandeja de Mensajería
  (sin abrir mensajes) para leer remitente/asunto/fecha.
- Envía un embed por Discord por cada mensaje nuevo que no haya sido
  notificado todavía (StateStore lleva el registro local).
- No marca nada como leído en MIeL: solo lee la lista.

Comando manual: escribiendo "!miel" en el canal configurado se dispara
una revisión inmediata, útil para probar sin esperar al intervalo.
"""
from __future__ import annotations

import asyncio
import logging

import discord
from discord.ext import commands, tasks

from config import Settings, load_settings
from miel_client import MielClient
from state_store import StateStore

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
log = logging.getLogger("miel-bot")

intents = discord.Intents.default()
intents.message_content = True

bot = commands.Bot(command_prefix="!", intents=intents)

settings: Settings = load_settings()
state = StateStore()


def revisar_miel_sync() -> list[tuple[str, "Mensaje"]]:  # noqa: F821 - tipo de miel_client
    """Corre en un hilo aparte (Selenium es bloqueante). Devuelve una
    lista de (nombre_materia, mensaje) para los mensajes nuevos.

    Recorre TODAS las materias activas y, para cada una, entra a su
    bandeja de mensajería (sin clickear ningún mensaje) para ver si hay
    filas marcadas como no leídas."""
    client = MielClient(
        login_url=settings.miel_login_url,
        home_url=settings.miel_home_url,
        headless=settings.headless,
    )
    nuevos = []
    try:
        client.login(settings.miel_dni, settings.miel_password)
        materias = client.obtener_materias()
        log.info("Materias encontradas: %s", [m.nombre for m in materias])

        for materia in materias:
            log.info("Revisando mensajería de: %s ...", materia.nombre)
            mensajes = client.obtener_mensajes_no_leidos(materia)
            if mensajes:
                log.info("  -> %d mensaje(s) sin leer", len(mensajes))
            for mensaje in mensajes:
                clave = mensaje.clave_unica(materia.nombre)
                if not state.ya_notificado(clave):
                    nuevos.append((materia.nombre, mensaje))
        log.info("Revisión de MIeL completa.")
    finally:
        client.close()
    return nuevos


async def notificar(materia_nombre: str, mensaje) -> None:  # noqa: ANN001
    canal = bot.get_channel(settings.discord_channel_id)
    if canal is None:
        log.error(
            "No se encontró el canal %s. ¿El bot está en ese servidor y tiene permisos?",
            settings.discord_channel_id,
        )
        return

    embed = discord.Embed(
        title="📩 Nuevo mensaje en MIeL",
        color=discord.Color.green(),
    )
    embed.add_field(name="Materia", value=materia_nombre, inline=False)
    embed.add_field(name="De", value=mensaje.remitente, inline=True)
    embed.add_field(name="Fecha", value=mensaje.fecha or "—", inline=True)
    embed.add_field(name="Asunto", value=mensaje.asunto, inline=False)

    await canal.send(embed=embed)
    state.marcar_notificado(mensaje.clave_unica(materia_nombre))


@tasks.loop(seconds=1)  # el intervalo real se fija en on_ready (ver más abajo)
async def revisar_periodicamente() -> None:
    log.info("Revisando MIeL...")
    try:
        nuevos = await asyncio.to_thread(revisar_miel_sync)
    except Exception:  # noqa: BLE001
        log.exception("Error revisando MIeL")
        return

    if not nuevos:
        log.info("Sin mensajes nuevos.")
        return

    for materia_nombre, mensaje in nuevos:
        await notificar(materia_nombre, mensaje)


@bot.event
async def on_ready() -> None:
    log.info("Conectado como %s", bot.user)
    if not revisar_periodicamente.is_running():
        revisar_periodicamente.change_interval(seconds=settings.poll_interval_seconds)
        await asyncio.sleep(5)
        revisar_periodicamente.start()


@bot.command(name="miel")
async def miel_command(ctx: commands.Context) -> None:
    """Fuerza una revisión inmediata de MIeL (sin esperar al intervalo)."""
    await ctx.send("Revisando MIeL ahora mismo...")
    nuevos = await asyncio.to_thread(revisar_miel_sync)
    if not nuevos:
        await ctx.send("No hay mensajes nuevos. ✅")
        return
    for materia_nombre, mensaje in nuevos:
        await notificar(materia_nombre, mensaje)


def main() -> None:
    bot.run(settings.discord_token)


if __name__ == "__main__":
    main()