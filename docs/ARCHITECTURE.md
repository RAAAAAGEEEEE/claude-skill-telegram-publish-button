# Architecture

Voir aussi : [CONFIGURATION.md](CONFIGURATION.md), [PRIVACY_AND_SECURITY.md](PRIVACY_AND_SECURITY.md).

## Vue d'ensemble

```text
 posts.txt + suivi.json ──envoyer──▶ Telegram : sujet du projet, message + bouton
                                              │ toucher
                                              ▼
                     serve (getUpdates, callback_query seulement)
                                              │ contrôles
                                              ▼
                               X : POST /2/tweets ──▶ lien renvoyé dans le sujet
```

Un seul fichier, `scripts/publish_button.py`, bibliothèque standard seulement. Le même script envoie les messages (commandes ponctuelles) et attend les touchers (commande `serve`, un processus permanent).

## Projets

Un projet = un slug, un nom, un compte X, un dossier de posts (`projets.json`) et un sujet du groupe (`sujets.json`). `choisir(slug)` fait pointer les chemins du module (secrets, état, dossier de posts) vers ce projet. Le service `serve` sert tous les projets : il choisit le projet d'après le bouton touché.

## Le bouton

Les données du bouton (`callback_data`, 64 octets au plus selon l'API Telegram) ont la forme :

```text
pub:<projet>:<id>:<empreinte>
```

L'empreinte est un SHA-256 tronqué à 12 caractères hexadécimaux, calculé sur le texte, le nom du visuel et le contenu du fichier visuel.

## Contrôles au toucher

Dans l'ordre, avant tout appel à X :

1. l'expéditeur est dans `autorises` et le message est dans le groupe configuré ;
2. les données du bouton ont la bonne forme et le projet existe ;
3. le message est dans le sujet de ce projet ;
4. le post existe, n'est pas bloqué, tient en 280 caractères (comptés comme X : 2 pour un emoji) et ne contient pas de lien si `refuser_liens` est vrai ;
5. l'empreinte correspond au post actuel et le texte du post figure dans le message touché ;
6. le compte X autorisé est bien celui du projet ;
7. sous verrou de fichier : le post n'est ni publié ni en cours, la pause depuis la dernière publication est respectée, le solde estimé reste au-dessus du seuil, et le post parent est publié s'il s'agit d'une réponse. Le post passe alors à `en_cours`.

## Publication

`publier()` est la seule fonction qui écrit sur X. Elle téléverse le visuel (image en un appel, GIF en trois temps : initialize, append, finalize), pose le texte alternatif sans bloquer en cas d'échec, puis appelle `POST /2/tweets`.

Issue de l'appel :

| Cas | État du post | Suite |
|---|---|---|
| Réponse avec identifiant | `publie` | bouton remplacé par le lien, solde décompté |
| Refus net de X (code 4xx) sur `POST /2/tweets` | `echec` | rien n'est publié, nouveau toucher possible |
| Délai, coupure, code 5xx ou réponse sans identifiant sur `POST /2/tweets` | `incertain` | solde décompté par prudence ; le post est peut-être parti : tout nouveau toucher est refusé jusqu'à `resoudre` |
| Toute erreur avant `POST /2/tweets` (jeton, téléversement du visuel) | `echec` | rien n'est publié, nouveau toucher possible |

L'état `incertain` évite le double post : sans réponse de X, le script ne peut pas savoir si le post existe. Un post resté `en_cours` (service arrêté en pleine publication) est traité de la même façon.

## Jetons X

OAuth 2.0 avec PKCE (code d'autorisation et vérificateur aléatoire), client confidentiel. X n'accepte le code d'autorisation que 30 secondes : `auth-url --ecoute` ouvre un petit serveur HTTP sur `127.0.0.1:8765` qui reçoit la redirection et fait l'échange aussitôt. Le jeton d'accès dure deux heures ; il est rafraîchi sous verrou dix minutes avant expiration. X change le jeton de rafraîchissement à chaque usage : le nouveau est écrit tout de suite, de façon atomique, avec l'ancienne version en `.prev`.

## Service

`serve` lit `getUpdates` avec `allowed_updates=["callback_query"]` : il ne reçoit aucun message texte. Au démarrage, il écarte les touchers faits pendant un arrêt, pour qu'un post ne parte pas des heures après le geste. Une erreur 409 signale qu'un autre programme lit le même bot ; le service attend alors 60 secondes et réessaie.

## Fichiers et concurrence

Les écritures de fichiers JSON sont atomiques (fichier temporaire, `fsync`, renommage). Les modifications d'état passent par des verrous `fcntl` (`etat.lock`, `jetons.lock`, `suivi.lock`, `.sujets.lock`, `.projets.lock`), ce qui permet de lancer `envoyer` pendant que `serve` tourne.
