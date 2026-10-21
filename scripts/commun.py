# -*- coding: utf-8 -*-
"""Fonctions partagées : configuration, chiffrement des données, lecture et écriture."""
import base64
import hashlib
import json
import os
import sys
from pathlib import Path

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

RACINE = Path(__file__).resolve().parent.parent
FICHIER_DONNEES = RACINE / "data" / "donnees.enc"


def config():
    return json.loads((RACINE / "scripts" / "config.json").read_text(encoding="utf-8"))


def mot_de_passe():
    mdp = os.environ.get("PS_MOT_DE_PASSE", "")
    if not mdp:
        sys.exit("Variable d'environnement PS_MOT_DE_PASSE manquante (mot de passe de l'espace statistiques).")
    return mdp


def cle_pour(mdp: str):
    site = config()["site"]
    return hashlib.pbkdf2_hmac("sha256", mdp.encode("utf-8"),
                               base64.b64decode(site["salt"]), int(site["iterations"]), dklen=32)


def cle():
    return cle_pour(mot_de_passe())


def chiffrer(cle_, clair: bytes) -> dict:
    iv = os.urandom(12)
    ct = AESGCM(cle_).encrypt(iv, clair, None)
    return {"iv": base64.b64encode(iv).decode(), "ct": base64.b64encode(ct).decode()}


def dechiffrer(cle_, iv: str, ct: str) -> bytes:
    return AESGCM(cle_).decrypt(base64.b64decode(iv), base64.b64decode(ct), None)


def lire_donnees(cle_=None):
    cle_ = cle_ or cle()
    enveloppe = json.loads(FICHIER_DONNEES.read_text(encoding="utf-8"))
    try:
        clair = dechiffrer(cle_, enveloppe["iv"], enveloppe["ct"])
    except Exception:
        sys.exit("Impossible de déchiffrer data/donnees.enc : mot de passe incorrect ?")
    return json.loads(clair.decode("utf-8"))


def ecrire_donnees(donnees, cle_=None):
    cle_ = cle_ or cle()
    donnees["months"] = sorted(donnees.get("months", []), key=lambda m: m["id"])
    clair = json.dumps(donnees, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    enveloppe = {"v": 1, **chiffrer(cle_, clair)}
    FICHIER_DONNEES.parent.mkdir(parents=True, exist_ok=True)
    FICHIER_DONNEES.write_text(json.dumps(enveloppe) + "\n", encoding="utf-8")
