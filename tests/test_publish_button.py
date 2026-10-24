#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Test d'integration de publish_button.py avec un faux reseau : aucun appel reel a X ni a Telegram.
Usage : python3 tests/test_publish_button.py  (Linux ou macOS : le script utilise fcntl)"""
import json
import os
import sys
import tempfile
from pathlib import Path

d = Path(tempfile.mkdtemp())
os.environ["PUBLISH_BUTTON_HOME"] = str(d)
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
import publish_button as pb  # noqa: E402

pb.ecrire_json(d / "config.json", {"groupe": "-100", "autorises": ["42"], "pause_min_s": 0})
pb.ecrire_json(d / "projets.json", {
    "demo": {"nom": "Demo", "compte": "DemoX", "travail": str(d / "w-demo")},
    "autre": {"nom": "Autre", "compte": "AutreX", "travail": str(d / "w-autre")}})
pb.ecrire_json(d / "sujets.json", {"demo": {"id": 911, "nom": "Demo"}, "autre": {"id": 912, "nom": "Autre"}})
pb.choisir("demo")
(pb.WORK / "visuels").mkdir(parents=True)
(pb.WORK / "visuels" / "a.png").write_bytes(b"\x89PNG" + b"0" * 100)
(pb.WORK / "visuels" / "b.gif").write_bytes(b"GIF89a" + b"0" * 2_500_000)
TEXTES = ["Un", "Deux", "Trois", "Quatre bloque", "Cinq"]


def ecrire(textes=TEXTES):
    (pb.WORK / "posts.txt").write_text("\n---\n".join(textes) + "\n", encoding="utf-8")
    (pb.WORK / "suivi.json").write_text(json.dumps({"posts": [
        {"id": 1, "visuel": "a.png", "alt": "Texte alt un"}, {"id": 2, "visuel": "b.gif", "reply_to": 1, "alt": "Alt deux"},
        {"id": 3, "visuel": None}, {"id": 4, "visuel": None, "bloque": True}, {"id": 5, "visuel": None}]}), encoding="utf-8")


ecrire()
appels, corps_tweets, alts = [], [], []
mode = {"tweets": "ok"}


def faux_http(methode, url, *, headers=None, corps=None, timeout=60):
    assert "api.telegram.org" not in url, "Telegram doit passer par FauxTg"
    appels.append((methode, url.replace("https://api.x.com", "X").split("?")[0]))
    if url.endswith("/2/media/metadata"):
        alts.append(json.loads(corps))
        if mode.get("alt") == "echec":
            raise pb.ErreurHttp(400, "Bad Request", definitif=True)
        return {}
    if url.endswith("/2/media/upload"):
        return {"data": {"id": "900"}}
    if url.endswith("/initialize"):
        return {"data": {"id": "901"}}
    if url.endswith("/append"):
        return {}
    if url.endswith("/finalize"):
        return {"data": {"id": "901"}}
    if url.endswith("/2/tweets"):
        if mode["tweets"] == "coupure":
            raise pb.ErreurHttp(0, "TimeoutError", definitif=False)
        if mode["tweets"] == "500":
            raise pb.ErreurHttp(503, "Service Unavailable", definitif=False)
        if mode["tweets"] == "400":
            raise pb.ErreurHttp(403, "Forbidden", definitif=True)
        if mode["tweets"] == "sansid":
            return {"data": {}}
        body = json.loads(corps)
        corps_tweets.append(body)
        return {"data": {"id": str(5000 + len(corps_tweets)), "text": body["text"]}}
    raise AssertionError(url)


pb.http = faux_http
pb.jeton_valide = lambda: "jeton-test"
pb.maj_suivi = lambda pid, url: None


def pub(pid, texte=None, h=None):
    p = next(x for x in pb.charger_posts() if x["id"] == pid)
    return pb.traiter_publication(pid, h or pb.empreinte(p), texte if texte is not None else "entete\n" + p["texte"])


ok, msg, _ = pub(1)
assert not ok and "pas encore connecté" in msg, msg          # X non autorise : refus
pb.ecrire_json(pb.SECRETS / "x_tokens.json", {"username": "DemoX", "access_token": "t", "expires_at": 9e12}, secret=True)
assert oct(os.stat(pb.SECRETS / "x_tokens.json").st_mode & 0o777) == "0o600"
ok, msg, _ = pub(1)
assert not ok and "jamais saisi" in msg, msg                 # solde jamais saisi : refus
pb.credit_ecrire(5.0)

ok, msg, url = pub(1)
assert ok and url == "https://x.com/demox/status/5001", (ok, msg, url)
assert corps_tweets[0]["media"] == {"media_ids": ["900"]}
assert alts == [{"id": "900", "metadata": {"alt_text": {"text": "Texte alt un"}}}], alts

n = len(appels)
ok, msg, _ = pub(1)                                          # deuxieme toucher : rien ne part
assert not ok and "déjà publié" in msg and len(appels) == n

mode["alt"] = "echec"                                        # texte alternatif refuse : le post part quand meme
ok, msg, url = pub(2)                                        # reponse + GIF en trois temps
mode["alt"] = "ok"
assert ok, msg
assert corps_tweets[1]["reply"] == {"in_reply_to_tweet_id": "5001"}
seq = [a[1] for a in appels if "media/upload" in a[1]][1:]
assert seq == ["X/2/media/upload/initialize"] + ["X/2/media/upload/901/append"] * 3 + ["X/2/media/upload/901/finalize"], seq

n = len(appels)
ok, msg, _ = pub(4)                                          # bloque
assert not ok and "bloqué" in msg and len(appels) == n

# empreinte et texte du message : ce qui est vu doit etre ce qui part
ok, msg, _ = pub(3, h="0" * 12)
assert not ok and "changé" in msg and len(appels) == n
ok, msg, _ = pub(3, texte="Autre texte")
assert not ok and "changé" in msg and len(appels) == n
ecrire(["Un", "Deux", "Trois MODIFIE", "Quatre bloque", "Cinq"])
ok, msg, _ = pub(3, h=pb.empreinte({"texte": "Trois", "visuel": None}), texte="Trois")
assert not ok and "changé" in msg and len(appels) == n
ecrire()


class FauxTg:
    groupe, autorises, token = "-100", {"42"}, "faux"

    def __init__(self):
        self.journal = []

    def appel(self, m, **c):
        self.journal.append((m, c))
        return {"ok": True, "result": {"message_id": 77, "message_thread_id": 950}}


def cb(tg, data, fil=911, chat="-100", user=42, mid=8, texte="Trois", sujet=True):
    msg = {"chat": {"id": chat}, "text": texte}
    if mid:
        msg["message_id"] = mid
    if sujet:
        msg.update(is_topic_message=True, message_thread_id=fil)
    pb.traiter_callback(tg, {"id": "c", "from": {"id": user}, "message": msg, "data": data})


h3 = pb.empreinte(next(x for x in pb.charger_posts() if x["id"] == 3))
tg, n = FauxTg(), len(appels)
cb(tg, f"pub:demo:3:{h3}", user=7)                           # mauvais expediteur
cb(tg, f"pub:demo:3:{h3}", chat="-555")                      # autre groupe
cb(tg, f"pub:demo:3:{h3}", chat="42")                        # conversation privee
cb(tg, "pub:3:" + h3)                                        # ancien format sans projet
cb(tg, f"pub:demo:3:{h3};rm")                                # donnee forgee
cb(tg, f"pub:inconnu:3:{h3}")                                # projet non declare
cb(tg, f"pub:demo:3:{h3}", fil=912)                          # bouton dans le sujet d'un autre projet
cb(tg, f"pub:demo:3:{h3}", sujet=False)                      # message hors sujet
cb(tg, f"pub:demo:3:{h3}", mid=0)                            # message inaccessible
assert len(appels) == n, "publication par un tiers ou sur un bouton perime"

cb(tg, f"pub:demo:3:{h3}")
assert len(appels) == n + 1 and any(m == "editMessageReplyMarkup" for m, _ in tg.journal)
envoi = [c for m, c in tg.journal if m == "sendMessage"][-1]
assert envoi["chat_id"] == "-100" and envoi["message_thread_id"] == 911, envoi
cb(tg, f"pub:demo:3:{h3}")                                   # deuxieme toucher
assert len(appels) == n + 1

# coupure, 5xx ou reponse sans id sur POST /2/tweets : etat incertain, aucun nouvel envoi
for nom in ("coupure", "500", "sansid"):
    mode["tweets"] = nom
    ok, msg, _ = pub(5)
    assert not ok and "peut-être parti" in msg, (nom, msg)
    ok, msg, _ = pub(5)
    assert not ok and "incertain" in msg, msg
    pb.cmd_resoudre(["5", "libre"])
mode["tweets"] = "400"                                       # refus net de X : on peut reessayer
ok, msg, _ = pub(5)
assert not ok and "Rien n'est publié" in msg, msg
mode["tweets"] = "ok"
ok, msg, url = pub(5)
assert ok, msg
pb.cmd_resoudre(["3", "publie", "777"])
assert pb.etat_lire()["3"]["tweet_id"] == "777"

# Envoi d'un post : bouton pub:<projet>:<id>:<empreinte>, dans le sujet du projet, 64 octets au plus
ecrire(["Un", "Deux", "Trois", "Quatre bloque", "Cinq", "Six"])
s = json.loads((pb.WORK / "suivi.json").read_text(encoding="utf-8"))
s["posts"].append({"id": 6, "visuel": None, "prevu": "2026-11-02", "theme": "<b>essai</b>"})
(pb.WORK / "suivi.json").write_text(json.dumps(s), encoding="utf-8")
tg = FauxTg()
pb.cmd_envoyer(["6", "--note", "remplace le précédent"], tg)
m, c = tg.journal[-1]
assert m == "sendMessage" and c["message_thread_id"] == 911 and "disable_notification" not in c, c
data = c["reply_markup"]["inline_keyboard"][0][0]["callback_data"]
assert data.startswith("pub:demo:6:") and len(data.encode()) <= 64, data
assert "&lt;b&gt;essai&lt;/b&gt;" in c["text"] and "<pre>Six</pre>" in c["text"], c["text"]
pb.cmd_envoyer(["6"], tg)                                    # deja envoye : rien
assert len(tg.journal) == 1
pb.cmd_envoyer(["4", "--silencieux"], tg)                    # bloque : sans bouton, sans sonnerie
m, c = tg.journal[-1]
assert "reply_markup" not in c and c["disable_notification"] is True, c

# Deuxieme projet : ses propres chemins, son propre compte
pb.choisir("autre")
assert pb.AFFICHE == "@AutreX" and pb.WORK == d / "w-autre" and pb.SECRETS == d / "secrets" / "autre"
ok, msg, _ = pb.traiter_publication(1, "0" * 12, "x")
assert not ok, msg

# Nouveau projet : declare, cree son sujet et ses dossiers
tg = FauxTg()
pb.cmd_nouveau_projet(["neuf", "Neuf", "@NeufX", str(d / "w-neuf")], tg)
assert tg.journal == [("createForumTopic", {"chat_id": "-100", "name": "Neuf"})], tg.journal
assert pb.projets()["neuf"] == {"nom": "Neuf", "compte": "NeufX", "travail": str(d / "w-neuf")}
assert json.loads((d / "sujets.json").read_text(encoding="utf-8"))["neuf"]["id"] == 950
assert (d / "w-neuf" / "visuels").is_dir() and oct(os.stat(d / "secrets" / "neuf").st_mode & 0o777) == "0o700"
assert pb.sujet(tg, "neuf") == 950 and len(tg.journal) == 1     # sujet deja connu : pas de seconde creation

# Autorisation X : adresse de retour collee, ou attente sur 127.0.0.1
assert pb.code_et_state("http://127.0.0.1:8765/callback?state=S1&code=C1\n") == ("C1", "S1")
assert pb.code_et_state("C2 S2") == ("C2", "S2")
import socket, threading, urllib.request  # noqa: E401,E402
with socket.socket() as so:
    so.bind(("127.0.0.1", 0))
    port = so.getsockname()[1]
threading.Timer(0.5, lambda: urllib.request.urlopen(f"http://127.0.0.1:{port}/callback?state=S3&code=C3", timeout=5).read()).start()
assert pb.code_et_state(pb.attendre_retour(port, delai=10)) == ("C3", "S3")

# Installation : ids lit les derniers messages et donne les identifiants
class FauxTgIds(FauxTg):
    def appel(self, m, **c):
        assert m == "getUpdates" and c["allowed_updates"] == ["message"]
        return {"ok": True, "result": [
            {"update_id": 1, "message": {"chat": {"id": -1009, "type": "supergroup", "title": "Equipe", "is_forum": True},
                                          "from": {"id": 42, "username": "moi"}}},
            {"update_id": 2, "message": {"chat": {"id": 42, "type": "private"}, "from": {"id": 42, "username": "moi"}}}]}


import contextlib, io  # noqa: E401,E402
sortie = io.StringIO()
with contextlib.redirect_stdout(sortie):
    pb.cmd_ids(FauxTgIds())
assert sortie.getvalue() == "groupe -1009 Equipe (sujets : oui)\npersonne 42 @moi\n", sortie.getvalue()

print("test d'integration OK ; appels X simules :", len(appels))
