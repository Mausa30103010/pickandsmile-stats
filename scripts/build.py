#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Construit les deux versions de la page à partir des données chiffrées.

  index.html          le site vu par le client (mois validés uniquement)
  apercu/index.html   la version d'aperçu (mois validés + mois en attente)

Usage : PS_MOT_DE_PASSE=... python3 scripts/build.py
"""
import base64
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from commun import RACINE, chiffrer, cle, config, lire_donnees  # noqa: E402

SRC = RACINE / "src"


def data_uri(chemin: Path, mime: str) -> str:
    return "data:%s;base64,%s" % (mime, base64.b64encode(chemin.read_bytes()).decode())


def polices() -> str:
    regles = []
    for poids in (400, 500, 600, 700):
        fichier = SRC / "fonts" / ("poppins-latin-%d-normal.woff2" % poids)
        regles.append('@font-face{font-family:"Poppins";font-style:normal;font-weight:%d;font-display:swap;'
                      'src:url(%s) format("woff2")}' % (poids, data_uri(fichier, "font/woff2")))
    return "\n".join(regles)


def page(donnees, cle_, mode: str) -> str:
    site = config()["site"]
    mois = donnees.get("months", [])
    if mode != "apercu":
        mois = [m for m in mois if m.get("status") == "published"]
    contenu = dict(donnees)
    contenu["months"] = sorted(mois, key=lambda m: m["id"])
    clair = json.dumps(contenu, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    charge = {"v": 1, "salt": site["salt"], "iter": int(site["iterations"]), **chiffrer(cle_, clair)}
    modele = (SRC / "template.html").read_text(encoding="utf-8")
    remplacements = {
        "__POLICES__": polices(),
        "__MASCOTTE__": data_uri(SRC / "img" / "mascotte.webp", "image/webp"),
        "__LOGO__": data_uri(SRC / "img" / "logo.webp", "image/webp"),
        "__MODE__": mode,
        "__CHARGE__": json.dumps(charge),
    }
    for cle_texte, valeur in remplacements.items():
        modele = modele.replace(cle_texte, valeur)
    return modele


def main():
    cle_ = cle()
    donnees = lire_donnees(cle_)
    (RACINE / "index.html").write_text(page(donnees, cle_, "site"), encoding="utf-8")
    (RACINE / "apercu").mkdir(exist_ok=True)
    (RACINE / "apercu" / "index.html").write_text(page(donnees, cle_, "apercu"), encoding="utf-8")
    publies = [m["id"] for m in donnees["months"] if m.get("status") == "published"]
    attente = [m["id"] for m in donnees["months"] if m.get("status") != "published"]
    print("index.html : %d mois publiés (%s)" % (len(publies), ", ".join(publies)))
    print("apercu/index.html : %d mois en attente (%s)" % (len(attente), ", ".join(attente) or "aucun"))


if __name__ == "__main__":
    main()
