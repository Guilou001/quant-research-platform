# ADR-016 : une spécification écrite avant le code pour l'infrastructure, la configuration avant le résultat pour la recherche

**Statut** : acceptée le 2026-09-03, après l'audit des phases 9 et 11.

## Contexte

L'audit du 2026-09-03, huit angles de revue sur les trois derniers commits,
a rendu quarante constats. Les quatre plus lourds n'étaient pas des fautes de
frappe mais des décisions de conception prises en écrivant le code. La série
de référence LEAN recopiait le passage aux mois de l'étude 001 au lieu de
l'appeler. L'algorithme de contrôle recopiait à la main l'univers et les
paramètres. La convention d'ouverture synthétique rendait le contrôle
d'exécution inopérant. L'étude 014 recopiait huit dates que les études
portaient déjà sous quatre noms différents, et l'une des copies divergeait.
Chacune aurait été visible dans une page de spécification d'une demi-heure,
lue avant la première ligne.

Spec Kit, l'outil de GitHub pour le développement piloté par spécification, a
été installé dans un dossier d'essai le 2026-09-03 pour voir ce qu'il pose.
Il pose dix compétences d'agent, un dossier `.specify/` de vingt-huit
fichiers, et des gabarits en anglais organisés en récits d'utilisateur,
critères d'acceptation, plan et tâches, dans un flux par branche de
fonctionnalité. Sa constitution, les
principes non négociables du projet, est ce que `CLAUDE.md` porte déjà sous
la forme de quinze règles.

## Décision

Deux régimes, selon ce qu'on écrit.

**La recherche est déjà pilotée par spécification.** Le `config.yaml` d'une
étude est sa spécification : l'hypothèse falsifiable, les données, les seuils
du verdict, tous écrits avant le premier chiffre, et le moteur de verdict est
son test d'acceptation. Rien ne change, et Spec Kit n'apporte rien ici, ses
récits d'utilisateur ne décrivant pas une hypothèse.

**L'infrastructure reçoit une spécification avant le code.** Tout module,
fournisseur, moteur ou pont dont l'écriture dépasse une journée commence par
une page dans `docs/specs/`, sur le gabarit `docs/specs/TEMPLATE.md`. La page
dit ce que la chose doit faire en une phrase et ce qu'elle réutilise du
dépôt. Elle porte les critères d'acceptation mesurables, les décisions de
conception, le plan en étapes vérifiables, et ce qui est hors périmètre. La page se relit contre les quinze
règles avant d'écrire, et la revue de code la relit après. Le gabarit reprend
de Spec Kit les critères d'acceptation et la séparation entre le quoi, le
comment et les tâches ; il laisse les récits d'utilisateur, les branches et
l'outillage.

## Conséquences

Une demi-heure de plus au début de chaque chantier d'infrastructure, contre
les quatre constats de conception de l'audit. La première page écrite est
`docs/specs/001-univers-sans-biais-de-survie.md`, le premier chantier de la
feuille de route.

Le dépôt n'installe pas Spec Kit : ses dix compétences et son dossier
`.specify/` sont un outillage d'agent, non un livrable, et ses gabarits sont
en anglais quand tout le dépôt est en français. Si un jour le projet a
plusieurs contributeurs et des branches de fonctionnalité, la décision se
rediscute.

## Options écartées

**Installer Spec Kit tel quel.** Rejeté : mesuré, il pose vingt-huit fichiers
et dix compétences pour un flux par branche que le dépôt n'a pas, et sa
constitution ferait double emploi avec `CLAUDE.md`.

**Le développement piloté par les tests seul.** Il est déjà la règle 10, et
il n'aurait pas attrapé les quatre constats : un test vérifie que le code fait
ce qu'on lui a dit, pas qu'on a dit la bonne chose.

**Ne rien changer.** Rejeté par la mesure citée en contexte.
