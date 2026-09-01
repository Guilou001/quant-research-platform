"""Les tests anti-biais : ceux qui protègent les résultats, pas le code.

Un test unitaire ordinaire vérifie qu'une fonction rend le bon nombre. Ces
tests-ci vérifient qu'aucune information future n'entre dans un calcul, ce qui
est une propriété du pipeline entier et non d'une fonction. Ils ne se
désactivent pas.
"""
