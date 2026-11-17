---
id: how-to-read-the-honours-spine-fr
locale: fr
title: "Comment lire le palmarès — vingt-quatre vrais tournois, une seule épine"
category: history
tags: [palmarès, roll-of-honours, coupe-du-monde, euro, records, how-to-read]
applies_to: [all]
difficulty: intermediate
source: "FOOTBALL OS original editorial in French — figures recomputed from the committed openfootball snapshots (CC-BY 4.0)"
confidence: high
last_reviewed: 2026-11-17
---

## Ce qu'est le palmarès

Le palmarès de ce produit tient en une table de vingt-quatre lignes : les vingt-deux Coupes du monde que ce produit porte (1930 en Uruguay jusqu'en 2022 au Qatar) plus les deux Championnats d'Europe (l'Euro 2021 — le tournoi 2020 disputé en 2021 — et l'Euro 2024 en Allemagne). Cela fait 1 066 matchs et 2 979 buts comptés sur le terrain. Aucun rang synthétique n'y figure. Chaque chiffre est recalculé à partir des instantanés openfootball soumis au commit, à chaque ouverture de la porte : vous ne lisez jamais la copie d'une fiche déposée, mais l'arithmétique des fichiers eux-mêmes.

Un détail de structure compte avant toute lecture : le champ `kind` distingue une ligne `worldcup` d'une ligne `euro`. Le registre des champions les compte ensemble, mais la question « de combien France dispose-t-elle ? » appelle une réponse précise — deux titres, tous deux en Coupe du monde (1998 à domicile et 2018 en Russie), sans compter ses parcours dans les euro. L'Italie en détient cinq : quatre en Coupe du monde (1934, 1938, 1982, 2006) et un à l'Euro 2021. Le Brésil en détient cinq, tous en Coupe du monde : 1958, 1962, 1970, 1994, 2002. L'Argentine en détient trois : 1978, 1986, 2022. L'Allemagne de l'Ouest en détient trois : 1954, 1974, 1990 — comptés séparément de l'Allemagne unifiée de 2014, parce que les instantanés désignent la fédération telle qu'elle était au coup de sifflet final, et l'uniformisation serait plus soignée sans être plus vraie. L'Espagne, deux : 2010 et l'Euro 2024. L'Uruguay, deux : 1930 et 1950. L'Angleterre, un : 1966.

## Comment la finale est imprimée

Chaque ligne imprime trois scores, toujours dans le même ordre : temps réglementaire, prolongations si elles ont été jouées, tirs au but si des pénalités ont tranché. Une finale qui est allée de la première à la dernière minute se lit comme celle de 2022 : 2-2 après quatre-vingt-dix minutes, 3-3 après prolongation, 4-2 aux tirs au but — vous distinguez d'un coup d'œil un titre gagné sur le terrain d'un titre gagné au point de penalty. `went_extra_time` est sa propre colonne. Les buts ne sont comptés que sur le terrain ; un titre aux tirs au but n'ajoute rien au total des buts.

## Deux finales à connaître avant d'aller plus loin

1950, le Maracanazo. Le Brésil était hôte, l'Uruguay a gagné 2 à 1 dans la finale de groupe de classement au Maracanã — la fin la plus radicale que le palmarès contienne : la nuit où la ville entière attendait la fête, le favori de la maison rapatrie ses espérances.

1954, le Miracle de Berne. Sur le papier, la Hongrie était plus forte ; l'Allemagne de l'Ouest a gagné la finale 3 à 2 à Berne. Les registres impriment cette finale comme toute autre, avec la même mise en page à trois scores : lisez les champs, pas la légende.

## Comment la porte de recherche répond

La porte de recherche (`/world/real-book/search`) est une sous-chaîne insensible à la casse sur les propres chiffres de l'épine : année du tournoi, hôte, champion, finaliste, stade, et les équipes du match à la marge la plus large. Tapez `Germany` et la porte répond à partir de dix lignes (2014 l'Allemagne ; 1954, 1974, 1990 l'Allemagne de l'Ouest ; l'hôte de 2018 ; l'hôte de l'Euro 2024 et d'autres lignes où le mot figure). Un champ vide rend les vingt-quatre — c'est délibéré, pour que la visite blanche ne soit pas un voyage perdu. `q=Allemagne` répond zéro : l'épine est en chiffres anglais, c'est le dessein, et un résultat honnêtement vide vaut mieux que trois colonnes de doublons.

## Ce que l'épine ne contient pas

Ni buteurs, ni passeurs, ni affluence, ni avertissements, ni VAR, ni météo. L'épine n'a volontairement qu'une seule forme : le tournoi, l'hôte, la finale, les buts, la plus large victoire, le registre des champions. Ce qui excède cette forme relève des volumes des tournois eux-mêmes — et de la presse de football. Si vous cherchez le nombre de buts d'un joueur dans le palmarès, vous êtes monté dans la mauvaise voiture ; si vous voulez seulement savoir si un titre a été tranché sur le terrain ou aux tirs au but, vous êtes exactement chez vous.

## Provenance, dit simplement

Source : les `worldcup.json` et `euro.json` d'openfootball (CC-BY 4.0). Les données sont publiques et réelles ; la provenance est estampillée à chaque réponse : `data_origin: public-real`, `is_demo_data: false`. Le monde synthétique de ce produit n'apparaît jamais dans ce palmarès, par construction. Et lorsque les instantanés seront resynchronisés depuis l'amont, chaque chiffre ci-dessus sera re-dérivé des mêmes octets.
