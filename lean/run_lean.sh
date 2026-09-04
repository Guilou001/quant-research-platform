#!/usr/bin/env sh
# Phase 9 : lance l'algorithme de contrôle dans l'image officielle de LEAN.
#
# Usage : sh lean/run_lean.sh [delai_en_seances] [jeu]
#   delai : 0 (défaut) ordres passés sur la barre de fin de mois, 1 une séance plus tard.
#   jeu   : lean (défaut), l'ouverture du jour est la clôture de la veille ;
#           lean_realopen, l'ouverture réelle de Yahoo, ajustée comme la clôture.
#
# Aucune inscription chez QuantConnect n'est nécessaire : l'image publique
# quantconnect/lean suffit, et lean-cli n'est pas employé parce que son
# initialisation exige un identifiant et un jeton d'API. L'image est épinglée
# par son empreinte, celle qui a produit les chiffres publiés le 2026-09-03.
set -eu

DELAI="${1:-0}"
JEU="${2:-lean}"
ICI="$(cd "$(dirname "$0")" && pwd)"
DONNEES="$ICI/data/$JEU"
if [ "$JEU" = "lean" ]; then
  RESULTATS="$ICI/data/results_delai_$DELAI"
else
  RESULTATS="$ICI/data/results_${JEU#lean_}_delai_$DELAI"
fi
IMAGE="quantconnect/lean@sha256:3168a6880479c88d3054b20acf9716db2bf01582b9e5434812705666b25768e3"

if [ ! -f "$DONNEES/custom/params.json" ]; then
  echo "jeu de données absent : $DONNEES. Lancer d'abord : uv run python lean/export_inputs.py" >&2
  exit 1
fi

# Les deux bases de référence de LEAN (heures de marché, propriétés des
# symboles) viennent de l'image elle-même, copiées une fois, chacune vérifiée.
if [ ! -d "$DONNEES/market-hours" ] || [ ! -d "$DONNEES/symbol-properties" ]; then
  mkdir -p "$DONNEES"
  CONTENEUR="$(docker create "$IMAGE")"
  [ -d "$DONNEES/market-hours" ] || docker cp "$CONTENEUR:/Lean/Data/market-hours" "$DONNEES/market-hours"
  [ -d "$DONNEES/symbol-properties" ] || docker cp "$CONTENEUR:/Lean/Data/symbol-properties" "$DONNEES/symbol-properties"
  docker rm "$CONTENEUR" > /dev/null
fi

rm -rf "$RESULTATS"
mkdir -p "$RESULTATS"

docker run --rm \
  -e "TSMOM_DELAY_DAYS=$DELAI" \
  -v "$ICI/algorithm:/Algorithm:ro" \
  -v "$DONNEES:/Data" \
  -v "$RESULTATS:/Results" \
  "$IMAGE" \
  --algorithm-type-name TsmomControl \
  --algorithm-language Python \
  --algorithm-location /Algorithm/main.py \
  --data-folder /Data \
  --results-destination-folder /Results \
  --environment backtesting

echo "résultats dans $RESULTATS"
