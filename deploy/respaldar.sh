#!/usr/bin/env bash
# Respaldo diario de las bases SQLite de los bots.
#
# Uso manual:   ~/graph/deploy/respaldar.sh
# Uso por cron: ver deploy/GUIA.md, Fase 10 (corre a las 03:30 cada día).
#
# Detalle importante: NO se copia el archivo a lo bruto (cp) porque con el
# modo WAL de SQLite podrías copiar un estado a medio escribir. Se usa la
# API .backup de SQLite (vía Python, que ya está instalado con uv), que
# hace una copia consistente aunque el bot esté escribiendo en ese momento.

set -euo pipefail

PROYECTO="/home/bots/graph"
DESTINO="/home/bots/backups"
FECHA=$(date +%F_%H%M)
DIAS_A_CONSERVAR=14

mkdir -p "$DESTINO"

for db in memoria.sqlite memoria_julieta.sqlite datos_julieta.sqlite; do
    if [ -f "$PROYECTO/$db" ]; then
        "$HOME/.local/bin/uv" run --project "$PROYECTO" python -c "
import sqlite3
origen = sqlite3.connect('$PROYECTO/$db')
destino = sqlite3.connect('$DESTINO/${FECHA}_$db')
origen.backup(destino)
destino.close(); origen.close()
print('respaldado: ${FECHA}_$db')
"
    fi
done

# Borrar respaldos con más de N días (mantiene la carpeta a raya).
find "$DESTINO" -name "*.sqlite" -mtime +$DIAS_A_CONSERVAR -delete

echo "[$(date)] respaldo OK"
