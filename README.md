# claude-skill-telegram-publish-button

A Claude Code skill and a stdlib-only Python script: drafted posts arrive in a Telegram forum topic (one topic per project) with a « Publier sur X » button; one tap publishes one post on that project's X account. No timeline reading, no scheduled posting. Documentation in French.

---

## Le problème

Vous préparez des posts X pour plusieurs projets, chacun avec son propre compte. Les publier à la main veut dire copier, coller, joindre l'image, changer de compte, et se tromper de compte une fois de temps en temps. Les publier par une tâche planifiée (cron) enlève le dernier regard humain.

Ce skill garde ce dernier regard et supprime le reste : chaque post prêt arrive dans le sujet Telegram de son projet, texte et visuel compris, avec un bouton. Vous relisez sur votre téléphone, vous touchez « Publier sur X », le post part sur le bon compte et le lien revient dans le sujet.

## Pour qui

- Les personnes seules ou les petites équipes qui gèrent plusieurs comptes X (un par projet) et qui utilisent déjà Telegram.
- Les utilisateurs de Claude Code qui font préparer leurs posts par un agent et veulent valider chacun d'un geste.

## Ce que ça apporte

- **Un toucher = un post.** Rien ne part sans ce geste. Un deuxième toucher ne republie pas.
- **Ce que vous voyez est ce qui part.** Le bouton porte une empreinte du texte et du visuel : si le post a changé depuis l'envoi du message, le bouton refuse.
- **Un projet = son compte X et son sujet.** Un bouton n'est accepté que dans le sujet de son projet, et l'autorisation X vérifie le nom du compte.
- **Une règle de notification simple.** Un message qui attend un geste (post à publier) sonne ; une simple information part sans sonnerie.
- **Des garde-fous de dépense.** L'API X est payante à l'usage : le script tient un solde estimé et s'arrête sous un seuil.

## Statut

**Alpha (version 0.1.0, 24/10/2026).** Le code vient d'un outil en service réel depuis octobre 2026 pour un seul projet, rendu générique pour plusieurs projets. La version générique passe ses tests hors ligne ; elle n'a pas encore servi en production sous cette forme.

## Exemple de sortie

Message reçu dans le sujet « Demo » du groupe (exemple illustratif) :

```text
Post 3/12 : à publier le 2026-11-02 (annonce)
Notre version 1.2 est sortie : trois nouveaux modes et un éditeur de niveaux.
[ Publier sur X ]
```

Après le toucher, le bouton devient « Voir le post publié » et une réponse arrive dans le sujet :

```text
Publié sur @DemoX (post 3).
https://x.com/demox/status/1234567890
```

## Prérequis

- Linux ou macOS (le script utilise `fcntl`), Python 3.10 ou plus récent, aucune dépendance.
- Un bot Telegram (créé avec @BotFather) et un groupe Telegram avec les sujets activés, où le bot est administrateur avec le droit de gérer les sujets.
- Pour chaque projet : un compte X et une app X (OAuth 2.0) avec du crédit d'API.
- Une machine allumée en permanence pour la commande `serve` (un petit serveur suffit).

## Démarrage rapide

```bash
git clone https://github.com/RAAAAAGEEEEE/claude-skill-telegram-publish-button.git
cd claude-skill-telegram-publish-button
python3 scripts/publish_button.py selftest
python3 tests/test_publish_button.py
```

Les deux commandes de test n'utilisent pas le réseau. La mise en service complète (bot, groupe, `config.json`, autorisation X, service systemd) est décrite pas à pas dans [docs/INSTALLATION.md](docs/INSTALLATION.md).

## Exemple minimal

Une fois l'installation faite, pour un projet de slug `demo` (identifiant court : minuscules, chiffres, tirets), dont le compte X est `@DemoX` :

```bash
python3 scripts/publish_button.py nouveau-projet demo "Demo" DemoX /srv/posts/demo
```

Cette commande crée le sujet « Demo » dans le groupe. Écrivez ensuite `posts.txt` et `suivi.json` dans `/srv/posts/demo` (format : [docs/USAGE.md](docs/USAGE.md)), puis :

```bash
python3 scripts/publish_button.py --projet demo envoyer tout
python3 scripts/publish_button.py info demo "Sauvegarde du soir terminée."
```

La première ligne envoie chaque post avec son bouton ; la seconde envoie une information sans sonnerie.

## Architecture en bref

Un seul script, `scripts/publish_button.py`. La commande `serve` écoute uniquement les touchers de boutons (`callback_query`) du bot. À chaque toucher, elle vérifie l'expéditeur, le groupe, le sujet, le projet et l'empreinte, réserve le post sous verrou, publie avec `POST /2/tweets`, puis répond dans le sujet. Détail : [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md).

## Configuration

Tout vit dans un dossier racine (`~/.publish-button` par défaut, ou `$PUBLISH_BUTTON_HOME`) : `config.json` (groupe, personnes autorisées, garde-fous), `projets.json`, `sujets.json`, et les secrets par projet. Détail : [docs/CONFIGURATION.md](docs/CONFIGURATION.md) et [.env.example](.env.example).

## Sécurité et confidentialité

Seuls les identifiants Telegram listés dans `config.json` peuvent publier, et seulement depuis le groupe configuré. Les jetons X sont stockés en clair dans des fichiers `chmod 600` sur votre machine ; aucun jeton n'est affiché ni écrit dans les journaux. Les seules données envoyées vont à Telegram et à X. Détail : [docs/PRIVACY_AND_SECURITY.md](docs/PRIVACY_AND_SECURITY.md) et [SECURITY.md](SECURITY.md).

## Limites

- Pas de Windows natif (verrous `fcntl`) ; passer par WSL.
- Le service et les commandes doivent tourner sur la même machine, avec le même utilisateur.
- Le solde de crédit X est une **estimation** locale, à recaler à la main avec `credit-set`.
- Si la réponse de X se perd pendant une publication, le script ne sait pas si le post est parti : il bloque ce post jusqu'à ce que vous tranchiez avec `resoudre`.
- Telegram ne règle pas de vibration par sujet : voir [les limites des notifications](docs/LIMITATIONS.md#notifications).

Liste complète : [docs/LIMITATIONS.md](docs/LIMITATIONS.md).

## Feuille de route (non contractuelle)

- Prise en charge de Bluesky et Threads avec le même bouton.
- Programmation d'une heure de publication après le toucher.
- Verrous portables pour Windows.

## Contribuer

Voir [CONTRIBUTING.md](CONTRIBUTING.md).

## Licence

MIT, voir [LICENSE](LICENSE).

## Documentation

- [docs/INSTALLATION.md](docs/INSTALLATION.md) : mise en service pas à pas
- [docs/USAGE.md](docs/USAGE.md) : commandes, format des posts, usage avec Claude Code
- [docs/CONFIGURATION.md](docs/CONFIGURATION.md) : fichiers et réglages
- [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) : fonctionnement interne
- [docs/TROUBLESHOOTING.md](docs/TROUBLESHOOTING.md) : messages d'erreur et solutions
- [docs/LIMITATIONS.md](docs/LIMITATIONS.md) : limites connues
- [docs/PRIVACY_AND_SECURITY.md](docs/PRIVACY_AND_SECURITY.md) : données, secrets, menaces
- [SKILL.md](SKILL.md) : instructions du skill pour Claude Code
