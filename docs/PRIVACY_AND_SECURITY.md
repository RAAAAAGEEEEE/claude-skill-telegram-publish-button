# Confidentialité et sécurité

Voir aussi : [SECURITY.md](../SECURITY.md) pour signaler une faille, [CONFIGURATION.md](CONFIGURATION.md) pour l'emplacement des fichiers.

## Données qui sortent de la machine

| Vers | Quoi | Quand |
|---|---|---|
| `api.telegram.org` | Texte et visuel des posts, informations envoyées avec `info` | À chaque `envoyer` ou `info` |
| `api.telegram.org` | Lecture des touchers de boutons | En continu avec `serve` |
| `api.x.com` | Texte, visuel et texte alternatif du post | Au toucher du bouton seulement |
| `api.x.com` | Échange et rafraîchissement des jetons, lecture du nom du compte autorisé | `auth-finish`, puis au besoin |

Aucune autre adresse n'est contactée. Aucune statistique, aucun suivi d'usage.

## Ce que le script ne fait jamais

- Lire X : ni timeline, ni mentions, ni recherche, ni messages privés.
- Publier sans toucher : aucune commande ne publie directement.
- Afficher un jeton : les messages d'erreur ne contiennent jamais l'adresse de l'API Telegram (qui contient le jeton du bot) ni les jetons X.

## Secrets

| Secret | Emplacement | Protection |
|---|---|---|
| Jeton du bot Telegram | `TELEGRAM_BOT_TOKEN` ou `secrets/bot.env` | `chmod 600` à faire à l'installation |
| Client ID et Client Secret de l'app X | `secrets/<projet>/x_app.json` | `chmod 600` à faire à l'installation |
| Jetons d'accès et de rafraîchissement X | `secrets/<projet>/x_tokens.json` (+ `.prev`) | écrits en `chmod 600` par le script |

Les secrets sont stockés **en clair** sur le disque. Toute personne qui lit ces fichiers peut publier sur vos comptes X. Protégez le compte système qui fait tourner le service, et ne versionnez jamais le dossier racine.

En cas de fuite :
- jeton du bot : `/revoke` auprès de @BotFather, puis nouveau jeton ;
- jetons X : révoquer l'accès de l'app dans les réglages du compte X (**Paramètres et confidentialité**, **Sécurité et accès au compte**, **Applications et sessions**), puis refaire `auth-url` et `auth-finish` ;
- Client Secret : le régénérer dans le portail développeur X.

## Qui peut publier

Seuls les identifiants Telegram listés dans `autorises`, depuis le groupe de `config.json`, dans le sujet du projet. Être membre du groupe ne suffit pas. Un bouton transféré dans une autre conversation est refusé.

## Menaces couvertes

- **Bouton forgé** : les données du bouton sont contrôlées par une expression régulière stricte, et l'empreinte doit correspondre au post actuel.
- **Contenu modifié après relecture** : l'empreinte couvre le texte et le fichier visuel ; le texte doit aussi figurer dans le message touché.
- **Double publication** : verrou de fichier, état `en_cours`, puis `publie` ou `incertain`.
- **Mauvais compte** : l'autorisation vérifie le nom du compte, et chaque publication vérifie le compte enregistré.
- **Dépense incontrôlée** : seuil d'arrêt et pause minimale entre deux publications.

## Menaces non couvertes

- Un compte Telegram autorisé volé peut publier les posts déjà envoyés (mais pas un texte de son choix).
- Une personne qui peut écrire dans le dossier de posts et renvoyer les messages peut faire publier son texte au toucher suivant : relisez avant de toucher.
- Le script ne chiffre pas les secrets au repos.
