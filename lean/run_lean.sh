#!/usr/bin/env sh
# Phase 9 : lance l'algorithme de contrôle dans l'image officielle de LEAN.
#
# Usage : sh lean/run_lean.sh [delai_en_seances]
#   0 (défaut) : les ordres sont passés sur la barre de fin de mois ;
#   1          : ils sont passés une séance plus tard.
#
# Aucune inscription chez QuantConnect n'est nécessaire : l'image publique
# quantconnect/lean suffit, et lean-cli n'est pas employé parce que son
# initialisation exige un identifiant et un jeton d'API.
set -eu

DELAI="${1:-0}"
ICI="$(cd "$(dirname "$0")" && pwd)"
DONNEES="$ICI/data/lean"
RESULTATS="$ICI/data/results_delai_$DELAI"
IMAGE="quantconnect/lean:latest"

# Les deux bases de référence de LEAN (heures de marché, propriétés des
# symboles) viennent de l'image elle-même, copiées une fois.
if [ ! -d "$DONNEES/market-hours" ]; then
  CONTENEUR="$(docker create "$IMAGE")"
  docker cp "$CONTENEUR:/Lean/Data/market-hours" "$DONNEES/market-hours"
  docker cp "$CONTENEUR:/Lean/Data/symbol-properties" "$DONNEES/symbol-properties"
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
