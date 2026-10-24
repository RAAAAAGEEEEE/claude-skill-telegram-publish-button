# Configuration

Tous les fichiers vivent dans le dossier racine : `$PUBLISH_BUTTON_HOME`, ou `~/.publish-button` si la variable n'est pas définie. Seule exception : le dossier de posts de chaque projet, dont le chemin est donné dans `projets.json`.

Voir aussi : [INSTALLATION.md](INSTALLATION.md), [PRIVACY_AND_SECURITY.md](PRIVACY_AND_SECURITY.md).

## Variables d'environnement

| Variable | Rôle | Défaut |
|---|---|---|
| `PUBLISH_BUTTON_HOME` | Dossier racine | `~/.publish-button` |
| `TELEGRAM_BOT_TOKEN` | Jeton du bot ; s'il est absent, lu dans `secrets/bot.env` | aucun |

Modèle : [.env.example](../.env.example).

## Arborescence

```text
~/.publish-button/
├── config.json          groupe, personnes autorisées, garde-fous
├── projets.json         un projet = son nom, son compte X, son dossier de posts
├── sujets.json          slug -> numéro du sujet Telegram (rempli par le script)
├── secrets/             chmod 700
│   ├── bot.env          TELEGRAM_BOT_TOKEN=... (chmod 600)
│   └── <projet>/        x_app.json, x_tokens.json et .prev (chmod 600),
│                        pkce.json (temporaire, pendant l'autorisation)
└── state/<projet>/      etat.json, credit.json, verrous
```

## config.json

```json
{
  "groupe": "-1001234567890",
  "autorises": ["111222333"],
  "cout_post_usd": 0.015,
  "marge_media_usd": 0.010,
  "seuil_arret_usd": 1.00,
  "pause_min_s": 60,
  "refuser_liens": true
}
```

| Clé | Rôle | Défaut |
|---|---|---|
| `groupe` | Identifiant du groupe à sujets (commande `ids`) | obligatoire |
| `autorises` | Identifiants Telegram des personnes qui peuvent publier | obligatoire |
| `cout_post_usd` | Coût estimé d'un post, déduit du solde à chaque publication | `0.015` |
| `marge_media_usd` | Coût ajouté quand le post a un visuel | `0.010` |
| `seuil_arret_usd` | Plus aucune publication si le solde estimé passerait sous ce montant | `1.00` |
| `pause_min_s` | Délai minimal entre deux publications du même projet, en secondes | `60` |
| `refuser_liens` | Refuser les textes qui contiennent un lien ou un nom de domaine | `true` |

Les coûts par défaut sont des estimations prudentes, pas des tarifs officiels : relevez le prix réel sur votre compte développeur X et ajustez-les. Le solde estimé se recale avec `credit-set`.

## projets.json

Écrit par `nouveau-projet` ; modifiable à la main.

```json
{
  "demo": {"nom": "Demo", "compte": "DemoX", "travail": "/srv/posts/demo"}
}
```

| Clé | Rôle |
|---|---|
| `nom` | Nom du sujet Telegram à sa création |
| `compte` | Nom du compte X, sans `@` ; l'autorisation X refuse tout autre compte |
| `travail` | Dossier de `posts.txt`, `suivi.json`, `visuels/` et `telegram_envois.json` |

## sujets.json

Rempli par le script à la création de chaque sujet. Pour réutiliser un sujet existant, ajoutez son numéro à la main (le numéro d'un sujet est l'identifiant de son premier message, visible dans le lien d'un message du sujet) :

```json
{"demo": {"id": 911, "nom": "Demo"}}
```

## Secrets par projet

- `secrets/<projet>/x_app.json` : `{"client_id": "...", "client_secret": "..."}`, à créer à la main ([INSTALLATION.md](INSTALLATION.md), étape 6).
- `secrets/<projet>/x_tokens.json` : écrit à la fin de l'autorisation et à chaque rafraîchissement. L'ancienne version est gardée en `x_tokens.json.prev`.
- `secrets/<projet>/pkce.json` : vérificateur et `state` de l'autorisation en cours, supprimé à la fin.

## État par projet

- `state/<projet>/etat.json` : état de chaque post (`en_cours`, `publie`, `incertain`, `echec`, `libre`).
- `state/<projet>/credit.json` : solde estimé et date de mise à jour.
