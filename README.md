# MIeL Bot

MIeL Bot es un bot de Discord que avisa cuando llega un mensaje nuevo en MIeL (Materias Interactivas en Línea) sin necesidad de tener la página abierta y sin marcar los mensajes como leídos.

## Funcionamiento

1. Con Selenium, inicia sesión en MIeL (`#usuario` / `#clave` + click en `#btnLogin`, que en MIeL dispara un login por AJAX y redirige a `/principal/interno/` si es correcto).
2. Entra a Materias activas y lee cada materia (`div.materia-bloque[data-id]`), tomando su nombre e id de comisión.
3. Para cada materia, entra a su bandeja de Mensajería (`https://miel.unlam.edu.ar/mensajeria/entrada/comision/<id>`) sin clickear ningún mensaje y busca las filas `<tr class="mensaje-no-leido">`, que es la clase que MIeL le pone a los mensajes sin leer. De ahí saca remitente, asunto y fecha. Si la bandeja tiene más de una página, las recorre todas.
4. Manda un embed a un canal de Discord o como mensaje directo por cada mensaje nuevo, indicando de qué materia es, guardando un registro local en `state.json` para no repetir avisos entre revisiones.
5. Repite esto cada `POLL_INTERVAL_SECONDS` (que por defecto es de 60 segundos).

Los selectores usados (`div.materia-bloque`, `div.materia-titulo`, `table.tabla-mensajes`, `tr.mensaje-no-leido`, `a.verMensaje`) están confirmados contra el HTML real de MIeL. La única parte no verificada es la paginación de mensajería (se asume el patrón `.../comision/<id>/pag/<n>`); si nunca hay más de una página de mensajes sin leer, esto no debería afectar en nada.

Adicionalmente, se puede escribir **!miel** en el canal para forzar una revisión inmediata en vez de esperar al intervalo.

## Estructura del proyecto

```
config.py          # Carga la configuración desde .env
miel_client.py     # Login y scraping de MIeL (Selenium + BeautifulSoup)
inspect_dom.py     # Herramienta para calibrar los selectores CSS reales
state_store.py     # Registro local de mensajes ya notificados
bot.py             # Bot de Discord (loop de polling + comando !miel)
.env.example       # Plantilla de variables de entorno
requirements.txt
```

## Instalación

```bash
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
```

Es necesario tener Google Chrome instalado. Selenium y webdriver-manager bajan el ChromeDriver correspondiente en forma automática.

## Configuración

1. Copiar `.env.example` a `.env`:
   ```bash
   cp .env.example .env
   ```
2. Completar `MIEL_DNI` y `MIEL_PASSWORD` con credenciales válidas.
3. Crear una aplicación/bot en el [Portal de desarrolladores de Discord](https://discord.com/developers/applications), activar **Message Content Intent** en la sección "Bot", copiar el token y pegarlo en `DISCORD_TOKEN`.
4. Invitar el bot al servidor (OAuth2 → URL Generator → scope `bot`, permisos `Send Messages` y `Embed Links`).
5. Activar el **Modo desarrollador** en Discord para copiar el ID del canal o cuenta donde se recibirán los mensajes y pegarlo en `DISCORD_CHANNEL_ID`.

## Uso

Una vez calibrados los selectores, se ejecuta:

```bash
python bot.py
```

El bot se conecta a Discord y empieza a revisar MIeL periódicamente. Se debe dejar corriendo en un servidor, VPS, Raspberry Pi, o similar para que
funcione de forma continua.