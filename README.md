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

## Próximos pasos posibles

- Alertas de scraping (precios, disponibilidad de una web, etc.)
- Recordatorios recurrentes (todos los días a tal hora)
- 24/7 real en la nube si en algún momento querés cargar una tarjeta (Fly.io) o migrar a un webhook serverless sin tarjeta (Cloudflare Workers)
