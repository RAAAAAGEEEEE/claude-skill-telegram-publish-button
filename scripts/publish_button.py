#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""publish_button.py : un bouton Telegram « Publier sur X » par post, un toucher = un post.

Un groupe Telegram a sujets (forum), un sujet par projet. Chaque projet a son compte X.
Les posts prepares arrivent dans le sujet du projet avec un bouton ; rien ne part sur X sans toucher.
Aucune lecture de timeline, aucun cron, aucune autre ecriture X que publier().

Commandes (--projet SLUG partout ou un projet est en jeu) :
  ids                                      identifiants du groupe et des personnes (installation)
  verifier                                 controle la configuration (bot, groupe, droits), sans rien envoyer
  nouveau-projet SLUG "Nom" COMPTE_X DOSSIER   declare un projet, cree son sujet et ses dossiers
  sujet SLUG ["Nom"]                       numero du sujet (cree s'il manque)
  info SLUG [--sonne] TEXTE                message dans un sujet (sans sonnerie par defaut ; TEXTE = - : entree standard)
  envoyer --projet SLUG IDS|tout [--renvoyer] [--silencieux] [--note "..."]
  auth-url --projet SLUG [--ecoute]        URL d'autorisation OAuth 2.0 PKCE du compte X du projet ;
                                           --ecoute attend le retour sur 127.0.0.1:8765 et finit seul
  auth-finish --projet SLUG                lit l'adresse de retour (ou « code state ») sur l'entree standard
  credit-set --projet SLUG 4.20            solde estime du credit X (obligatoire avant le premier post)
  resoudre --projet SLUG ID libre|publie TWEET_ID
  status --projet SLUG                     etat sans secret
  serve                                    boucle Telegram (callback_query seulement), tous projets
  selftest                                 tests hors ligne

Dossier racine : $PUBLISH_BUTTON_HOME (defaut ~/.publish-button) : config.json, projets.json, sujets.json,
secrets/<projet>/ (chmod 700 : x_app.json, x_tokens.json), state/<projet>/.
Jeton du bot : variable TELEGRAM_BOT_TOKEN, sinon secrets/bot.env (TELEGRAM_BOT_TOKEN=...). Jamais affiche.
Dossier de travail d'un projet : posts.txt (posts separes par une ligne ---), suivi.json, visuels/.
"""
import base64
import fcntl
import hashlib
import html
import json
import mimetypes
import os
import re
import secrets
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
from datetime import datetime
from pathlib import Path

BASE = Path(os.environ.get("PUBLISH_BUTTON_HOME", str(Path.home() / ".publish-button")))
API = "https://api.x.com"
REDIRECT_URI = "http://127.0.0.1:8765/callback"
SCOPES = "tweet.read tweet.write users.read media.write offline.access"
MAX_CHARS = 280
LIEN = re.compile(r"(://|www\.|\b[a-z0-9-]+\.[a-z]{2,24}\b)", re.I)
SLUG = re.compile(r"[a-z][a-z0-9-]{1,15}")
DEFAUTS = {"cout_post_usd": 0.015, "marge_media_usd": 0.010, "seuil_arret_usd": 1.00,
           "pause_min_s": 60, "refuser_liens": True}

# Projet courant (choisir() les bascule)
PROJET, COMPTE, AFFICHE = "", "", ""
SECRETS, STATE, WORK = BASE / "secrets", BASE / "state", BASE


def log(*a) -> None:
    print(datetime.now().isoformat(timespec="seconds"), *a, flush=True)


# ---------------------------------------------------------------- fichiers

def lire_json(p: Path, defaut=None):
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return defaut


def ecrire_json(p: Path, data, secret: bool = False) -> None:
    """Ecriture atomique (fsync) ; chmod 600 si secret, avec l'ancienne version en .prev."""
    p.parent.mkdir(parents=True, exist_ok=True, mode=0o700 if secret else 0o755)
    tmp = p.with_suffix(p.suffix + ".tmp")
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600 if secret else 0o644)
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=1)
        f.flush()
        os.fsync(f.fileno())
    if secret and p.exists():
        prev = p.with_suffix(p.suffix + ".prev")
        prev.write_bytes(p.read_bytes())
        os.chmod(prev, 0o600)
    os.replace(tmp, p)


def lire_env(p: Path) -> dict:
    out = {}
    if not p.exists():
        return out
    for ligne in p.read_text(encoding="utf-8", errors="replace").splitlines():
        ligne = ligne.strip()
        if ligne and not ligne.startswith("#") and "=" in ligne:
            k, v = ligne.split("=", 1)
            out[k.strip().removeprefix("export ").strip()] = v.strip().strip("\"'")
    return out


class Verrou:
    """Verrou de fichier : une seule modification d'etat a la fois."""
    def __init__(self, dossier: Path, nom: str) -> None:
        dossier.mkdir(parents=True, exist_ok=True)
        self.f = open(dossier / nom, "a+")

    def __enter__(self):
        fcntl.flock(self.f, fcntl.LOCK_EX)
        return self

    def __exit__(self, *a):
        fcntl.flock(self.f, fcntl.LOCK_UN)
        self.f.close()


def config() -> dict:
    c = lire_json(BASE / "config.json")
    if not c or not c.get("groupe") or not c.get("autorises"):
        raise RuntimeError(f"{BASE / 'config.json'} absent ou incomplet (groupe, autorises)")
    return {**DEFAUTS, **c}


def projets() -> dict:
    return lire_json(BASE / "projets.json", {}) or {}


def choisir(slug: str) -> None:
    """Bascule chemins et compte sur ce projet."""
    global PROJET, COMPTE, AFFICHE, SECRETS, STATE, WORK
    p = projets().get(slug)
    if not p:
        raise KeyError(f"projet inconnu : {slug}")
    PROJET, COMPTE, AFFICHE = slug, p["compte"].lower(), "@" + p["compte"]
    SECRETS, STATE, WORK = BASE / "secrets" / slug, BASE / "state" / slug, Path(p["travail"])


# ---------------------------------------------------------------- HTTP

class Incertain(Exception):
    """L'appel de creation a pu aboutir sans qu'on le sache."""


class ErreurHttp(Exception):
    def __init__(self, code: int, detail: str, definitif: bool) -> None:
        super().__init__(f"HTTP {code}: {detail}")
        self.code, self.detail, self.definitif = code, detail, definitif


def http(methode: str, url: str, *, headers=None, corps: bytes | None = None, timeout=60) -> dict:
    """Retourne le JSON. Les erreurs ne contiennent jamais l'URL (le jeton Telegram y figure)."""
    req = urllib.request.Request(url, data=corps, method=methode, headers=headers or {})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            brut = r.read().decode("utf-8", "replace")
            return json.loads(brut) if brut.strip() else {}
    except urllib.error.HTTPError as e:
        brut = e.read().decode("utf-8", "replace")[:400]
        raise ErreurHttp(e.code, re.sub(r"\s+", " ", brut), definitif=e.code < 500) from None
    except Exception as e:  # delai, DNS, coupure : on ne sait pas si le serveur a agi
        raise ErreurHttp(0, type(e).__name__, definitif=False) from None


def multipart(champs: dict, fichier: tuple[str, str, bytes, str] | None = None) -> tuple[bytes, str]:
    b = uuid.uuid4().hex
    corps = b""
    for k, v in champs.items():
        corps += f'--{b}\r\nContent-Disposition: form-data; name="{k}"\r\n\r\n{v}\r\n'.encode()
    if fichier:
        champ, nom, data, ctype = fichier
        corps += (f'--{b}\r\nContent-Disposition: form-data; name="{champ}"; filename="{nom}"\r\n'
                  f"Content-Type: {ctype}\r\n\r\n").encode() + data + b"\r\n"
    corps += f"--{b}--\r\n".encode()
    return corps, f"multipart/form-data; boundary={b}"


# ---------------------------------------------------------------- Telegram

def jeton_bot() -> str:
    t = os.environ.get("TELEGRAM_BOT_TOKEN") or lire_env(BASE / "secrets" / "bot.env").get("TELEGRAM_BOT_TOKEN", "")
    if not t:
        raise RuntimeError("jeton du bot absent (TELEGRAM_BOT_TOKEN ou secrets/bot.env)")
    return t


class Tg:
    def __init__(self, sans_config: bool = False) -> None:
        self.token = jeton_bot()
        c = {} if sans_config else config()
        self.groupe = str(c.get("groupe", ""))
        self.autorises = {str(x) for x in c.get("autorises", [])}

    def appel(self, methode: str, **champs) -> dict:
        try:
            return http("POST", f"https://api.telegram.org/bot{self.token}/{methode}",
                        headers={"Content-Type": "application/json"}, corps=json.dumps(champs).encode(), timeout=70)
        except ErreurHttp as e:
            return {"ok": False, "code": e.code, "description": e.detail}


def sujet(tg: Tg, slug: str, nom: str | None = None) -> int:
    """Numero du sujet du groupe ; le cree s'il manque (le bot doit pouvoir gerer les sujets)."""
    with Verrou(BASE, ".sujets.lock"):
        s = lire_json(BASE / "sujets.json", {}) or {}
        if slug in s:
            return int(s[slug]["id"])
        nom = nom or (projets().get(slug) or {}).get("nom") or slug.capitalize()
        r = tg.appel("createForumTopic", chat_id=tg.groupe, name=nom)
        if not r.get("ok"):
            raise RuntimeError(f"creation du sujet {slug} refusee : {r.get('description')}")
        s[slug] = {"id": r["result"]["message_thread_id"], "nom": nom}
        ecrire_json(BASE / "sujets.json", s)
        return int(s[slug]["id"])


def info(tg: Tg, slug: str, texte: str, sonne: bool = False) -> dict:
    """Regle commune : une simple information part sans sonnerie ; sonne=True si un geste est attendu."""
    return tg.appel("sendMessage", chat_id=tg.groupe, message_thread_id=sujet(tg, slug), text=texte[:4096],
                    disable_notification=not sonne, disable_web_page_preview=True)


# ---------------------------------------------------------------- OAuth 2.0 (X)

def app_x() -> dict:
    a = lire_json(SECRETS / "x_app.json")
    if not a or not a.get("client_id"):
        raise RuntimeError(f"{SECRETS / 'x_app.json'} absent : client_id et client_secret de l'app X manquants")
    return a


def entete_basic(a: dict) -> str:
    return "Basic " + base64.b64encode(f"{a['client_id']}:{a.get('client_secret', '')}".encode()).decode()


def pkce_nouveau() -> tuple[str, str, str]:
    verifier = base64.urlsafe_b64encode(secrets.token_bytes(48)).decode().rstrip("=")
    challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).decode().rstrip("=")
    return verifier, challenge, secrets.token_urlsafe(24)


def cmd_auth_url(ecoute: bool = False) -> None:
    a = app_x()
    verifier, challenge, state = pkce_nouveau()
    ecrire_json(SECRETS / "pkce.json", {"verifier": verifier, "state": state, "ts": time.time()}, secret=True)
    q = urllib.parse.urlencode({
        "response_type": "code", "client_id": a["client_id"], "redirect_uri": REDIRECT_URI,
        "scope": SCOPES, "state": state, "code_challenge": challenge, "code_challenge_method": "S256"},
        quote_via=urllib.parse.quote)
    print("https://x.com/i/oauth2/authorize?" + q, flush=True)
    if ecoute:
        print("en attente du retour de X sur", REDIRECT_URI, "(15 min au plus)", flush=True)
        finir_auth(*code_et_state(attendre_retour()))


def attendre_retour(port: int = 8765, delai: float = 900) -> str:
    """Attend la redirection de X sur 127.0.0.1 et retourne son chemin (le code ne vit que 30 s)."""
    from http.server import BaseHTTPRequestHandler, HTTPServer
    recu = []

    class Retour(BaseHTTPRequestHandler):
        def do_GET(self):
            if not self.path.startswith("/callback"):
                self.send_response(404)
                self.end_headers()
                return
            recu.append(self.path)
            self.send_response(200)
            self.send_header("Content-Type", "text/plain; charset=utf-8")
            self.end_headers()
            self.wfile.write("Autorisation reçue, retour au terminal.".encode())

        def log_message(self, *a):
            pass

    fin = time.time() + delai
    try:
        srv = HTTPServer(("127.0.0.1", port), Retour)
    except OSError:
        sys.exit(f"port {port} deja pris sur 127.0.0.1 : liberer ce port, ou utiliser auth-url puis auth-finish")
    with srv:
        srv.timeout = 5
        while not recu and time.time() < fin:
            srv.handle_request()
    if not recu:
        sys.exit("aucun retour de X : relancer auth-url --ecoute")
    return recu[0]


def code_et_state(texte: str) -> tuple[str, str]:
    """Accepte l'adresse de retour complete (ou son chemin) ou « code state »."""
    texte = texte.strip()
    if "code=" in texte:
        q = urllib.parse.parse_qs(urllib.parse.urlsplit(texte).query)
        if "error" in q:
            sys.exit(f"autorisation refusee sur X : {q['error'][0]}")
        if q.get("code") and q.get("state"):
            return q["code"][0], q["state"][0]
    parts = texte.split()
    if len(parts) != 2:
        sys.exit("entree attendue : l'adresse de retour complete, ou « code state »")
    return parts[0], parts[1]


def jeton_requete(donnees: dict) -> dict:
    return http("POST", f"{API}/2/oauth2/token",
                headers={"Content-Type": "application/x-www-form-urlencoded", "Authorization": entete_basic(app_x())},
                corps=urllib.parse.urlencode(donnees).encode())


def enregistrer_jetons(rep: dict, ancien: dict | None = None) -> dict:
    t = dict(ancien or {})
    t["access_token"] = rep["access_token"]
    t["refresh_token"] = rep.get("refresh_token") or t.get("refresh_token", "")
    t["expires_at"] = time.time() + int(rep.get("expires_in", 7200))
    ecrire_json(SECRETS / "x_tokens.json", t, secret=True)
    return t


def cmd_auth_finish() -> None:
    finir_auth(*code_et_state(sys.stdin.read()))


def finir_auth(code: str, state: str) -> None:
    p = lire_json(SECRETS / "pkce.json")
    if not p or p["state"] != state:
        sys.exit("state inconnu : relancer auth-url")
    if time.time() - p["ts"] > 900:
        sys.exit("autorisation trop ancienne : relancer auth-url")
    try:
        rep = jeton_requete({"grant_type": "authorization_code", "code": code, "redirect_uri": REDIRECT_URI,
                             "code_verifier": p["verifier"], "client_id": app_x()["client_id"]})
    except ErreurHttp as e:
        sys.exit(f"echange refuse par X (HTTP {e.code}) : code expire (30 s), callback ou client secret faux. "
                 "Relancer auth-url --ecoute")
    if "access_token" not in rep:
        sys.exit("echange refuse")
    moi = http("GET", f"{API}/2/users/me", headers={"Authorization": "Bearer " + rep["access_token"]})["data"]
    if moi.get("username", "").lower() != COMPTE:
        sys.exit(f"MAUVAIS COMPTE : {moi.get('username')} au lieu de {AFFICHE}. Rien enregistre.")
    t = enregistrer_jetons(rep)
    t["user_id"], t["username"] = moi["id"], moi["username"]
    ecrire_json(SECRETS / "x_tokens.json", t, secret=True)
    (SECRETS / "pkce.json").unlink(missing_ok=True)
    print("compte verifie :", moi["username"])


def jeton_valide() -> str:
    """Access token valide, rafraichi si besoin (le refresh token tourne : re-ecrit tout de suite)."""
    with Verrou(STATE, "jetons.lock"):
        t = lire_json(SECRETS / "x_tokens.json")
        if not t or t.get("username", "").lower() != COMPTE:
            raise RuntimeError(f"X non connecte pour {AFFICHE} (auth-url puis auth-finish)")
        if t["expires_at"] - 600 > time.time():
            return t["access_token"]
        try:
            rep = jeton_requete({"grant_type": "refresh_token", "refresh_token": t["refresh_token"],
                                 "client_id": app_x()["client_id"]})
        except ErreurHttp as e:
            if e.code == 0:  # coupure : on pourra reessayer
                raise
            raise RuntimeError("rafraichissement refuse : refaire l'autorisation") from None
        if "access_token" not in rep:
            raise RuntimeError("rafraichissement refuse : refaire l'autorisation")
        return enregistrer_jetons(rep, t)["access_token"]


# ---------------------------------------------------------------- posts, credit, etat

def charger_posts() -> list[dict]:
    textes = [p.strip() for p in (WORK / "posts.txt").read_text(encoding="utf-8").split("\n---\n") if p.strip()]
    suivi = json.loads((WORK / "suivi.json").read_text(encoding="utf-8"))["posts"]
    if len(textes) != len(suivi):
        raise ValueError("posts.txt et suivi.json ne correspondent pas")
    return [dict(m, texte=t) for t, m in zip(textes, suivi)]


def poids(t: str) -> int:
    """Longueur comptee comme X : 1 par caractere latin courant, 2 pour emoji, CJK et autres."""
    n = 0
    for c in t:
        o = ord(c)
        n += 1 if (o <= 0x10FF or 0x2000 <= o <= 0x200D or 0x2010 <= o <= 0x201F or 0x2032 <= o <= 0x2037) else 2
    return n


def empreinte(p: dict) -> str:
    """12 hex qui lient le texte et le visuel : le bouton ne vaut que pour ce qui a ete envoye."""
    h = hashlib.sha256(p["texte"].encode("utf-8") + b"\0" + str(p.get("visuel")).encode())
    if p.get("visuel"):
        f = WORK / "visuels" / p["visuel"]
        h.update(f.read_bytes() if f.exists() else b"absent")
    return h.hexdigest()[:12]


def controle_post(p: dict, c: dict) -> str | None:
    """Motif de refus, ou None si le post peut partir."""
    if p.get("bloque"):
        return "bloqué : " + p.get("bloque_motif", "feu vert attendu")
    if poids(p["texte"]) > MAX_CHARS:
        return f"texte trop long ({poids(p['texte'])}/{MAX_CHARS})"
    if c["refuser_liens"] and LIEN.search(p["texte"]):
        return "le texte contient un lien (refuser_liens dans config.json)"
    return None


def etat_lire() -> dict:
    return lire_json(STATE / "etat.json", {}) or {}


def etat_ecrire(e: dict) -> None:
    ecrire_json(STATE / "etat.json", e)


def credit_lire() -> float | None:
    c = lire_json(STATE / "credit.json")
    return float(c["solde_usd"]) if c and "solde_usd" in c else None


def credit_ecrire(v: float) -> None:
    ecrire_json(STATE / "credit.json", {"solde_usd": round(v, 4), "maj": datetime.now().isoformat(timespec="seconds")})


def cout(p: dict, c: dict) -> float:
    return c["cout_post_usd"] + (c["marge_media_usd"] if p.get("visuel") else 0)


def reserver(p: dict, c: dict) -> str | None:
    """Passe le post a « en_cours » sous verrou. Motif de refus ou None."""
    with Verrou(STATE, "etat.lock"):
        e = etat_lire()
        cur = e.get(str(p["id"]), {})
        if cur.get("etat") == "publie":
            return f"déjà publié : {cur.get('url')}"
        if cur.get("etat") in ("en_cours", "incertain"):
            return f"état incertain : une publication a peut-être déjà eu lieu. Vérifie le profil {AFFICHE}."
        derniere = max([v.get("ts", 0) for v in e.values()] or [0])
        if time.time() - derniere < c["pause_min_s"]:
            return f"trop rapproché : attends {int(c['pause_min_s'] - (time.time() - derniere))} s"
        solde = credit_lire()
        if solde is None:
            return "solde du crédit X jamais saisi (credit-set) : publication refusée par prudence"
        if solde - cout(p, c) < c["seuil_arret_usd"]:
            return f"crédit X estimé à {solde:.2f} $ : arrêt sous {c['seuil_arret_usd']:.2f} $"
        if p.get("reply_to") and e.get(str(p["reply_to"]), {}).get("etat") != "publie":
            return f"c'est une réponse au post {p['reply_to']}, qui n'est pas encore publié"
        e[str(p["id"])] = {"etat": "en_cours", "ts": time.time()}
        etat_ecrire(e)
    return None


def conclure(pid: int, **champs) -> None:
    with Verrou(STATE, "etat.lock"):
        e = etat_lire()
        e[str(pid)] = dict(e.get(str(pid), {}), ts=time.time(), **champs)
        etat_ecrire(e)


# ---------------------------------------------------------------- X : media + post

def televerser(visuel: Path, jeton: str) -> str:
    """Upload v2 : image en un coup, GIF en trois temps (initialize, append, finalize)."""
    data = visuel.read_bytes()
    gif = visuel.suffix.lower() == ".gif"
    ctype = mimetypes.guess_type(visuel.name)[0] or "application/octet-stream"
    cat = "tweet_gif" if gif else "tweet_image"
    if len(data) > (15 if gif else 5) * 1024 * 1024:
        raise RuntimeError("visuel trop lourd pour X")
    h = {"Authorization": "Bearer " + jeton}
    if not gif:
        corps, ct = multipart({"media_category": cat}, ("media", visuel.name, data, ctype))
        return http("POST", f"{API}/2/media/upload", headers=dict(h, **{"Content-Type": ct}), corps=corps)["data"]["id"]
    ini = http("POST", f"{API}/2/media/upload/initialize", headers=dict(h, **{"Content-Type": "application/json"}),
               corps=json.dumps({"total_bytes": len(data), "media_type": ctype, "media_category": cat}).encode())
    mid = ini["data"]["id"]
    taille = 1024 * 1024
    for i in range(0, len(data), taille):
        corps, ct = multipart({"segment_index": i // taille}, ("media", visuel.name, data[i:i + taille], ctype))
        http("POST", f"{API}/2/media/upload/{mid}/append", headers=dict(h, **{"Content-Type": ct}), corps=corps)
    fin = http("POST", f"{API}/2/media/upload/{mid}/finalize", headers=h)
    info_t = (fin.get("data") or {}).get("processing_info")
    for _ in range(6):
        if not info_t or info_t.get("state") in (None, "succeeded"):
            break
        if info_t.get("state") == "failed":
            raise RuntimeError("X a refusé le GIF")
        time.sleep(min(int(info_t.get("check_after_secs", 2)), 10))
        st = http("GET", f"{API}/2/media/upload?command=STATUS&media_id={mid}", headers=h)
        info_t = (st.get("data") or {}).get("processing_info")
    return mid


def poser_alt(mid: str, alt: str, jeton: str) -> None:
    """Texte alternatif (jamais bloquant : en cas d'echec le post part sans)."""
    try:
        http("POST", f"{API}/2/media/metadata", headers={"Authorization": "Bearer " + jeton, "Content-Type": "application/json"},
             corps=json.dumps({"id": mid, "metadata": {"alt_text": {"text": alt[:1000]}}}).encode(), timeout=30)
    except Exception as e:
        log("texte alternatif non pose :", type(e).__name__)


def publier(p: dict, reply_id: str | None = None) -> dict:
    """SEULE fonction qui ecrit sur X. Retourne {'id', 'url'}. Etat deja reserve par l'appelant."""
    jeton = jeton_valide()
    corps = {"text": p["texte"]}
    if p.get("visuel"):
        mid = televerser(WORK / "visuels" / p["visuel"], jeton)
        if p.get("alt"):
            poser_alt(mid, p["alt"], jeton)
        corps["media"] = {"media_ids": [mid]}
    if reply_id:
        corps["reply"] = {"in_reply_to_tweet_id": reply_id}
    jeton = jeton_valide()
    try:
        rep = http("POST", f"{API}/2/tweets", corps=json.dumps(corps).encode(),
                   headers={"Authorization": "Bearer " + jeton, "Content-Type": "application/json"})
        tid = rep["data"]["id"]
    except ErreurHttp as e:
        if not e.definitif:      # delai, coupure ou 5xx : le post a peut-etre ete cree
            raise Incertain(e.detail) from None
        raise
    except (KeyError, TypeError):
        raise Incertain("réponse de X sans identifiant") from None
    return {"id": tid, "url": f"https://x.com/{COMPTE}/status/{tid}"}


def traiter_publication(pid: int, h: str, texte_message: str) -> tuple[bool, str, str | None]:
    """Coeur du bouton. Rien ne part si ce qui est vu n'est pas ce qui serait publie."""
    c = config()
    try:
        p = next(x for x in charger_posts() if x["id"] == pid)
    except StopIteration:
        return False, "post inconnu", None
    except Exception as e:
        return False, f"Refusé : fichiers des posts illisibles ({type(e).__name__})", None
    refus = controle_post(p, c)
    if refus:
        return False, f"Refusé : {refus}", None
    if empreinte(p) != h or p["texte"] not in (texte_message or ""):
        return False, "Refusé : le post a changé depuis l'envoi de ce message. Renvoie-le.", None
    if (lire_json(SECRETS / "x_tokens.json") or {}).get("username", "").lower() != COMPTE:
        return False, f"Refusé : X n'est pas encore connecté à {AFFICHE}.", None
    refus = reserver(p, c)
    if refus:
        return False, f"Refusé : {refus}", None
    reply_id = None
    if p.get("reply_to"):
        reply_id = etat_lire().get(str(p["reply_to"]), {}).get("tweet_id")
        if not reply_id:
            conclure(pid, etat="echec", detail="parent sans tweet_id")
            return False, "Refusé : l'identifiant du post parent est inconnu.", None
    try:
        r = publier(p, reply_id)
    except Incertain as e:
        conclure(pid, etat="incertain", detail=str(e)[:100])
        credit_ecrire((credit_lire() or 0) - cout(p, c))
        return False, (f"Réponse de X perdue : le post est peut-être parti. Ne retouche pas le bouton : "
                       f"regarde {AFFICHE}, puis « resoudre » (libre ou publie)."), None
    except ErreurHttp as e:
        conclure(pid, etat="echec", detail=f"HTTP {e.code}")
        if e.code == 0:
            return False, f"Connexion à X impossible ({e.detail}). Rien n'est publié, tu peux réessayer.", None
        return False, f"X a refusé (HTTP {e.code}) : {e.detail[:200]}. Rien n'est publié, tu peux réessayer.", None
    except Exception as e:
        conclure(pid, etat="echec", detail=type(e).__name__)
        motif = str(e)[:150] if isinstance(e, RuntimeError) else type(e).__name__
        return False, f"Échec avant publication ({motif}). Rien n'est publié, tu peux réessayer.", None
    conclure(pid, etat="publie", tweet_id=r["id"], url=r["url"])
    credit_ecrire((credit_lire() or 0) - cout(p, c))
    log("publie", PROJET, "post", pid, r["id"])
    try:
        maj_suivi(pid, r["url"])
    except Exception as e:  # le post est parti : ne jamais perdre la confirmation
        log("maj_suivi echec", type(e).__name__)
    return True, f"Publié sur {AFFICHE} (post {pid}).", r["url"]


def maj_suivi(pid: int, url: str) -> None:
    f = WORK / "suivi.json"
    with Verrou(STATE, "suivi.lock"):
        s = json.loads(f.read_text(encoding="utf-8"))
        for p in s["posts"]:
            if p["id"] == pid:
                p["statut"], p["publie"], p["url"] = "publie", datetime.now().isoformat(timespec="seconds"), url
        ecrire_json(f, s)


# ---------------------------------------------------------------- bouton

def traiter_callback(tg: Tg, cb: dict, sujet_de=None) -> None:
    """Bouton pub:<projet>:<id>:<empreinte>, accepte seulement dans le sujet de ce projet."""
    sujet_de = sujet_de or (lambda slug: sujet(tg, slug))
    de, msg = str(cb.get("from", {}).get("id")), cb.get("message") or {}
    chat = str(msg.get("chat", {}).get("id"))
    if de not in tg.autorises or chat != tg.groupe:
        log("callback refuse (expediteur ou chat non autorise)")
        tg.appel("answerCallbackQuery", callback_query_id=cb["id"], text="Non autorisé")
        return
    m = re.fullmatch(r"pub:([a-z][a-z0-9-]{1,15}):(\d{1,4}):([0-9a-f]{12})", cb.get("data", ""))
    if not m or not msg.get("message_id") or m.group(1) not in projets():
        tg.appel("answerCallbackQuery", callback_query_id=cb["id"], text="Bouton périmé : renvoie le post")
        return
    slug, pid, h = m.group(1), int(m.group(2)), m.group(3)
    fil = msg.get("message_thread_id") if msg.get("is_topic_message") else None
    if fil != sujet_de(slug):
        log("callback refuse (bouton hors du sujet du projet)", slug)
        tg.appel("answerCallbackQuery", callback_query_id=cb["id"], text="Bouton hors du sujet du projet")
        return
    choisir(slug)
    tg.appel("answerCallbackQuery", callback_query_id=cb["id"], text="Publication en cours...")
    ok, texte, url = traiter_publication(pid, h, msg.get("text") or msg.get("caption") or "")
    ou = {"chat_id": chat, "message_thread_id": fil}
    if ok and url:
        tg.appel("editMessageReplyMarkup", chat_id=chat, message_id=msg["message_id"],
                 reply_markup={"inline_keyboard": [[{"text": "Voir le post publié", "url": url}]]})
        tg.appel("sendMessage", **ou, text=f"{texte}\n{url}", reply_to_message_id=msg["message_id"],
                 disable_web_page_preview=True)
    else:
        tg.appel("sendMessage", **ou, text=texte, reply_to_message_id=msg["message_id"])


def cmd_serve() -> None:
    tg = Tg()
    log("service demarre ; projets :", ", ".join(projets()) or "aucun")
    offset, conflits = None, 0
    # Touchers faits pendant une panne : ecartes (il suffit de retoucher), jamais publies des heures apres.
    vieux = tg.appel("getUpdates", offset=-1, timeout=0, allowed_updates=["callback_query"])
    if vieux.get("ok") and vieux.get("result"):
        offset = vieux["result"][-1]["update_id"] + 1
    while True:
        champs = {"timeout": 50, "allowed_updates": ["callback_query"]}
        if offset:
            champs["offset"] = offset
        rep = tg.appel("getUpdates", **champs)
        if not rep.get("ok"):
            if rep.get("code") == 409:
                conflits += 1
                log("CONFLIT getUpdates : un autre processus lit ce bot (", conflits, ")")
                time.sleep(60)
            else:
                log("getUpdates erreur", rep.get("code"), str(rep.get("description"))[:100])
                time.sleep(10)
            continue
        conflits = 0
        for u in rep.get("result", []):
            offset = u["update_id"] + 1
            if "callback_query" in u:
                try:
                    traiter_callback(tg, u["callback_query"])
                except Exception as e:
                    log("erreur callback", type(e).__name__, str(e)[:120])


# ---------------------------------------------------------------- envoi des posts

def legende_post(p: dict, total: int, note: str = "") -> str:
    prevu = p.get("prevu") or "?"
    tete = f"Post {p['id']}/{total} : à publier le {prevu}"
    if p.get("theme"):
        tete += f" ({html.escape(p['theme'], quote=False)})"
    if p.get("bloque"):
        tete += f"\nBLOQUÉ : {html.escape(p.get('bloque_motif', 'feu vert attendu'), quote=False)}"
    if note:
        tete += f"\n{html.escape(note, quote=False)}"
    return f"{tete}\n<pre>{html.escape(p['texte'], quote=False)}</pre>"


def envoyer_post(tg: Tg, p: dict, total: int, note: str = "", silencieux: bool = False) -> dict:
    """Un message par post dans le sujet du projet ; il sonne (un geste est attendu) sauf --silencieux."""
    legende = legende_post(p, total, note)
    champs = {"chat_id": tg.groupe, "message_thread_id": sujet(tg, PROJET), "parse_mode": "HTML"}
    if silencieux:
        champs["disable_notification"] = True
    if not p.get("bloque") and p.get("statut") != "publie":
        champs["reply_markup"] = {"inline_keyboard": [[{
            "text": "Publier sur X", "callback_data": f"pub:{PROJET}:{p['id']}:{empreinte(p)}"}]]}
    v = p.get("visuel")
    if not v:
        return tg.appel("sendMessage", text=legende, disable_web_page_preview=True, **champs)
    chemin = WORK / "visuels" / v
    if not chemin.exists():
        return {"ok": False, "description": f"visuel absent : {v}"}
    if len(legende) > 1024:
        return {"ok": False, "description": f"légende trop longue ({len(legende)} > 1024)"}
    gif = v.lower().endswith(".gif")
    plats = {k: (json.dumps(x) if isinstance(x, dict) else x) for k, x in champs.items()}
    plats["caption"] = legende
    corps, ct = multipart(plats, ("animation" if gif else "photo", chemin.name, chemin.read_bytes(),
                                  mimetypes.guess_type(chemin.name)[0] or "application/octet-stream"))
    try:
        return http("POST", f"https://api.telegram.org/bot{tg.token}/{'sendAnimation' if gif else 'sendPhoto'}",
                    headers={"Content-Type": ct}, corps=corps, timeout=120)
    except ErreurHttp as e:
        return {"ok": False, "code": e.code, "description": e.detail}


def cmd_envoyer(a: list, tg: Tg | None = None) -> None:
    posts = charger_posts()
    journal = WORK / "telegram_envois.json"
    j = lire_json(journal, []) or []
    cible = a[0] if a and not a[0].startswith("--") else "tout"
    ids = [p["id"] for p in posts] if cible == "tout" else [int(x) for x in cible.split(",")]
    if "--renvoyer" not in a:
        deja = {e["post"] for e in j}
        ids = [i for i in ids if i not in deja]
    note = a[a.index("--note") + 1] if "--note" in a else ""
    tg = tg or Tg()
    for p in posts:
        if p["id"] not in ids:
            continue
        r = envoyer_post(tg, p, len(posts), note, "--silencieux" in a)
        mid = (r.get("result") or {}).get("message_id")
        print("post", p["id"], "ok" if r.get("ok") else "ECHEC " + str(r.get("description"))[:200], "message_id=", mid)
        if r.get("ok"):
            j.append({"post": p["id"], "message_id": mid, "date": datetime.now().isoformat(timespec="seconds")})
            ecrire_json(journal, j)


def cmd_nouveau_projet(a: list, tg: Tg | None = None) -> None:
    if len(a) != 4 or not SLUG.fullmatch(a[0]):
        sys.exit('usage : nouveau-projet slug "Nom" compte_x /chemin/du/dossier')
    slug, nom, compte, dossier = a[0], a[1], a[2].lstrip("@"), a[3]
    with Verrou(BASE, ".projets.lock"):
        p = projets()
        if slug in p:
            sys.exit(f"projet déjà déclaré : {slug}")
        p[slug] = {"nom": nom, "compte": compte, "travail": dossier}
        (BASE / "secrets" / slug).mkdir(parents=True, exist_ok=True, mode=0o700)
        (BASE / "state" / slug).mkdir(parents=True, exist_ok=True)
        (Path(dossier) / "visuels").mkdir(parents=True, exist_ok=True)
        ecrire_json(BASE / "projets.json", p)
    n = sujet(tg or Tg(), slug, nom)
    print(f"projet {slug} déclaré ; sujet n° {n} ; reste : secrets/{slug}/x_app.json puis auth-url --projet {slug} --ecoute")


def cmd_ids(tg: Tg | None = None) -> None:
    """Identifiants des groupes et des personnes qui ont ecrit au bot recemment (installation)."""
    tg = tg or Tg(sans_config=True)
    r = tg.appel("getUpdates", timeout=0, allowed_updates=["message"])
    if not r.get("ok"):
        sys.exit(f"getUpdates refuse : {r.get('description')} (arreter « serve » pendant l'installation)")
    chats, gens = {}, {}
    for u in r.get("result", []):
        m = u.get("message") or {}
        c, f = m.get("chat") or {}, m.get("from") or {}
        if c.get("type") in ("group", "supergroup"):
            chats[c["id"]] = f"{c.get('title', '')} (sujets : {'oui' if c.get('is_forum') else 'non'})"
        if f.get("id") and not f.get("is_bot"):
            gens[f["id"]] = "@" + f["username"] if f.get("username") else f.get("first_name", "")
    if not chats and not gens:
        print("aucun message recu : ecrire un message dans le groupe, puis relancer")
    for i, t in chats.items():
        print("groupe", i, t)
    for i, t in gens.items():
        print("personne", i, t)


def cmd_verifier() -> None:
    tg = Tg()
    moi = tg.appel("getMe")
    if not moi.get("ok"):
        sys.exit("jeton du bot refusé par Telegram")
    m = tg.appel("getChatMember", chat_id=tg.groupe, user_id=moi["result"]["id"]).get("result") or {}
    ch = tg.appel("getChat", chat_id=tg.groupe).get("result") or {}
    print("bot :", "@" + moi["result"]["username"])
    print("groupe a sujets :", "oui" if ch.get("is_forum") else "NON (activer les sujets)")
    print("bot admin, gestion des sujets :", "oui" if m.get("can_manage_topics") else "NON (le nommer admin)")
    print("projets :", ", ".join(projets()) or "aucun")


def cmd_resoudre(a: list) -> None:
    pid, mode = a[0], a[1]
    with Verrou(STATE, "etat.lock"):
        e = etat_lire()
        if mode == "libre":
            e[pid] = {"etat": "libre", "ts": time.time()}
        elif mode == "publie" and len(a) == 3 and a[2].isdigit():
            e[pid] = {"etat": "publie", "tweet_id": a[2], "url": f"https://x.com/{COMPTE}/status/{a[2]}", "ts": time.time()}
        else:
            sys.exit("usage : resoudre ID libre | resoudre ID publie TWEET_ID")
        etat_ecrire(e)
    print("post", pid, "->", e[pid]["etat"])


def cmd_status() -> None:
    t = lire_json(SECRETS / "x_tokens.json") or {}
    print("projet :", PROJET, "- compte :", AFFICHE)
    print("app X :", "oui" if (SECRETS / "x_app.json").exists() else "non")
    print("compte autorise :", t.get("username", "aucun"))
    print("solde estime (USD) :", credit_lire())
    for k, v in sorted(etat_lire().items(), key=lambda kv: int(kv[0])):
        print("post", k, v.get("etat"), v.get("url", ""))


# ---------------------------------------------------------------- tests hors ligne

def cmd_selftest() -> None:
    import tempfile
    global BASE
    BASE = Path(tempfile.mkdtemp())
    ecrire_json(BASE / "config.json", {"groupe": "-100", "autorises": ["42"], "pause_min_s": 0})
    ecrire_json(BASE / "projets.json", {"demo": {"nom": "Demo", "compte": "DemoX", "travail": str(BASE / "w")}})
    choisir("demo")
    WORK.mkdir()
    (WORK / "posts.txt").write_text("Premier\n---\nSecond\n---\nVa sur exemple.com\n---\nBloque\n---\n" + "x" * 281, encoding="utf-8")
    (WORK / "suivi.json").write_text(json.dumps({"posts": [
        {"id": 1}, {"id": 2, "reply_to": 1}, {"id": 3}, {"id": 4, "bloque": True}, {"id": 5}]}), encoding="utf-8")
    c = config()
    P = {p["id"]: p for p in charger_posts()}
    assert "jamais saisi" in reserver(P[1], c)
    credit_ecrire(5.0)
    for url in ("bit.ly/x", "youtu.be/abc", "s.team", "https://x.com"):
        assert LIEN.search("va sur " + url), url
    assert not LIEN.search("Fin de phrase. Et la suite, MENU. Oui")
    assert poids("é«»") == 3 and poids("😀") == 2
    assert controle_post(P[1], c) is None and "lien" in controle_post(P[3], c)
    assert "bloqué" in controle_post(P[4], c) and "trop long" in controle_post(P[5], c)
    assert "pas encore publié" in reserver(P[2], c)
    assert reserver(P[1], c) is None and "incertain" in reserver(P[1], c)
    conclure(1, etat="publie", tweet_id="111", url="u")
    assert "déjà publié" in reserver(P[1], c)
    credit_ecrire(1.01)
    P[2].pop("reply_to")
    assert "crédit" in reserver(P[2], c)
    v, ch, _ = pkce_nouveau()
    assert base64.urlsafe_b64encode(hashlib.sha256(v.encode()).digest()).decode().rstrip("=") == ch
    print("selftest OK")


def main(argv: list | None = None) -> None:
    a = list(sys.argv[1:] if argv is None else argv)
    if "--projet" in a:
        i = a.index("--projet")
        choisir(a[i + 1])
        del a[i:i + 2]
    if not a:
        sys.exit(__doc__)
    cmd, reste = a[0], a[1:]
    if cmd == "nouveau-projet":
        cmd_nouveau_projet(reste)
    elif cmd == "sujet" and reste:
        print(sujet(Tg(), reste[0], reste[1] if len(reste) > 1 else None))
    elif cmd == "info" and len(reste) >= 2:
        texte = sys.stdin.read() if reste[-1] == "-" else reste[-1]
        r = info(Tg(), reste[0], texte, sonne="--sonne" in reste[1:-1])
        print("ok" if r.get("ok") else "ECHEC " + str(r.get("description")))
    elif cmd == "credit-set" and len(reste) == 1 and PROJET:
        credit_ecrire(float(reste[0]))
        print("solde estime :", credit_lire())
    elif cmd == "resoudre" and len(reste) >= 2 and PROJET:
        cmd_resoudre(reste)
    elif cmd == "envoyer" and PROJET:
        cmd_envoyer(reste)
    elif cmd == "auth-url" and PROJET:
        cmd_auth_url("--ecoute" in reste)
    elif cmd in ("auth-finish", "status") and PROJET:
        {"auth-finish": cmd_auth_finish, "status": cmd_status}[cmd]()
    elif cmd in ("serve", "selftest", "verifier", "ids"):
        {"serve": cmd_serve, "selftest": cmd_selftest, "verifier": cmd_verifier, "ids": cmd_ids}[cmd]()
    else:
        sys.exit(__doc__)


if __name__ == "__main__":
    main()
