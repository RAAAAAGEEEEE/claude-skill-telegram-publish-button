# Sécurité

## Surface

Le script parle à deux API : Telegram (envoi de messages, lecture des touchers de boutons) et X (publication, jetons OAuth). Il stocke en clair, sur la machine qui le fait tourner, le jeton du bot et les jetons X de chaque projet. Détail des données et des menaces : [docs/PRIVACY_AND_SECURITY.md](docs/PRIVACY_AND_SECURITY.md).

## Signaler un problème

Utilisez le signalement privé de GitHub : onglet **Security**, puis **Report a vulnerability** ([lien direct](https://github.com/RAAAAAGEEEEE/claude-skill-telegram-publish-button/security/advisories/new)). N'ouvrez pas d'issue publique pour une faille.

Cas typiques à signaler :
- une publication possible sans toucher, ou par une personne absente de `autorises` ;
- un jeton visible dans une sortie, un message Telegram ou un journal ;
- un double post possible malgré l'état `incertain`.

## Versions concernées

Seule la dernière version publiée (voir [CHANGELOG.md](CHANGELOG.md)) reçoit des correctifs.
