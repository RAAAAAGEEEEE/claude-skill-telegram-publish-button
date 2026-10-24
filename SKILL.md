---
name: telegram-publish-button
description: >
  Bouton Telegram « Publier sur X » : les posts préparés arrivent dans le sujet Telegram de leur projet
  (groupe à sujets, un sujet par projet, un compte X par projet) avec un bouton ; un toucher publie un
  post, rien ne part sans ce geste. Sert aussi à envoyer une information dans un sujet, sans sonnerie
  par défaut. À utiliser quand l'utilisateur dit « envoie les posts sur Telegram », « prépare le bouton
  Publier », « ajoute un projet au bouton », « nouveau compte X à brancher », « publie d'un toucher »,
  « envoie ça dans le sujet X du groupe », ou en anglais « Telegram publish button », « approve tweets
  from Telegram », « one tap to post on X ». Ne lit jamais X, ne programme rien, n'affiche aucun jeton.
license: MIT
compatibility: >
  Claude Code (skill personnel ou par projet). Linux ou macOS, Python 3.10+, bibliothèque standard
  seulement. Réseau : api.telegram.org et api.x.com uniquement.
metadata:
  author: Anto1nx
  version: "0.1.0"
  repository: https://github.com/RAAAAAGEEEEE/claude-skill-telegram-publish-button
allowed-tools: Read Bash(python3:*)
---

# Bouton « Publier sur X » dans Telegram

Le script `scripts/publish_button.py` de ce skill envoie des posts dans un groupe Telegram à sujets, un sujet par projet, chacun avec un bouton « Publier sur X ». Le service `serve` publie le post sur le compte X du projet quand une personne autorisée touche le bouton.

Les commandes ci-dessous supposent une installation personnelle, dans `~/.claude/skills/telegram-publish-button/`. Pour une installation par projet, remplacer ce chemin par `.claude/skills/telegram-publish-button/`. Les lancer sur la machine et avec l'utilisateur du service `serve` (voir `docs/INSTALLATION.md`, étape 8).

## Périmètre

Dans le périmètre :
- déclarer un projet (sujet Telegram, compte X, dossier de posts) ;
- envoyer des posts dans le sujet de leur projet, avec bouton, texte et visuel ;
- envoyer une information dans un sujet, sans sonnerie par défaut, avec `--sonne` si un geste est attendu ;
- lire l'état d'un projet (`status`), recaler le solde estimé (`credit-set`), trancher un post incertain (`resoudre`) ;
- vérifier la configuration (`verifier`).

Hors périmètre, à refuser ou à signaler :
- publier sur X sans toucher du bouton : le skill ne publie jamais lui-même ;
- lire X (timeline, mentions, recherche) ou programmer des publications ;
- afficher, copier ou coller un jeton (Telegram ou X) ;
- toucher le bouton à la place de l'utilisateur, ou faire un « post de test » réel sans sa demande explicite.

## Quand l'utiliser

- L'utilisateur a des posts prêts et veut les valider d'un toucher : commande `envoyer`.
- Un nouveau projet ou un nouveau compte X arrive : `nouveau-projet`, puis l'autorisation X, que l'utilisateur fait lui-même dans son navigateur.
- Un script ou un agent doit prévenir l'utilisateur : `info` dans un sujet, sans sonnerie sauf si une action est attendue.

Ne pas l'utiliser pour un message privé à une autre personne ni pour un autre réseau que X.

## Ordre d'exécution

1. **Vérifier** :

   ```bash
   python3 ~/.claude/skills/telegram-publish-button/scripts/publish_button.py verifier
   ```

   S'arrêter si le bot n'est pas administrateur ou si le groupe n'a pas de sujets (voir `docs/TROUBLESHOOTING.md`).
2. **Préparer** : écrire `posts.txt` et `suivi.json` dans le dossier du projet (format dans `docs/USAGE.md`). Chaque texte fait 280 caractères au plus, sans lien si `refuser_liens` est vrai.
3. **Envoyer** :

   ```bash
   python3 ~/.claude/skills/telegram-publish-button/scripts/publish_button.py --projet demo envoyer tout
   ```

   Un post déjà envoyé n'est pas renvoyé, sauf avec `--renvoyer`.
4. **Rendre compte** : dire à l'utilisateur combien de posts attendent dans quel sujet. La publication reste son geste.

## Entrées et sorties

Entrées : `config.json`, `projets.json`, `sujets.json` et les secrets dans `$PUBLISH_BUTTON_HOME` (par défaut `~/.publish-button`) ; `posts.txt`, `suivi.json` et `visuels/` dans le dossier de chaque projet.

Sorties :
- messages Telegram dans le sujet du projet ;
- `telegram_envois.json` (journal des envois) dans le dossier du projet ;
- `state/<projet>/etat.json` (état de chaque post) et `credit.json` (solde estimé) ;
- `suivi.json` mis à jour (statut, date, lien) après chaque publication.

## Exemples d'invocation

Commandes abrégées : `pb` désigne `python3 ~/.claude/skills/telegram-publish-button/scripts/publish_button.py`.

- « Envoie les posts de la semaine du projet demo sur Telegram. » → `pb --projet demo envoyer tout`
- « Renvoie le post 4, je l'ai corrigé. » → `pb --projet demo envoyer 4 --renvoyer --note "version corrigée"`
- « Branche le compte @NouveauX pour le projet nouveau. » → `pb nouveau-projet nouveau "Nouveau" NouveauX /chemin/posts`, puis guider l'utilisateur dans la création de l'app X et l'autorisation (`docs/INSTALLATION.md`, étapes 6 et 7).
- « Préviens-moi dans Telegram quand la sauvegarde est finie. » → `pb info serveur "Sauvegarde terminée."`

## Exemple de sortie

Exemple illustratif :

```text
post 1 ok message_id= 120
post 2 ok message_id= 121
post 3 ECHEC visuel absent : v3.png message_id= None
```

## Repli et erreurs

- Un envoi en échec n'est pas journalisé : relancer la même commande ne renvoie que les posts manquants.
- Un post refusé au toucher (texte modifié, crédit sous le seuil, post bloqué) reçoit une explication ; rien n'est publié.
- Réponse de X perdue pendant une publication : le post passe en état « incertain » et le bouton refuse tout nouveau toucher. Demander à l'utilisateur de regarder le profil X, puis `pb --projet demo resoudre ID libre` (post absent) ou `pb --projet demo resoudre ID publie TWEET_ID` (post présent).
- `CONFLIT getUpdates` dans le journal du service : un autre programme lit déjà ce bot. Ne pas lancer un second `serve`.

Liste complète : `docs/TROUBLESHOOTING.md`.

## Niveaux de preuve

Les comptes rendus distinguent ce qui est vérifié (sortie de commande, `message_id` renvoyé par Telegram, lien `x.com/.../status/...` renvoyé par X) de ce qui est estimé (solde de crédit : estimation locale, jamais une lecture de X).

## Tests et évaluations

`python3 scripts/publish_button.py selftest` et `python3 tests/test_publish_button.py`, depuis le dossier du skill : hors ligne, sans jeton, à lancer après toute modification du script. Pas d'évaluation du déclenchement du skill pour l'instant.

## Installation

- Personnelle : copier ce dossier dans `~/.claude/skills/telegram-publish-button/`.
- Par projet : le copier dans `.claude/skills/telegram-publish-button/` à la racine du projet.

La mise en service du bot, du groupe et des comptes X est décrite dans `docs/INSTALLATION.md`.

## Sécurité et confidentialité

- Données envoyées : à Telegram, les posts (texte et visuel) et les messages `info` ; à X, au toucher seulement, le texte, le visuel et le texte alternatif du post, plus les échanges de jetons et la lecture du nom du compte autorisé. Aucune autre destination.
- Le jeton du bot vient de `TELEGRAM_BOT_TOKEN` ou de `secrets/bot.env` ; les jetons X sont dans `secrets/<projet>/` en `chmod 600`. Ne jamais les afficher ni les recopier dans une réponse.
- L'autorisation X se fait dans le navigateur de l'utilisateur : le skill prépare l'adresse, l'utilisateur se connecte lui-même.

Détail : `docs/PRIVACY_AND_SECURITY.md`.

## Version

0.1.0 du 24/10/2026. Historique : `CHANGELOG.md`.

## Références

- API Telegram Bot, sujets de forum : https://core.telegram.org/bots/api#createforumtopic
- API X v2, création de post : https://docs.x.com/x-api/posts/create-post
