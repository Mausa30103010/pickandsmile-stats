#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Gestion des données chiffrées du tableau de bord.

  resume                    liste des mois et de leur statut
  exporter FICHIER          écrit les données en clair dans FICHIER (à garder hors du dépôt)
  importer FICHIER          remplace les données par le contenu de FICHIER (après vérification)
  ajouter-mois FICHIER      ajoute ou remplace un mois (statut « draft » par défaut)
  publier AAAA-MM           rend le mois visible par le client
  retirer AAAA-MM           supprime un mois en attente
  verifier [FICHIER]        contrôle la structure et repère les textes restés à rédiger

Toutes les commandes lisent le mot de passe dans PS_MOT_DE_PASSE.
"""
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from commun import cle, ecrire_donnees, lire_donnees  # noqa: E402

A_REDIGER = "À RÉDIGER"


def textes(obj, chemin=""):
    if isinstance(obj, str):
        yield chemin, obj
    elif isinstance(obj, dict):
        for k, v in obj.items():
            yield from textes(v, chemin + "." + k if chemin else k)
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            yield from textes(v, "%s[%d]" % (chemin, i))


def controler(donnees):
    erreurs, alertes = [], []
    ids = [m.get("id") for m in donnees.get("months", [])]
    if len(ids) != len(set(ids)):
        erreurs.append("Mois en double : %s" % ids)
    for m in donnees.get("months", []):
        if not re.fullmatch(r"\d{4}-\d{2}", str(m.get("id", ""))):
            erreurs.append("Identifiant de mois invalide : %r" % m.get("id"))
        if m.get("status") not in ("published", "draft"):
            erreurs.append("%s : statut inconnu %r" % (m.get("id"), m.get("status")))
        for res in ("facebook", "instagram", "linkedin"):
            if res in m and "followers" not in (m[res].get("kpi") or {}):
                alertes.append("%s : abonnés %s absents" % (m.get("id"), res))
    for chemin, t in textes(donnees):
        if A_REDIGER in t:
            erreurs.append("Texte à rédiger : %s" % chemin)
        if ("—" in t or "–" in t) and not chemin.startswith("author"):
            alertes.append("Tiret long à remplacer : %s" % chemin)
    return erreurs, alertes


def afficher_controle(donnees):
    erreurs, alertes = controler(donnees)
    for a in alertes:
        print("attention :", a)
    for e in erreurs:
        print("ERREUR :", e)
    return not erreurs


def main(argv):
    if not argv:
        print(__doc__)
        return 1
    cmd, args = argv[0], argv[1:]
    if cmd == "verifier" and args:
        donnees = json.loads(Path(args[0]).read_text(encoding="utf-8"))
        if "months" not in donnees:
            donnees = {"months": [donnees]}
        ok = afficher_controle(donnees)
        print("OK" if ok else "À corriger")
        return 0 if ok else 1

    cle_ = cle()
    donnees = lire_donnees(cle_)

    if cmd == "resume":
        for m in donnees["months"]:
            print("%s  %s" % (m["id"], "publié" if m.get("status") == "published" else "en attente de validation"))
        return 0
    if cmd == "exporter":
        Path(args[0]).write_text(json.dumps(donnees, ensure_ascii=False, indent=1), encoding="utf-8")
        print("Données exportées dans", args[0])
        return 0
    if cmd == "verifier":
        ok = afficher_controle(donnees)
        print("OK" if ok else "À corriger")
        return 0 if ok else 1
    if cmd == "importer":
        nouvelles = json.loads(Path(args[0]).read_text(encoding="utf-8"))
        if not afficher_controle(nouvelles):
            return 1
        ecrire_donnees(nouvelles, cle_)
        print("Données importées.")
        return 0
    if cmd == "ajouter-mois":
        mois = json.loads(Path(args[0]).read_text(encoding="utf-8"))
        mois.setdefault("status", "draft")
        if not afficher_controle({"months": [mois]}):
            return 1
        donnees["months"] = [m for m in donnees["months"] if m["id"] != mois["id"]] + [mois]
        ecrire_donnees(donnees, cle_)
        print("Mois %s enregistré (%s)." % (mois["id"], mois["status"]))
        return 0
    if cmd == "publier":
        trouve = False
        for m in donnees["months"]:
            if m["id"] == args[0]:
                m["status"] = "published"
                trouve = True
        if not trouve:
            print("Mois introuvable :", args[0])
            return 1
        ecrire_donnees(donnees, cle_)
        print("Mois %s publié." % args[0])
        return 0
    if cmd == "retirer":
        avant = len(donnees["months"])
        donnees["months"] = [m for m in donnees["months"] if not (m["id"] == args[0] and m.get("status") != "published")]
        if len(donnees["months"]) == avant:
            print("Aucun mois en attente à retirer pour", args[0])
            return 1
        ecrire_donnees(donnees, cle_)
        print("Mois %s retiré." % args[0])
        return 0
    print(__doc__)
    return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
