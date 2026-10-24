# Dépannage

Voir aussi : [USAGE.md](USAGE.md), [CONFIGURATION.md](CONFIGURATION.md).

Dans les solutions, `pb` désigne `python3 scripts/publish_button.py` et `demo` le slug de votre projet.

## Installation

| Message | Cause | Solution |
|---|---|---|
| `jeton du bot absent (TELEGRAM_BOT_TOKEN ou secrets/bot.env)` | Ni variable ni fichier | Remplir `secrets/bot.env` ([INSTALLATION.md](INSTALLATION.md), étape 4) |
| `jeton du bot refusé par Telegram` | Jeton faux ou révoqué | En demander un nouveau à @BotFather (`/token`) |
| `config.json absent ou incomplet (groupe, autorises)` | Étape 5 pas faite | Créer `config.json` avec `groupe` et `autorises` |
| `aucun message recu` (commande `ids`) | Personne n'a écrit depuis l'ajout du bot | Écrire un message dans le groupe, relancer |
| `getUpdates refuse : ... Conflict` (commande `ids`) | `serve` tourne déjà | Arrêter le service le temps de l'installation |
| `groupe a sujets : NON` | Sujets désactivés | Infos du groupe, Modifier, activer Sujets |
| `bot admin, gestion des sujets : NON` | Bot simple membre | Le nommer administrateur avec **Gérer les sujets** |
| `creation du sujet ... refusee` | Même cause que la ligne précédente | Idem |
| `ModuleNotFoundError: No module named 'fcntl'` | Windows | Utiliser Linux, macOS ou WSL |
| `posts.txt et suivi.json ne correspondent pas` | Nombre de textes différent du nombre d'entrées, ou séparateur `---` mal formé | Voir le format dans [USAGE.md](USAGE.md) |

## Autorisation X

| Message | Cause | Solution |
|---|---|---|
| `x_app.json absent` | Fichier de l'app X manquant | Le créer ([INSTALLATION.md](INSTALLATION.md), étape 6) |
| `port 8765 deja pris sur 127.0.0.1 : ...` | Un autre programme écoute sur ce port | Le libérer, ou passer par `auth-url` puis `auth-finish` ([INSTALLATION.md](INSTALLATION.md), étape 7) |
| `aucun retour de X : relancer auth-url --ecoute` | 15 minutes sans retour, ou tunnel SSH absent | Ouvrir le tunnel ([INSTALLATION.md](INSTALLATION.md), étape 7), relancer |
| `autorisation refusee sur X : ...` | **Cancel** cliqué sur X, ou réglages de l'app incomplets | Relancer et cliquer **Authorize app** |
| `state inconnu : relancer auth-url` | Adresse d'une autre tentative, ou nouvel `auth-url` lancé depuis | Relancer `pb --projet demo auth-url --ecoute` |
| `autorisation trop ancienne` | Plus de 15 minutes depuis `auth-url` | Relancer `auth-url` |
| `echange refuse par X (HTTP 400) : ...` | Code collé après 30 secondes, callback différent de `http://127.0.0.1:8765/callback`, ou Client Secret faux | Utiliser `--ecoute` ; vérifier les réglages de l'app X |
| `MAUVAIS COMPTE : ...` | Navigateur connecté à un autre compte X | Se connecter au bon compte, relancer |

## Au toucher du bouton

Les trois premières lignes s'affichent en notification brève ; les autres arrivent en réponse au post, dans le sujet.

| Réponse | Cause | Solution |
|---|---|---|
| `Non autorisé` | Votre identifiant n'est pas dans `autorises`, ou bouton hors du groupe | Ajouter l'identifiant (commande `ids`) |
| `Bouton périmé : renvoie le post` | Ancien format ou projet supprimé | `pb --projet demo envoyer ID --renvoyer` |
| `Bouton hors du sujet du projet` | Message déplacé, ou numéro de sujet changé dans `sujets.json` | Renvoyer le post |
| `post inconnu` | Post retiré de `suivi.json` depuis l'envoi | Rien à faire, ou le remettre |
| `Refusé : fichiers des posts illisibles (...)` | `posts.txt` ou `suivi.json` absent ou mal formé | Corriger les fichiers |
| `Refusé : le post a changé depuis l'envoi de ce message` | Texte ou visuel modifié après l'envoi | `pb --projet demo envoyer ID --renvoyer` |
| `Refusé : X n'est pas encore connecté à @...` | Étape 7 pas faite pour ce projet | `pb --projet demo auth-url --ecoute` |
| `Refusé : solde du crédit X jamais saisi` | `credit-set` jamais lancé | `pb --projet demo credit-set MONTANT` |
| `Refusé : crédit X estimé à ... : arrêt sous ...` | Solde estimé trop bas | Recharger le crédit sur X, puis `credit-set` |
| `Refusé : trop rapproché` | Pause minimale pas écoulée | Attendre le délai indiqué |
| `Refusé : déjà publié : <lien>` | Deuxième toucher | Rien à faire |
| `Refusé : c'est une réponse au post N, qui n'est pas encore publié` | `reply_to` vers un post non publié | Publier d'abord le post N |
| `Refusé : l'identifiant du post parent est inconnu.` | Parent marqué publié sans identifiant de post | `pb --projet demo resoudre N publie TWEET_ID` pour le parent |
| `Refusé : texte trop long` / `contient un lien` | Contrôle du texte | Corriger le post, le renvoyer |
| `Refusé : bloqué : ...` | `bloque` vrai dans `suivi.json` | Retirer `bloque`, renvoyer |
| `X a refusé (HTTP 403) ...` | Doublon, droits de l'app, compte limité | Lire le détail ; rien n'est publié |
| `Connexion à X impossible (...)` | Réseau coupé avant la publication | Retoucher plus tard ; rien n'est publié |
| `Échec avant publication (rafraichissement refuse : refaire l'autorisation)` | Autorisation révoquée sur X, ou réponse de rafraîchissement perdue | Refaire l'étape 7 |
| `Échec avant publication (...)` | Autre erreur avant l'appel de publication (visuel refusé, par exemple) | Lire le détail ; rien n'est publié |
| `Réponse de X perdue : le post est peut-être parti` | Coupure pendant la publication | Regarder le profil X, puis `pb --projet demo resoudre ID libre` (post absent) ou `pb --projet demo resoudre ID publie TWEET_ID` (post présent) |
| `Refusé : état incertain ...` | Suite du cas précédent pas encore tranchée, ou service arrêté en pleine publication | Idem |

## Service

| Journal | Cause | Solution |
|---|---|---|
| `CONFLIT getUpdates : un autre processus lit ce bot` | Deux `serve`, ou un autre programme sur le même bot | Garder un seul lecteur par bot |
| `getUpdates erreur 401` | Jeton révoqué | Nouveau jeton dans `secrets/bot.env`, redémarrer |
| `texte alternatif non pose` | X a refusé le texte alternatif | Sans effet sur la publication |
