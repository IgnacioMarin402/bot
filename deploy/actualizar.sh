#!/usr/bin/env bash
# Despliegue de cambios nuevos: el "deploy" del día a día.
#
# Flujo completo: programas en Windows -> git push -> ssh al VPS ->
#   ~/graph/deploy/actualizar.sh
#
# Hace: traer el código nuevo, sincronizar dependencias EXACTAS (uv.lock),
# reiniciar el servicio y mostrar que quedó vivo. Si algo falla, el script
# se detiene ahí (set -e) y el servicio anterior sigue corriendo.

set -euo pipefail

cd /home/bots/graph

echo "== 1/4 Trayendo cambios de GitHub =="
git pull

echo "== 2/4 Sincronizando dependencias (uv.lock) =="
"$HOME/.local/bin/uv" sync

echo "== 3/4 Reiniciando el servicio =="
sudo systemctl restart bots

echo "== 4/4 Estado =="
sleep 2
systemctl status bots --no-pager -l | head -12
curl -s http://127.0.0.1:8000/ && echo
echo "Deploy OK ✅"
