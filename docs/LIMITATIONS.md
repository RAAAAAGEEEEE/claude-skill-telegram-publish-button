# Limites connues

Voir aussi : [ARCHITECTURE.md](ARCHITECTURE.md), [TROUBLESHOOTING.md](TROUBLESHOOTING.md).

## Portée

- **X seulement.** Ni Bluesky, ni Threads, ni Mastodon.
- **Un post à la fois.** Pas de fil publié d'un seul toucher : chaque post d'un fil a son bouton, et `reply_to` impose l'ordre.
- **Pas de programmation.** La date `prevu` est affichée, jamais appliquée : le post part au moment du toucher.
- **Un seul groupe.** Tous les projets partagent le groupe de `config.json`.

## Technique

- **Pas de Windows natif** : les verrous utilisent `fcntl`. WSL convient.
- **Un bot = un lecteur.** Le bot ne doit être lu par aucun autre programme (`getUpdates` ou webhook), sinon Telegram répond 409 à l'un des deux.
- **Une machine allumée en permanence** pour `serve`. Un toucher fait pendant un arrêt est écarté au redémarrage : il faut retoucher.
- **Visuels** : une image ou un GIF par post (5 Mo pour une image, 15 Mo pour un GIF côté script) ; pas de vidéo. La légende Telegram d'un post avec visuel est limitée à 1 024 caractères.
- **Longueur** : le comptage des 280 caractères reproduit la règle de X pour le latin et les emoji (2 par emoji ou caractère CJK), sans gérer le raccourcissement des liens (les liens sont refusés par défaut). Un emoji composé (famille, drapeau, teinte de peau) compte plus que sur X : un texte peut être refusé alors que X l'aurait accepté.
- **Filtre de liens** : il refuse tout ce qui ressemble à un nom de domaine, y compris des faux positifs comme `M.Dupont` ou `posts.txt`. Mettre `refuser_liens` à `false` pour le désactiver.
- **Autorisation X** : X n'accepte le code que 30 secondes ; sans `auth-url --ecoute` (même machine ou tunnel SSH), la copie à la main doit être rapide.
- **Rafraîchissement du jeton** : si la réponse de X se perd pendant un rafraîchissement, l'ancien jeton de rafraîchissement peut déjà être consommé ; il faut alors refaire l'autorisation.
- **Même machine, même utilisateur** pour le service et les commandes (droits sur l'état et le dossier de posts).

## Argent

- **Le solde est une estimation.** Le script ne lit pas le crédit réel sur X : il déduit un coût fixe par post (`cout_post_usd`, `marge_media_usd`). Recalez-le avec `credit-set` après chaque recharge et de temps en temps.
- Les coûts par défaut ne sont pas des tarifs officiels.

## Cas incertain

Si la réponse de X se perd pendant une publication, le script ne peut pas savoir si le post est parti. Il bloque ce post (état `incertain`) jusqu'à ce que vous regardiez le profil et lanciez `resoudre`. C'est volontaire : sans ce blocage, un nouveau toucher pourrait publier deux fois.

## Notifications

Relevé du 24/10/2026, Telegram pour iPhone :

- Un message envoyé sans sonnerie produit une notification sans son ([API Telegram, `disable_notification`](https://core.telegram.org/bots/api#sendmessage)). Sur iPhone, une notification sans son ne vibre pas non plus, même en mode vibreur (comportement observé, non documenté par Telegram) : c'est ce qui distingue une information d'un post à publier.
- Chaque sujet d'un groupe a ses propres réglages de notification, ce qui permet de couper le son des seuls sujets d'information ([annonce Telegram des sujets](https://telegram.org/blog/topics-in-groups-collectible-usernames)).
- Un son personnalisé est possible par conversation (fichier de moins de 5 secondes et de 300 Ko, depuis **Couper le son**, puis **Personnaliser**), mais il ne joue pas quand le téléphone est en mode vibreur.
- Telegram ne propose pas de motif de vibration par conversation ni par sujet. Sur iPhone, les vibrations personnalisées ne valent que pour les contacts du téléphone et les sons du système.

## Statut

Version 0.1.0 (alpha). Tests hors ligne seulement dans ce dépôt ; la version d'origine, propre à un projet, est en service depuis octobre 2026.
