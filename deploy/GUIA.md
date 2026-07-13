# 🚀 Guía de despliegue en Hetzner (paso a paso, desde cero)

> ⚠️ **NOTA HISTÓRICA (2026-07-13):** el dueño finalmente desplegó en
> **Fly.io** (app `bot-chuleta`, ver `fly.toml` y `Dockerfile` en la raíz).
> Esta guía queda como referencia por si algún día se migra a un VPS
> clásico. Lo VIGENTE para Fly está en fly.toml (incluida la sección de
> persistencia con volumen — CRÍTICA) y en memory/decisiones.md.

> Para quien nunca montó un VPS. Tiempo estimado: 1-2 horas la primera vez.
> Decisión de diseño: **sin Docker** — systemd + uv + Caddy (ver
> memory/decisiones.md). La reproducibilidad la da `uv.lock`.

## Qué vamos a montar

```
WhatsApp → Twilio → https://TU-DOMINIO.duckdns.org  (URL FIJA, chao ngrok)
                          │
                    [Caddy] puerto 443, HTTPS automático con Let's Encrypt
                          │ reverse proxy
                    [uvicorn] 127.0.0.1:8000 ← systemd lo mantiene vivo
                          │
                    tu app (Alejandro /whatsapp + Julieta /julieta)
                          │
                    *.sqlite en el disco del VPS (+ backup diario por cron)
```

**Convenciones de esta guía** (cámbialas si quieres, pero sé consistente):
- Usuario del servidor: `bots`
- Carpeta del proyecto: `/home/bots/graph`
- Dominio: `TU-DOMINIO.duckdns.org` (reemplázalo por el tuyo en TODOS los pasos)

---

## Fase 1 — Preparación local (en tu PC, antes de pagar nada)

### 1.1 Sube el repo a GitHub (privado)

El servidor necesita de dónde clonar. En github.com crea un repo **privado**
(ej. `graph`) y desde tu carpeta del proyecto:

```powershell
git remote add origin https://github.com/TU-USUARIO/graph.git
git add -A
git commit -m "preparar despliegue"
git push -u origin main
```

(El `.gitignore` ya protege `.env` y los `.sqlite` — no viajan a GitHub.)

### 1.2 Genera tu llave SSH (si no tienes)

En PowerShell:

```powershell
ssh-keygen -t ed25519
# Enter a todo (sin passphrase está OK para empezar)
Get-Content ~\.ssh\id_ed25519.pub
```

Copia esa línea que empieza con `ssh-ed25519` — la necesitas en la Fase 2.
Es tu "llave pública": se la das a Hetzner para entrar sin contraseña.

---

## Fase 2 — Crear el servidor en Hetzner

1. Cuenta en https://www.hetzner.com → **Cloud** (console.hetzner.cloud).
   (Puede pedir verificación de identidad la primera vez; es normal.)
2. Crea un proyecto (ej. "bots") → **Add Server**:
   - **Location**: `Ashburn, VA (us-east)` ← el más cercano a Chile (menor latencia).
   - **Image**: Ubuntu 24.04.
   - **Type**: el compartido más barato disponible (CPX11 o CX22, ~€4-5/mes).
     Para 2 bots de WhatsApp sobra por kilómetros.
   - **Networking**: deja IPv4 + IPv6.
   - **SSH keys** → Add SSH key → pega tu llave pública de la Fase 1.2.
   - Create & Buy now.
3. Anota la **IP pública** del servidor (ej. `5.161.x.x`).

---

## Fase 3 — Dominio gratis (DuckDNS)

Los webhooks exigen HTTPS con certificado válido, y para eso hace falta dominio.

1. https://www.duckdns.org → entra con GitHub/Google.
2. Crea un subdominio (ej. `julieta-bots`) → te queda `julieta-bots.duckdns.org`.
3. En el campo **current ip** pon la IP de tu VPS → **update ip**.

(La IP del VPS es fija, así que esto se configura UNA vez y listo.)

---

## Fase 4 — Primera conexión y usuario

```powershell
ssh root@LA-IP-DE-TU-VPS
```

(Escribe `yes` cuando pregunte por el fingerprint — solo la primera vez.)

Ya adentro, crea el usuario de trabajo y pásale tu llave:

```bash
adduser bots --disabled-password --gecos ""
usermod -aG sudo bots
echo "bots ALL=(ALL) NOPASSWD:ALL" > /etc/sudoers.d/bots
rsync --archive --chown=bots:bots ~/.ssh /home/bots
exit
```

Desde ahora entras como: `ssh bots@LA-IP` (y ya no usas root).

---

## Fase 5 — Instalar herramientas (una sola vez)

Conectado como `bots`:

```bash
# Básicos + firewall
sudo apt update && sudo apt upgrade -y
sudo apt install -y git ufw
sudo ufw allow OpenSSH
sudo ufw allow 80
sudo ufw allow 443
sudo ufw --force enable

# uv (mismo gestor que usas en Windows)
curl -LsSf https://astral.sh/uv/install.sh | sh
source ~/.bashrc    # para que 'uv' quede en el PATH

# Caddy (repo oficial — el reverse proxy con HTTPS automático)
sudo apt install -y debian-keyring debian-archive-keyring apt-transport-https curl
curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/gpg.key' | sudo gpg --dearmor -o /usr/share/keyrings/caddy-stable-archive-keyring.gpg
curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/debian.deb.txt' | sudo tee /etc/apt/sources.list.d/caddy-stable.list
sudo apt update && sudo apt install -y caddy
```

---

## Fase 6 — El proyecto

```bash
cd ~
git clone https://github.com/TU-USUARIO/graph.git
# (repo privado: GitHub te pedirá usuario + un Personal Access Token como contraseña.
#  Se crea en github.com → Settings → Developer settings → Tokens (classic) → repo)
cd graph
uv sync
```

Crea el `.env` del servidor (los secretos NUNCA viajan por git):

```bash
nano .env
```

Contenido (ajusta a tu configuración real):

```
LLM_PROVIDER=gemini
GOOGLE_API_KEY=tu-key
TWILIO_ACCOUNT_SID=tu-sid
TWILIO_AUTH_TOKEN=tu-token
```

Guarda (Ctrl+O, Enter, Ctrl+X) y protégelo:

```bash
chmod 600 .env
```

**Prueba manual** (la primera vez, para ver que todo vive):

```bash
uv run uvicorn interfaces.whatsapp:app --host 127.0.0.1 --port 8000
# En OTRA terminal ssh:  curl http://127.0.0.1:8000/
# Debe responder: {"ok":true,"bots":[...]}
# Ctrl+C para pararlo — systemd lo manejará desde ahora
```

---

## Fase 7 — systemd (el proceso queda vivo para siempre)

```bash
sudo cp ~/graph/deploy/bots.service /etc/systemd/system/bots.service
sudo systemctl daemon-reload
sudo systemctl enable --now bots
sudo systemctl status bots        # debe decir "active (running)"
```

Ver logs en vivo (el equivalente a la consola de uvicorn):

```bash
journalctl -u bots -f
```

systemd reinicia el proceso si crashea y lo arranca al bootear el VPS.

---

## Fase 8 — Caddy (HTTPS automático)

```bash
sudo cp ~/graph/deploy/Caddyfile /etc/caddy/Caddyfile
sudo nano /etc/caddy/Caddyfile    # reemplaza TU-DOMINIO.duckdns.org por el tuyo
sudo systemctl reload caddy
```

Caddy pide el certificado a Let's Encrypt solo (tarda ~30 segundos la
primera vez). Prueba desde tu navegador en Windows:

```
https://TU-DOMINIO.duckdns.org/
```

Debe responder el JSON de salud. **Ya tienes URL fija con HTTPS.** 🎉

---

## Fase 9 — Apuntar Twilio a la URL fija

En Twilio, webhook "A message comes in" (POST) de cada número:

- Número de Alejandro → `https://TU-DOMINIO.duckdns.org/whatsapp`
- Número de Julieta   → `https://TU-DOMINIO.duckdns.org/julieta`

Se configura UNA vez — se acabó el ritual de ngrok.

---

## Fase 10 — Backups (antes de que haya datos reales)

```bash
chmod +x ~/graph/deploy/respaldar.sh
crontab -e     # elige nano si pregunta
```

Agrega esta línea al final (backup diario a las 03:30):

```
30 3 * * * /home/bots/graph/deploy/respaldar.sh >> /home/bots/backups/respaldos.log 2>&1
```

Guarda copias fechadas de los 3 `.sqlite` en `~/backups/` y borra las de
más de 14 días. Para restaurar: parar el servicio, copiar el archivo de
vuelta, arrancar.

---

## Operación del día a día

| Quiero... | Comando (conectado por ssh) |
|---|---|
| Desplegar cambios nuevos | `~/graph/deploy/actualizar.sh` |
| Ver logs en vivo | `journalctl -u bots -f` |
| Reiniciar el bot | `sudo systemctl restart bots` |
| Ver si está vivo | `systemctl status bots` o `curl localhost:8000/` |
| Exportar Excel de Julieta | `cd ~/graph && uv run poe exportar` (luego `scp` a tu PC) |

Flujo de desarrollo: programas en Windows → `git push` → entras por ssh →
`~/graph/deploy/actualizar.sh` (hace pull + sync + restart).

---

## ⚠️ Pendientes de seguridad ANTES de uso real con clientes

1. **Validar `X-Twilio-Signature`** en el webhook (está en memory/roadmap.md).
   Con URL fija y pública es la única barrera contra requests falsos que
   quemen tu cuota o ensucien la BD de Daniela.
2. Cuando migres a **Meta Cloud API** directo (sin Twilio): es OTRA interfaz
   (`interfaces/meta.py` — JSON distinto + handshake de verificación GET),
   no un cambio de URL. El grafo y las tools no se tocan.
