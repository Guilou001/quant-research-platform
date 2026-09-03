# Sécurité

Le dépôt ne gère ni compte, ni paiement, ni donnée personnelle. Les seules
informations sensibles sont les clés de fournisseurs de données, qui vivent
dans un fichier `.env` jamais commité, et l'en-tête d'identification que la SEC
exige. Le fichier `.env.example` montre la forme attendue sans aucune valeur.

Si vous trouvez une clé, un jeton ou un courriel personnel dans l'historique
du dépôt, ou une faille dans la façon dont le code lit une source distante,
écrivez à l'adresse indiquée sur le profil GitHub de l'auteur plutôt que
d'ouvrir un ticket public. Une réponse arrive sous sept jours.

Les dépendances sont épinglées dans `uv.lock`, et la CI les réinstalle à chaque
exécution depuis ce fichier.
