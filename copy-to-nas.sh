#!/bin/bash
NAS=/Volumes/docker/studio-orlandi/frontend
SRC=/Users/francorlandi/studio-orlandi/frontend

cp "$SRC/index.html"                    "$NAS/index.html"
cp "$SRC/assets/style.css"              "$NAS/assets/style.css"
cp "$SRC/medico/home.html"              "$NAS/medico/home.html"
cp "$SRC/medico/anagrafica.html"        "$NAS/medico/anagrafica.html"
cp "$SRC/medico/calendario.html"        "$NAS/medico/calendario.html"
cp "$SRC/medico/impostazioni.html"      "$NAS/medico/impostazioni.html"
cp "$SRC/medico/login.html"             "$NAS/medico/login.html"
cp "$SRC/paziente/prenota.html"         "$NAS/paziente/prenota.html"

echo "✓ Tutti i file frontend copiati sul NAS"
