# Contribuer

Issues et pull requests bienvenues.

## Avant d'ouvrir une pull request

1. Les deux tests passent, hors ligne et sans jeton :

   ```bash
   python3 scripts/publish_button.py selftest
   python3 tests/test_publish_button.py
   ```

2. Tout nouveau comportement a son test dans `tests/test_publish_button.py`, avec le faux réseau du fichier : aucun test ne contacte Telegram ni X.
3. `publier()` reste la seule fonction qui écrit sur X. Aucune lecture de X, aucune publication sans toucher du bouton.
4. Aucun message ni journal n'affiche un jeton ou une adresse d'API qui en contient un.
5. La documentation change dans le même commit que le comportement : `SKILL.md` si le déroulé change, `docs/` si l'usage ou la configuration change, `.env.example` et `docs/CONFIGURATION.md` pour toute nouvelle variable, `CHANGELOG.md` dans tous les cas.
6. Aucune donnée personnelle, aucun identifiant réel ni nom de projet réel dans les exemples et les tests : tout est fictif et dit comme tel.

## Style

- Python 3.10 ou plus récent, bibliothèque standard seulement, un seul fichier de script.
- Code, messages et documentation en français, comme le reste du dépôt.
- Annotations de type sur les fonctions.
