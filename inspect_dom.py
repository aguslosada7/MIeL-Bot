"""
Herramienta de diagnóstico (opcional). Los selectores que usa
miel_client.py ya están confirmados contra el HTML real de MIeL, así
que en general NO hace falta correr esto. Es útil solo si:

  - MIeL cambia de diseño en el futuro y el bot deja de encontrar
    materias o mensajes.
  - Querés confirmar a mano cómo se ve la paginación de mensajería
    cuando hay más de una página de mensajes (algo que no pudimos
    verificar de antemano).

Guarda el HTML de la página de materias y, opcionalmente, de una
bandeja de mensajería puntual, para inspeccionarlo.

Uso:
    python inspect_dom.py
    python inspect_dom.py --comision 118139
"""
from __future__ import annotations

import argparse

from config import load_settings
from miel_client import MENSAJERIA_ENTRADA_URL, MielClient


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--comision",
        help="Id de comisión de una materia puntual (el que aparece en "
        "la URL de mensajería) para volcar también ese HTML.",
    )
    parser.add_argument(
        "--show-browser",
        action="store_true",
        help="Corre el navegador visible en vez de headless.",
    )
    args = parser.parse_args()

    settings = load_settings()
    client = MielClient(
        login_url=settings.miel_login_url,
        home_url=settings.miel_home_url,
        headless=not args.show_browser,
    )

    try:
        print(f"Iniciando sesión como {settings.miel_dni}...")
        client.login(settings.miel_dni, settings.miel_password)

        print(f"Cargando {settings.miel_home_url} ...")
        client.driver.get(settings.miel_home_url)
        with open("dump_materias.html", "w", encoding="utf-8") as f:
            f.write(client.driver.page_source)
        print("Guardado: dump_materias.html")

        materias = client.obtener_materias()
        print(f"\nMaterias detectadas ({len(materias)}):")
        for m in materias:
            print(f"  - {m.nombre} (comisión {m.id_comision}) -> {m.url_mensajeria}")

        if args.comision:
            url = MENSAJERIA_ENTRADA_URL.format(id=args.comision)
            print(f"\nCargando {url} ...")
            client.driver.get(url)
            with open("dump_mensajes.html", "w", encoding="utf-8") as f:
                f.write(client.driver.page_source)
            print("Guardado: dump_mensajes.html")

    finally:
        client.close()


if __name__ == "__main__":
    main()
