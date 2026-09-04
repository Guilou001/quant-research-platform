# Spécification 006 : lire les jeux de données 13F de la SEC, positions des gestionnaires, trimestre par trimestre

**Statut** : acceptée le 2026-09-04 ; amendée le même jour, voir la fin.
**Règles concernées** : 1, 4, 5, 13.

## Ce que cela doit faire

Chaque trimestre, tout gestionnaire américain qui gère plus de cent millions
de dollars déclare ses positions à la SEC dans un formulaire 13F, dans les
quarante-cinq jours. La SEC publie depuis 2013 ces déclarations en jeux de données structurés,
un fichier compressé par trimestre. Mesuré le 2026-09-04 : 53 fichiers, 73 Mo
pour celui du quatrième trimestre 2023, dont une table de positions de 294 Mo.
Cette table porte le CUSIP, le FIGI, la valeur et le nombre de titres de
chaque ligne. Le laboratoire doit les lire avec la date de dépôt,
qui est la seule date à laquelle une position est connaissable, règle 1.

En mots simples : la liste de ce que chaque grand gestionnaire détenait, telle
qu'il l'a déclarée et le jour où il l'a déclarée.

## Ce que le dépôt porte déjà, et qui sera appelé plutôt que recopié

`BaseProvider` et son cache brut, qui gardent le fichier compressé tel quel ;
le référentiel Polygon, dont le `composite_figi` relie un FIGI à un symbole,
radié ou non ; `quantlab.data.providers.yahoo` pour les prix des survivants.

## Les critères d'acceptation, mesurables

1. Le fichier du quatrième trimestre 2023 rend trois tables. Les dépôts, avec
l'accession, le CIK, la date de dépôt et la période. La couverture, avec le
nom du gestionnaire. Les positions, avec le CUSIP, le FIGI, la valeur et les
titres. Testé sur un extrait écrit à la main.
2. La date de dépôt d'une position est postérieure ou égale à la fin de sa
   période, vérifié sur toutes les lignes lues, et une violation lève.
3. Le manifeste porte `point_in_time` à vrai, avec la date de dépôt comme
   date de disponibilité.
4. `make test` ne fait aucun appel réseau.

## Les décisions de conception, et ce qu'elles écartent

Les jeux structurés de la SEC plutôt que les dépôts XML un par un : un
fichier par trimestre au lieu de dizaines de milliers. Le FIGI de la SEC
plutôt qu'une correspondance CUSIP maison quand il est présent, et OpenFIGI
pour les trimestres qui ne le portent pas, en lots de dix, la limite sans clé.
La valeur est ramenée en dollars déclaration par déclaration, voir l'amendement.

## Le plan, en étapes vérifiables

1. Le fournisseur et ses analyseurs.
2. L'étude 020 : les plus grosses positions des gestionnaires concentrés,
   tenues d'un dépôt au suivant, contre le marché, avec le décompte des
   positions dont le prix manque, qui borne le biais de survie.

## Hors périmètre

Les formulaires 4 des initiés et la dérive après annonce de résultats, qui
sont deux autres sources de la SEC et deux autres spécifications.

## Amendement du 2026-09-04 : la valeur n'est pas en dollars

La première version écrivait « la valeur est en dollars entiers, comme la
SEC la publie ». Mesuré sur la première lecture de l'étude 020. La colonne
est en milliers de dollars dans 97 % des déclarations jusqu'en 2021, dans 81 %
en 2022, puis dans 19 % en 2023 et 6 % en 2026. Un déclarant sur mille
déclare cent fois trop. Le fournisseur lit donc l'unité déclaration par
déclaration, par la médiane de la valeur par titre. Il multiplie par mille
sous un dollar, marque suspecte au-delà de cinq mille dollars, et garde le
diagnostic dans une colonne. Critère ajouté, testé sur un extrait écrit à la
main. Une déclaration à 0,15 $ par titre est ramenée à 150 $ ; une à
22 574 $ est marquée sans correction. Vérifié sur Apple à trois trimestres.

