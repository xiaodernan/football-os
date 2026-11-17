---
id: comment-le-coach-repond-fr
locale: fr
title: "Comment le coach répond — du score au paragraphe, sans jamais inventer"
category: coaching
tags: [coach, ai, stategraph, réponse, algorithme, how-it-works]
applies_to: [all]
difficulty: intermediate
source: "FOOTBALL OS original editorial in French — the six nodes of CoachGraphState as this project runs them"
confidence: high
last_reviewed: 2026-11-17
---

## Le coach n'est pas un chat — c'est un graphe à états

Depuis toujours, la tentation est de laisser un grand modèle écrire ce qu'il veut à la place des chiffres. Dans ce produit, le coach ne fait pas ça. Chaque question que tu lui poses traverse six étapes, toujours dans cet ordre, toujours bornées par un nombre maximal de visites : `classify_intent → build_arithmetic → spend_gate → phrase_answer → persist_answer → END`.

Ce rituel n'est pas décoratif. C'est lui qui fait que chaque réponse du coach peut dire exactement ce qu'elle contient — et surtout ce qu'elle ne contient pas.

## Les six nœuds, un par un

**1. classify_intent — à quoi tu penses ?**
Le coach lit ta question avec un moteur de règles, pas avec le modèle. Il range ce que tu dis dans une intention connue : l'entraînement du jour, un plan 7/30/90 jours, le pied faible, ton taux de pertes de balle. Ce triage est une décision de code, pas une inférence.

**2. build_arithmetic — le calcul d'abord.**
Les chiffres viennent de tes données : ton profil, ta notation pied faible, tes dernières séances terminées. Le coach sélectionne l'exercice ou construit le plan, mais le travail reste strictement celui du moteur arithmétique et statistique, jamais du modèle.

**3. spend_gate — on peut tourner le modèle maintenant ?**
Même le meilleur modèle se tait si le budget du jour est épuisé. Ce portail le décide. Si tu t'es déjà fait répondre trente fois dans la journée, ta question repart sur le moteur de règles et le modèle ne dira pas un mot — même si ta question est magnifique.

**4. phrase_answer — le modèle, sur une seule tâche.**
Quand le portail est ouvert, le modèle reçoit les seules figures depuis lesquelles il parle : l'exercice, la raison, la confiance, la formule de la table stockée. Il écrit un paragraphe, une seule phrase, jamais de leçon de vie. Et s'il refuse parce que ses propres limites sont franchies, l'answer le dit honnêtement.

**5. persist_answer — la mémoire avant la fin.**
La question, la réponse, les raisons, le niveau de confiance — tout cela atterrit dans ton carnet d'entraînement. Tu retrouves toujours ce que ton coach t'a dit la dernière fois. Il ne peut pas te programmer une deuxième séance identique parce qu'il ne se souvient pas ; il se souvient.

**6. END — le graphe s'arrête.**
Il n'y a pas d'itération sans fin : le graphe est acyclique par construction, et le moteur refuse toute marche au-delà de six pas. C'est la plus grande différence entre un flux conversationnel gratuit et un système qui sait ce qu'il fait.

## Pourquoi c'est différent de ChatGPT

Quand tu demandes à un modèle libre pourquoi tu rates tes contrôles, tu obtiens une réponse plausible. Quand tu demandes à ce coach-là, tu obtiens la même réponse — mais derrière, chaque seconde est balisée : tu sais d'où vient chaque figure, pourquoi cette recommandation plutôt qu'une autre, et que si le modèle s'est tu, c'est précisément au nœud `spend_gate` que ça c'est passé.

Ce n'est pas du marketing. C'est un constat d'architecture.

## Quand il ne répond pas

Il arrive que le coach te réponde « je n'ai pas ce qu'il faut ». Ce n'est pas un défaut, c'est le contrat : s'il n'a pas suffisamment de données sur toi, ou si le budget du jour est clos, il refuse plutôt que d'improviser. Un coach qui refuse proprement vaut mieux qu'un coach qui invente.

## Comment le lire sur ton écran

Chaque réponse affiche : l'intention reconnue, le niveau de confiance, la raison ligne à ligne, la provider et le modèle, et la part de la réponse qui est venue directement du cache. Les chips du lexique `graph_trace` te montrent exactement les nœuds que la machine a traversés.

Bref : dans ce produit, ton coach est une machine qui n'improvise pas. Il veut que tu progresses, pas qu'il soit créatif.
