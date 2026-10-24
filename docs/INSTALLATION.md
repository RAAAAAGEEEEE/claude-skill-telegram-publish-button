# Installation

Mise en service complète, de zéro jusqu'au premier bouton. Les libellés d'interface cités ont été relevés le 24/10/2026 et peuvent changer.

Voir aussi : [CONFIGURATION.md](CONFIGURATION.md) pour le détail des fichiers, [TROUBLESHOOTING.md](TROUBLESHOOTING.md) en cas d'erreur.

## Avant de commencer : une machine, un utilisateur

Le service `serve` et toutes les commandes (`envoyer`, `status`, `credit-set`, et celles que lance Claude Code) doivent tourner **sur la même machine, avec le même utilisateur système et le même dossier racine**. Cet utilisateur doit pouvoir écrire dans le dossier de posts de chaque projet. Sinon l'état des posts devient illisible pour l'un des deux, et le bouton refuse de publier.

Les exemples ci-dessous supposent le dépôt cloné dans `/opt/claude-skill-telegram-publish-button` ; remplacez ce chemin par le vôtre.

## 1. Récupérer le code et lancer les tests

Sur cette machine (Linux ou macOS, Python 3.10 ou plus récent) :

```bash
git clone https://github.com/RAAAAAGEEEEE/claude-skill-telegram-publish-button.git /opt/claude-skill-telegram-publish-button
cd /opt/claude-skill-telegram-publish-button
python3 scripts/publish_button.py selftest
python3 tests/test_publish_button.py
```

Résultat attendu : `selftest OK`, puis une dernière ligne `test d'integration OK ; appels X simules : 16`.

## 2. Créer le bot Telegram

1. Dans Telegram, ouvrir une conversation avec [@BotFather](https://t.me/BotFather).
2. Envoyer `/newbot`, puis un nom affiché et un nom d'utilisateur qui finit par `bot`.
3. BotFather répond avec le jeton du bot (une longue chaîne `123456:ABC...`). Ne le collez nulle part ailleurs que dans le fichier de l'étape 4.

Un bot ne peut être lu que par un seul programme à la fois. Si vous avez déjà un bot qui sert à autre chose, créez-en un nouveau pour ce service.

## 3. Créer le groupe à sujets

1. Créer un groupe Telegram (même avec vous seul dedans).
2. Ouvrir les infos du groupe, **Modifier**, puis activer **Sujets** (Topics). Le groupe devient un « forum » : chaque sujet est un fil séparé.
3. Ajouter le bot au groupe, puis dans **Administrateurs**, le nommer administrateur avec au moins le droit **Gérer les sujets** (Manage Topics).

## 4. Préparer le dossier racine

```bash
mkdir -p ~/.publish-button/secrets
chmod 700 ~/.publish-button/secrets
cp .env.example ~/.publish-button/secrets/bot.env
chmod 600 ~/.publish-button/secrets/bot.env
```

Ouvrir `~/.publish-button/secrets/bot.env` dans un éditeur et mettre le jeton du bot après `TELEGRAM_BOT_TOKEN=`.

Pour utiliser un autre dossier que `~/.publish-button`, définir `PUBLISH_BUTTON_HOME` avant chaque commande et dans le service (étape 8).

## 5. Trouver les identifiants et écrire config.json

1. Écrire un message quelconque dans le groupe.
2. Lancer :

   ```bash
   python3 scripts/publish_button.py ids
   ```

   Sortie attendue (exemple illustratif) :

   ```text
   groupe -1001234567890 Mes projets (sujets : oui)
   personne 111222333 @vous
   ```

3. Créer `~/.publish-button/config.json` avec ces deux valeurs :

   ```json
   {
     "groupe": "-1001234567890",
     "autorises": ["111222333"]
   }
   ```

   `autorises` liste les comptes Telegram qui ont le droit de publier en touchant un bouton. Les autres réglages (seuils, pause) ont des valeurs par défaut : voir [CONFIGURATION.md](CONFIGURATION.md).

4. Vérifier :

   ```bash
   python3 scripts/publish_button.py verifier
   ```

   Les lignes `groupe a sujets` et `bot admin, gestion des sujets` doivent dire `oui`. Sinon, voir [TROUBLESHOOTING.md](TROUBLESHOOTING.md).

## 6. Déclarer un projet et créer son app X

Pour chaque projet. Ici, le projet a pour slug `demo` (identifiant court : minuscules, chiffres, tirets), pour compte X `@DemoX`, et ses posts vivent dans `/srv/posts/demo` :

```bash
python3 scripts/publish_button.py nouveau-projet demo "Demo" DemoX /srv/posts/demo
```

Le sujet « Demo » apparaît dans le groupe.

Ensuite, créer l'app X du projet sur le portail développeur ([developer.x.com](https://developer.x.com/en/portal/dashboard)) :

1. Créer un projet et une app (ou réutiliser une app existante).
2. Dans les réglages de l'app, section **User authentication settings**, choisir **Set up** puis :
   - **App permissions** : *Read and write* ;
   - **Type of App** : *Web App, Automated App or Bot* (client confidentiel) ;
   - **Callback URI / Redirect URL** : `http://127.0.0.1:8765/callback` ;
   - **Website URL** : l'adresse du site du projet.
3. Dans **Keys and tokens**, copier le **Client ID** et le **Client Secret** (OAuth 2.0).
4. Créer `~/.publish-button/secrets/demo/x_app.json`, puis le passer en `chmod 600` :

   ```json
   {"client_id": "...", "client_secret": "..."}
   ```

5. Vérifier qu'il reste du crédit d'API X sur le compte développeur : la publication est facturée à l'usage.

## 7. Autoriser le compte X

X ne laisse que 30 secondes pour échanger le code d'autorisation ([documentation X](https://docs.x.com/fundamentals/authentication/oauth-2-0/authorization-code)). Le script attend donc lui-même le retour de X sur `127.0.0.1:8765`, ce qui marche quand le navigateur tourne sur la même machine que le script.

Si le script tourne sur un serveur distant, ouvrez d'abord, depuis votre ordinateur, un tunnel qui renvoie ce port vers le serveur (remplacez `utilisateur@serveur`) :

```bash
ssh -L 8765:127.0.0.1:8765 utilisateur@serveur
```

Puis, dans ce terminal ou sur la machine du script :

```bash
python3 scripts/publish_button.py --projet demo auth-url --ecoute
```

1. Ouvrir l'adresse affichée dans un navigateur **connecté au compte X du projet** (ici `@DemoX`).
2. Cliquer **Authorize app**.
3. La page affiche « Autorisation reçue, retour au terminal. » et le terminal affiche `compte verifie : DemoX`. Si le navigateur était connecté à un autre compte, le script refuse et n'enregistre rien.

Sans tunnel possible : lancez `python3 scripts/publish_button.py --projet demo auth-url` (sans `--ecoute`), puis préparez dans un second terminal `python3 scripts/publish_button.py --projet demo auth-finish`. Après **Authorize app**, le navigateur arrive sur une page `127.0.0.1` qui ne s'affiche pas : copiez toute l'adresse, collez-la dans le second terminal, puis Entrée et Ctrl+D, le tout en moins de 30 secondes.

Enfin, saisir le solde de crédit X affiché sur le portail (en dollars) :

```bash
python3 scripts/publish_button.py --projet demo credit-set 4.20
```

Sans ce solde, toute publication est refusée.

## 8. Lancer le service

Exemple d'unité systemd dans `/etc/systemd/system/publish-button.service`. Remplacez `publish` par l'utilisateur choisi au début, et les chemins par les vôtres :

```ini
[Unit]
Description=Bouton Telegram « Publier sur X »
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=publish
Environment=PUBLISH_BUTTON_HOME=/home/publish/.publish-button
ExecStart=/usr/bin/python3 /opt/claude-skill-telegram-publish-button/scripts/publish_button.py serve
Restart=on-failure
RestartSec=30
UMask=0077
NoNewPrivileges=true

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now publish-button
journalctl -u publish-button -n 20
```

Le journal doit afficher `service demarre ; projets : demo`.

## 9. Premier envoi

Écrire `posts.txt` et `suivi.json` dans `/srv/posts/demo` (format dans [USAGE.md](USAGE.md)), puis :

```bash
python3 scripts/publish_button.py --projet demo envoyer tout
```

Les posts arrivent dans le sujet « Demo ». Toucher « Publier sur X » publie le post correspondant.

## 10. Installer le skill dans Claude Code

- Pour vous seul : copier le dossier du dépôt dans `~/.claude/skills/telegram-publish-button/`.
- Pour un projet : le copier dans `.claude/skills/telegram-publish-button/` à la racine du projet.

Claude Code lit alors [SKILL.md](../SKILL.md) et sait envoyer les posts et les informations. Il doit tourner sur la machine et avec l'utilisateur du service.
