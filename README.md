# openclawT

Bot de Telegram para recordatorios y agenda personal.

## Setup

1. Creá el bot en Telegram hablando con [@BotFather](https://t.me/BotFather):
   `/newbot`, elegí nombre y usuario, y copiá el token que te da.
2. Copiá `.env.example` a `.env` y pegá tu token:
   ```bash
   cp .env.example .env
   ```
3. Instalá dependencias (ya hay un venv creado):
   ```bash
   source venv/bin/activate
   pip install -r requirements.txt
   ```
4. Corré el bot:
   ```bash
   python3 bot.py
   ```

## Comandos

- `/start` - ayuda
- `/recordar <tiempo> <mensaje>` - crea un recordatorio
  - Tiempo relativo: `10m`, `2h`, `1d`
  - Hora de hoy/mañana: `20:30`
  - Fecha y hora exacta: `05/09/2026 14:00`
- `/lista` - recordatorios pendientes
- `/borrar <id>` - elimina un recordatorio

Los recordatorios se guardan en `recordatorios.db` (SQLite) y se reprograman
automáticamente si reiniciás el bot.

## Servicio automático (LaunchAgent)

El bot corre como un LaunchAgent de macOS (`~/Library/LaunchAgents/com.openclawt.draculabot.plist`):
arranca solo cuando iniciás sesión en la Mac y se reinicia solo si se cae.
Los logs quedan en `bot.log`.

Importante: el proyecto vive en `~/openclawT` (no en `~/Desktop`) porque macOS
bloquea el acceso a Desktop/Documents/Downloads para procesos en segundo plano.

Comandos útiles:

```bash
# Ver estado
launchctl print gui/$(id -u)/com.openclawt.draculabot | grep state

# Reiniciar el bot (por ejemplo después de editar el código)
launchctl kickstart -k gui/$(id -u)/com.openclawt.draculabot

# Apagarlo del todo
launchctl bootout gui/$(id -u)/com.openclawt.draculabot

# Volver a activarlo
launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/com.openclawt.draculabot.plist
```

Como sigue corriendo en tu Mac, solo funciona mientras la compu esté prendida
(aunque no haga falta tener la terminal abierta). Para 24/7 real e independiente
de tu compu hace falta un servidor en la nube (la mayoría pide tarjeta aunque
te quedes en el nivel gratuito, ej. Fly.io).

## Alertas de banco (solo lectura, multi-banco)

El bot vigila en tiempo real (IMAP IDLE, no consultas cada tanto) las
notificaciones que tus bancos mandan por correo a Gmail, y te avisa por
Telegram casi al instante cuando detecta:

- Depósitos recibidos
- Compras con tarjeta
- Códigos de retiro sin tarjeta
- Inicios de sesión en la banca digital

**Importante:** esto es solo lectura. El bot nunca inicia sesión en la banca
en línea ni ejecuta transferencias, compras o pagos — solo lee correos que el
banco ya mandó, usando una **contraseña de aplicación de Gmail** (no tu
contraseña normal), configurada en `.env`:

```
GMAIL_ADDRESS=tu_correo@gmail.com
GMAIL_APP_PASSWORD=contraseña_de_aplicacion_de_16_caracteres
```

Generá la contraseña de aplicación en
[myaccount.google.com/apppasswords](https://myaccount.google.com/apppasswords).

### Agregar un banco nuevo

Cada banco es un adaptador independiente en [bancos/](bancos/). Hoy solo está
[bancos/cuscatlan.py](bancos/cuscatlan.py). Para sumar otro:

1. Copiá `bancos/cuscatlan.py` a un archivo nuevo (ej. `bancos/agricola.py`).
2. Cambiá `REMITENTE` y `NOMBRE`, y ajustá `parsear()` con un ejemplo real de
   una notificación de ese banco (pedímelo si necesitás ayuda armándolo).
3. Importalo y agregalo a `MODULOS` en [bancos/\_\_init\_\_.py](bancos/__init__.py).

El motor (`banco.py`) no necesita ningún cambio: detecta automáticamente de
qué banco es cada correo según el remitente.

## Rachas y logros

`/racha` muestra cuántos días seguidos llevás anotando gastos y qué logros
desbloqueaste. Los logros se avisan solos apenas los cruzás (no hace falta
pedirlos):

- Racha: 3, 7, 14, 30, 60 y 100 días seguidos
- Total de gastos registrados: 1, 10, 50, 100 y 500

## Dashboard web (opcional)

Un panel local con gráficos de tus gastos, recordatorios pendientes y logros.
Corre aparte del bot, en tu propia compu (no se expone a internet):

```bash
source venv/bin/activate
python3 dashboard.py
```

Después abrí [http://127.0.0.1:5050](http://127.0.0.1:5050) en el navegador.

## Tests

Suite de `pytest` (32 tests) que cubre el intérprete de fechas, la
persistencia, el resumidor, el parser de bancos y la integridad del menú del
bot. Corre sola en GitHub Actions en cada push (ver
[.github/workflows/tests.yml](.github/workflows/tests.yml)), y también podés
correrla localmente:

```bash
source venv/bin/activate
pip install -r requirements-dev.txt
pytest -v
```

## Próximos pasos posibles

- Alertas de scraping (precios, disponibilidad de una web, etc.)
- 24/7 real en la nube si en algún momento querés cargar una tarjeta (Fly.io) o migrar a un webhook serverless sin tarjeta (Cloudflare Workers)
