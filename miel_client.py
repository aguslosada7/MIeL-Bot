"""
Cliente de MIeL: inicia sesión y recorre la mensajería de cada materia
buscando mensajes sin leer, SIN abrir ningún mensaje individual (eso es
lo que los marcaría como leídos en MIeL).

Selectores confirmados a partir del HTML real de:
  - https://miel.unlam.edu.ar/principal/home/           (login)
  - https://miel.unlam.edu.ar/principal/interno/         (materias activas)
  - https://miel.unlam.edu.ar/mensajeria/entrada/comision/<id>  (bandeja)

Notas sobre cómo funciona MIeL (según el HTML provisto):

- El login NO es un <form> tradicional: el botón #btnLogin dispara un
  POST por AJAX a /principal/event/login/ y, si las credenciales son
  correctas (data.estado == 0), el JS hace
  `window.location = '.../principal/interno/'`. Por eso esperamos a
  que la URL cambie en vez de esperar una navegación de formulario.

- Cada materia en "Materias activas" es un
  `div.materia-bloque[data-id="<idComision>"]`, con el nombre en
  `div.materia-titulo`. El id de comisión (data-id) es exactamente el
  que se usa en la URL de mensajería:
  https://miel.unlam.edu.ar/mensajeria/entrada/comision/<idComision>
  Por eso NO hace falta parsear el ícono/badge de "Mensajes": directo
  se arma la URL de mensajería a partir del data-id y se entra ahí.

- En la bandeja de entrada, cada fila de mensaje es un `<tr>` dentro de
  `table.tabla-mensajes`. MIeL le agrega la clase `mensaje-no-leido` a
  las filas no leídas y `mensaje-leido` a las ya leídas (se ve en el JS
  de la página: `filaDelMensaje.addClass('mensaje-no-leido')`). Esto es
  server-side en la carga inicial, así que con solo hacer GET a la
  página (sin clickear nada) podemos filtrar `tr.mensaje-no-leido`.
  Columnas de cada fila: [0] Fecha, [1] Remitente, [2] ícono extra,
  [3] Asunto (dentro de `a.verMensaje`), [4] acciones, [5] fecha lectura.

- La bandeja puede estar paginada ("Página X de Y" arriba a la
  derecha). Si hay más de una página, se recorren agregando /pag/<n>/
  a la URL de mensajería (patrón visto en los links de detalle de
  mensaje: .../pag/1/from/entrada/id/...). Si ese patrón de paginación
  cambiara, el bot simplemente deja de encontrar más páginas y sigue
  con lo que ya juntó (no rompe).
"""
from __future__ import annotations

import re
import time
from dataclasses import dataclass, field
from typing import Optional

from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait
from webdriver_manager.chrome import ChromeDriverManager

MENSAJERIA_ENTRADA_URL = "https://miel.unlam.edu.ar/mensajeria/entrada/comision/{id}"
MENSAJERIA_ENTRADA_URL_PAG = "https://miel.unlam.edu.ar/mensajeria/entrada/comision/{id}/pag/{pag}"

PAGINA_REGEX = re.compile(r"P[aá]gina\s+(\d+)\s+de\s+(\d+)", re.IGNORECASE)


@dataclass
class Mensaje:
    remitente: str
    asunto: str
    fecha: str

    def clave_unica(self, materia: str) -> str:
        return f"{materia}|{self.fecha}|{self.remitente}|{self.asunto}"


@dataclass
class Materia:
    nombre: str
    id_comision: str
    mensajes: list[Mensaje] = field(default_factory=list)

    @property
    def url_mensajeria(self) -> str:
        return MENSAJERIA_ENTRADA_URL.format(id=self.id_comision)


class MielClient:
    def __init__(self, login_url: str, home_url: str, headless: bool = True):
        self.login_url = login_url
        self.home_url = home_url
        self.driver = self._build_driver(headless)

    @staticmethod
    def _build_driver(headless: bool) -> webdriver.Chrome:
        options = Options()
        if headless:
            options.add_argument("--headless=new")
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--window-size=1366,900")
        service = Service(ChromeDriverManager().install())
        return webdriver.Chrome(service=service, options=options)

    def close(self) -> None:
        self.driver.quit()

    # -- login -----------------------------------------------------------

    def login(self, dni: str, password: str, timeout: int = 20) -> None:
        """Completa el formulario de login (#usuario / #clave) y hace
        click en #btnLogin, que dispara un login por AJAX. Espera a que
        la URL cambie a .../principal/interno/ (éxito) o a que aparezca
        el mensaje de error (#mensajeErrorLogin)."""
        self.driver.get(self.login_url)

        usuario_input = WebDriverWait(self.driver, timeout).until(
            EC.presence_of_element_located((By.ID, "usuario"))
        )
        usuario_input.clear()
        usuario_input.send_keys(dni)

        clave_input = self.driver.find_element(By.ID, "clave")
        clave_input.clear()
        clave_input.send_keys(password)

        self.driver.find_element(By.ID, "btnLogin").click()

        deadline = time.time() + timeout
        while time.time() < deadline:
            if "interno" in self.driver.current_url:
                return
            try:
                error_div = self.driver.find_element(By.ID, "mensajeErrorLogin")
                if "w3-hide" not in (error_div.get_attribute("class") or ""):
                    mensaje = error_div.text.strip() or "Usuario o contraseña incorrectos."
                    raise RuntimeError(f"MIeL rechazó el login: {mensaje}")
            except Exception:
                pass
            time.sleep(0.3)

        raise RuntimeError(
            "Tiempo de espera agotado esperando el login en MIeL. "
            "Revisá que MIEL_DNI/MIEL_PASSWORD sean correctos o que "
            "MIeL no haya cambiado su formulario de login."
        )

    # -- materias ----------------------------------------------------------

    def obtener_materias(self) -> list[Materia]:
        """Lee 'Materias activas' y devuelve TODAS las materias con su
        nombre e id de comisión (data-id de cada div.materia-bloque)."""
        self.driver.get(self.home_url)
        WebDriverWait(self.driver, 15).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "div.materia-bloque"))
        )

        soup = BeautifulSoup(self.driver.page_source, "html.parser")
        materias: list[Materia] = []

        for bloque in soup.select("div.materia-bloque"):
            id_comision = bloque.get("data-id")
            if not id_comision:
                continue
            titulo_el = bloque.select_one("div.materia-titulo")
            nombre = titulo_el.get_text(strip=True) if titulo_el else f"Materia {id_comision}"
            materias.append(Materia(nombre=nombre, id_comision=id_comision))

        return materias

    # -- mensajería ----------------------------------------------------------

    def obtener_mensajes_no_leidos(self, materia: Materia, max_paginas: int = 10) -> list[Mensaje]:
        """Entra a la bandeja de entrada de la materia (sin clickear
        ningún mensaje) y devuelve los mensajes marcados como no leídos
        (fila <tr class="mensaje-no-leido">), recorriendo paginación si
        existe."""
        mensajes: list[Mensaje] = []
        pagina = 1

        while pagina <= max_paginas:
            url = (
                materia.url_mensajeria
                if pagina == 1
                else MENSAJERIA_ENTRADA_URL_PAG.format(id=materia.id_comision, pag=pagina)
            )
            self.driver.get(url)

            try:
                WebDriverWait(self.driver, 15).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, "table.tabla-mensajes"))
                )
            except Exception:
                # Puede pasar si la materia no tiene mensajería habilitada
                # o si la página solicitada no existe (fin de paginación).
                break

            soup = BeautifulSoup(self.driver.page_source, "html.parser")
            tabla = soup.select_one("table.tabla-mensajes")
            if tabla is None:
                break

            for fila in tabla.select("tr.mensaje-no-leido"):
                celdas = fila.find_all("td")
                if len(celdas) < 4:
                    continue
                fecha = celdas[0].get_text(strip=True)
                remitente = celdas[1].get_text(strip=True)
                asunto_link = celdas[3].select_one("a.verMensaje")
                asunto = (
                    asunto_link.get_text(strip=True)
                    if asunto_link
                    else celdas[3].get_text(strip=True)
                ) or "(sin asunto)"

                mensajes.append(Mensaje(remitente=remitente, asunto=asunto, fecha=fecha))

            # ¿Hay más páginas? Buscamos el texto "Página X de Y".
            total_paginas = self._detectar_total_paginas(soup)
            if total_paginas is None or pagina >= total_paginas:
                break
            pagina += 1

        return mensajes

    @staticmethod
    def _detectar_total_paginas(soup: BeautifulSoup) -> Optional[int]:
        texto = soup.get_text(" ", strip=True)
        match = PAGINA_REGEX.search(texto)
        if not match:
            return None
        return int(match.group(2))