# Utilisation

Toutes les commandes passent par `scripts/publish_button.py`, lancé depuis le dossier du dépôt, sur la machine et avec l'utilisateur du service (voir [INSTALLATION.md](INSTALLATION.md)). Celles qui concernent un projet prennent `--projet SLUG` : le slug fait de 2 à 16 caractères (minuscules, chiffres, tirets) et commence par une lettre.

Voir aussi : [CONFIGURATION.md](CONFIGURATION.md) pour les fichiers, [TROUBLESHOOTING.md](TROUBLESHOOTING.md) pour les messages d'erreur.

## Commandes

| Commande | Rôle |
|---|---|
| `ids` | Identifiants du groupe et des personnes qui ont écrit récemment (installation, service arrêté) |
| `verifier` | Contrôle le bot, le groupe et les droits, sans rien envoyer |
| `nouveau-projet SLUG "Nom" COMPTE_X DOSSIER` | Déclare un projet, crée son sujet et ses dossiers |
| `sujet SLUG ["Nom"]` | Numéro du sujet (le crée s'il manque) |
| `info SLUG [--sonne] TEXTE` | Message dans un sujet ; `TEXTE` = `-` lit l'entrée standard |
| `--projet SLUG envoyer IDS\|tout [--renvoyer] [--silencieux] [--note "..."]` | Envoie des posts avec leur bouton |
| `--projet SLUG auth-url [--ecoute]` | Adresse d'autorisation du compte X ; `--ecoute` attend le retour de X et finit seul |
| `--projet SLUG auth-finish` | Lit l'adresse de retour de X (ou `code state`) sur l'entrée standard |
| `--projet SLUG credit-set MONTANT` | Recale le solde estimé du crédit X (en dollars) |
| `--projet SLUG resoudre ID libre\|publie TWEET_ID` | Tranche un post en état incertain |
| `--projet SLUG status` | État du projet, sans secret |
| `serve` | Service : écoute les boutons de tous les projets |
| `selftest` | Tests hors ligne intégrés |

## Format des posts

Dans le dossier du projet :

- `posts.txt` : les textes, séparés par une ligne `---` seule (fins de ligne Unix, sans espace après `---`).
- `suivi.json` : une entrée par texte, dans le même ordre. Les deux fichiers doivent avoir le même nombre d'entrées.
- `visuels/` : les images (PNG, JPEG) et GIF animés cités dans `suivi.json`.

Exemple illustratif de `posts.txt` :

```text
Notre version 1.2 est sortie : trois nouveaux modes et un éditeur de niveaux.
---
Le mode coopératif arrive vendredi. Vous jouez à deux sur le même écran.
---
Rendez-vous le 14 novembre pour la sortie sur consoles.
```

Exemple illustratif de `suivi.json` :

```json
{"posts": [
  {"id": 1, "prevu": "2026-11-02", "theme": "annonce", "visuel": "v12.png", "alt": "Écran titre de la version 1.2"},
  {"id": 2, "prevu": "2026-11-03", "reply_to": 1, "visuel": null},
  {"id": 3, "bloque": true, "bloque_motif": "attendre la date de sortie"}
]}
```

| Champ | Rôle |
|---|---|
| `id` | Numéro du post : entier de 1 à 9999, unique dans le projet |
| `prevu` | Date affichée dans le message (information seulement : rien n'est programmé) |
| `theme` | Étiquette affichée dans l'en-tête |
| `visuel` | Nom du fichier dans `visuels/`, ou `null` |
| `alt` | Texte alternatif de l'image, envoyé à X |
| `reply_to` | Publier en réponse au post `id` indiqué (qui doit déjà être publié) |
| `bloque`, `bloque_motif` | Post envoyé sans bouton, avec le motif affiché |

Après chaque publication, le script ajoute `statut`, `publie` (date) et `url` à l'entrée du post.

## Envoyer des posts

```bash
python3 scripts/publish_button.py --projet demo envoyer tout
python3 scripts/publish_button.py --projet demo envoyer 2,3
python3 scripts/publish_button.py --projet demo envoyer 2 --renvoyer --note "version corrigée"
```

- Un post déjà envoyé (présent dans `telegram_envois.json`) est sauté, sauf avec `--renvoyer`.
- Un message qui porte un bouton **sonne** : il attend votre geste. `--silencieux` l'envoie sans sonnerie, par exemple pour renvoyer des posts déjà vus.
- Si vous modifiez un post après l'envoi, l'ancien bouton refuse de publier : renvoyez le post avec `--renvoyer`.

## Publier

Touchez « Publier sur X » sous le post, dans le sujet du projet. Le script :

1. affiche une notification brève « Publication en cours... » ;
2. publie le texte et le visuel sur le compte X du projet ;
3. remplace le bouton par « Voir le post publié » et répond dans le sujet avec le lien.

En cas de refus, rien n'est publié. Un refus sur le bouton lui-même (personne non autorisée, bouton périmé, mauvais sujet) s'affiche en notification brève ; un refus sur le post (texte modifié, crédit, état) arrive en réponse dans le sujet. Tous les messages sont listés dans [TROUBLESHOOTING.md](TROUBLESHOOTING.md).

## Envoyer une information

```bash
python3 scripts/publish_button.py info demo "Sauvegarde du soir terminée."
echo "Incident : disque plein" | python3 scripts/publish_button.py info alertes --sonne -
```

Règle conseillée : une simple information part sans sonnerie ; `--sonne` seulement quand une action est attendue. Le sujet est créé à la première utilisation si le slug est inconnu (il n'a pas besoin d'être un projet). Ce qu'un téléphone fait d'un message sans sonnerie est décrit dans [LIMITATIONS.md](LIMITATIONS.md#notifications).

Depuis un autre script Python :

```python
import sys
sys.path.insert(0, "/opt/claude-skill-telegram-publish-button/scripts")
import publish_button as pb

pb.info(pb.Tg(), "serveur", "Sauvegarde du soir terminée.")
```

## Avec Claude Code

Une fois le skill installé ([INSTALLATION.md](INSTALLATION.md), étape 10), il suffit de demander : « envoie les posts du projet demo sur Telegram » ou « préviens-moi dans le sujet serveur quand c'est fini ». Claude Code ne publie jamais lui-même : la publication reste votre toucher.
