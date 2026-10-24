# Journal des versions

Format inspiré de [Keep a Changelog](https://keepachangelog.com/fr/1.1.0/), versions selon [SemVer](https://semver.org/lang/fr/).

## [0.1.0] - 2026-10-24

Première version publique.

### Ajouté

- `scripts/publish_button.py` : bouton Telegram « Publier sur X », plusieurs projets dans un groupe à sujets (un sujet et un compte X par projet).
- Autorisation X avec `auth-url --ecoute` : petit serveur local qui reçoit la redirection, car X n'accepte le code que 30 secondes ; `auth-finish` accepte aussi l'adresse de retour complète.
- Commandes `ids`, `verifier`, `nouveau-projet`, `sujet`, `info`, `envoyer`, `auth-url`, `auth-finish`, `credit-set`, `resoudre`, `status`, `serve`, `selftest`.
- Garde-fous : empreinte du contenu dans le bouton, état `incertain` contre le double post, solde estimé avec seuil d'arrêt, pause minimale, refus des liens, vérification du compte X.
- Tests hors ligne `tests/test_publish_button.py` et intégration continue (Linux, macOS ; Python 3.10 et 3.12).
- `SKILL.md` et documentation complète dans `docs/`.
