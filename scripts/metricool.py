#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Préparation mensuelle à partir des exports Metricool.

  requetes AAAA-MM
      Affiche, pour chaque fichier attendu, la période et la liste exacte des métriques
      à demander (dans cet ordre) pour la marque Pick & Smile.

  preparer AAAA-MM --brut DOSSIER --sortie FICHIER.json
      Lit dans DOSSIER les réponses Metricool enregistrées telles quelles
      (un fichier par requête : facebook.json, instagram.json, ...), calcule les
      indicateurs du mois et écrit un mois prêt à compléter : chiffres, classements
      de posts et campagnes, et textes marqués « À RÉDIGER ».
      Si PS_MOT_DE_PASSE est défini, affiche aussi la comparaison avec le mois précédent.
"""
import argparse
import calendar
import json
import sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

sys.path.insert(0, str(Path(__file__).resolve().parent))
from commun import config  # noqa: E402

A_REDIGER = "À RÉDIGER"
FORMATS_IG = {"FEED_IMAGE": "Image", "FEED_CAROUSEL_ALBUM": "Carrousel", "FEED_VIDEO": "Vidéo",
              "REELS": "Reel", "CAROUSEL_ALBUM": "Carrousel", "IMAGE": "Image", "VIDEO": "Vidéo"}


def periode(mois: str, fuseau: str):
    an, m = (int(x) for x in mois.split("-"))
    dernier = calendar.monthrange(an, m)[1]
    tz = ZoneInfo(fuseau)
    debut = datetime(an, m, 1, 0, 0, 0, tzinfo=tz)
    fin = datetime(an, m, dernier, 23, 59, 59, tzinfo=tz)
    return debut.isoformat(), fin.isoformat()


def num(x):
    if x is None or x == "":
        return None
    try:
        return float(x)
    except (TypeError, ValueError):
        return None


def charger(dossier: Path, nom: str, metriques):
    f = dossier / (nom + ".json")
    if not f.exists():
        return None
    brut = json.loads(f.read_text(encoding="utf-8"))
    lignes = brut.get("rows", brut) if isinstance(brut, dict) else brut
    for ligne in lignes:
        if len(ligne) > len(metriques) + 1:
            sys.exit("%s : une ligne compte %d valeurs pour %d métriques demandées." % (f.name, len(ligne), len(metriques)))
    return lignes


def evolution(lignes, metriques):
    """Lignes quotidiennes : [m1, m2, ..., AAAAMMJJ]. Renvoie des accès somme / dernière / unique."""
    lignes = sorted(lignes, key=lambda l: str(l[-1]))
    col = {m: i for i, m in enumerate(metriques)}

    def somme(m):
        vals = [num(l[col[m]]) for l in lignes]
        vals = [v for v in vals if v is not None]
        return sum(vals) if vals else None

    def derniere(m):
        for l in reversed(lignes):
            v = num(l[col[m]])
            if v is not None:
                return v
        return None
    return somme, derniere


def entier(v):
    return None if v is None else int(round(v))


def arrondi(v, d=2):
    return None if v is None else round(v, d)


def titre_par_defaut(texte, limite=70):
    premiere = (texte or "").strip().split("\n")[0].strip()
    return premiere if len(premiere) <= limite else premiere[:limite - 1].rstrip() + "…"


def date_iso(v):
    v = str(v)
    return "%s-%s-%s" % (v[0:4], v[4:6], v[6:8]) if len(v) >= 8 and v[:8].isdigit() else v


def kpis_facebook(lignes, met):
    s, d = evolution(lignes, met)
    k = {
        "followers": entier(d("FBEV17")), "followersGained": entier(s("FBEV47")), "followersLost": entier(s("FBEV48")),
        "posts": entier(s("FBEV04")), "reels": entier(s("FBEV21")), "stories": entier(s("FBEV35")),
        "views": entier(s("FBEV49")), "pageVisits": entier(s("FBEV03")),
        "avgReachPerPost": arrondi(d("FBEV18"), 1), "engagement": arrondi(d("FBEV19"), 2),
        "interactions": entier(s("FBEV34")), "clicks": entier(s("FBEV16")), "reactions": entier(s("FBEV13")),
        "comments": entier(s("FBEV14")), "shares": entier(s("FBEV15")),
    }
    k["contents"] = sum(v or 0 for v in (k["posts"], k["reels"], k["stories"]))
    return {a: b for a, b in k.items() if b is not None}


def kpis_instagram(lignes, met):
    s, d = evolution(lignes, met)
    k = {
        "followers": entier(d("IGEV01")), "followersGained": entier(s("IGEV43")), "followersLost": entier(s("IGEV44")),
        "posts": entier(s("IGEV04")), "reels": entier(s("IGEV22")), "stories": entier(s("IGEV16")),
        "views": entier(s("IGEV05")), "avgReachPerPost": arrondi(d("IGEV19"), 1),
        "avgReachPerStory": arrondi(d("IGEV20"), 1), "engagement": arrondi(d("IGEV21"), 2),
        "interactions": entier(s("IGEV09")), "likes": entier(s("IGEV13")), "comments": entier(s("IGEV14")),
        "shares": entier(s("IGEV40")), "saves": entier(s("IGEV15")),
    }
    if k.get("reels"):
        k["reelsAvgReach"] = arrondi(d("IGEV30"), 0)
    return {a: b for a, b in k.items() if b is not None}


def kpis_linkedin(lignes, met):
    s, d = evolution(lignes, met)
    k = {
        "followers": entier(d("LIEV01")), "posts": entier(s("LIEV04")), "impressions": entier(s("LIEV22")),
        "reactions": entier(s("LIEV21")), "clicks": entier(s("LIEV24")), "comments": entier(s("LIEV23")),
        "shares": entier(s("LIEV20")), "pageViews": entier(s("LIEV31")),
    }
    return {a: b for a, b in k.items() if b is not None}


def kpis_publicite(lignes, met):
    s, d = evolution(lignes, met)

    def couts(impr, clics, dep):
        out = {}
        if impr:
            out["cpm"] = round(dep / impr * 1000, 2)
            out["ctr"] = round(clics / impr * 100, 2)
        if clics:
            out["cpc"] = round(dep / clics, 2)
        return out
    meta = {"impressions": entier(s("FAEV01")), "reach": entier(d("FAEV03")), "spend": arrondi(s("FAEV04")),
            "clicks": entier(s("FAEV05"))}
    tiktok = {"impressions": entier(s("KAEV01")), "spend": arrondi(s("KAEV02")), "clicks": entier(s("KAEV03")),
              "conversions": entier(s("KAEV04"))}
    meta.update(couts(meta["impressions"] or 0, meta["clicks"] or 0, meta["spend"] or 0))
    tiktok.update(couts(tiktok["impressions"] or 0, tiktok["clicks"] or 0, tiktok["spend"] or 0))
    return ({a: b for a, b in meta.items() if b is not None}, {a: b for a, b in tiktok.items() if b is not None})


def table_posts(lignes, champs, tri, colonnes, limite=5, transformer=None):
    rows = []
    for l in lignes or []:
        r = dict(zip(champs, l))
        r = {k: (num(v) if k not in ("date", "texte", "url", "type", "name") else v) for k, v in r.items()}
        if transformer:
            r = transformer(r)
        if r is not None:
            rows.append(r)
    rows.sort(key=lambda r: (r.get(tri) or 0), reverse=True)
    return {"columns": colonnes, "rows": rows[:limite]}


PAYS = {
    "FR": "France", "DZ": "Algérie", "MA": "Maroc", "TN": "Tunisie", "BE": "Belgique", "CH": "Suisse",
    "LU": "Luxembourg", "ES": "Espagne", "PT": "Portugal", "IT": "Italie", "DE": "Allemagne", "NL": "Pays-Bas",
    "GB": "Royaume-Uni", "IE": "Irlande", "GR": "Grèce", "PL": "Pologne", "RO": "Roumanie", "HU": "Hongrie",
    "LT": "Lituanie", "SE": "Suède", "DK": "Danemark", "NO": "Norvège", "FI": "Finlande", "AT": "Autriche",
    "CZ": "Tchéquie", "SK": "Slovaquie", "BG": "Bulgarie", "HR": "Croatie", "RS": "Serbie", "UA": "Ukraine",
    "RU": "Russie", "TR": "Turquie", "US": "États-Unis", "CA": "Canada", "MX": "Mexique", "BR": "Brésil",
    "AR": "Argentine", "CO": "Colombie", "PE": "Pérou", "CL": "Chili", "HT": "Haïti", "CI": "Côte d'Ivoire",
    "SN": "Sénégal", "CM": "Cameroun", "BJ": "Bénin", "TG": "Togo", "ML": "Mali", "BF": "Burkina Faso",
    "NE": "Niger", "GN": "Guinée", "GA": "Gabon", "CG": "Congo-Brazzaville", "CD": "RD Congo", "TD": "Tchad",
    "MG": "Madagascar", "MU": "Maurice", "KM": "Comores", "DJ": "Djibouti", "NG": "Nigeria", "GH": "Ghana",
    "KE": "Kenya", "TZ": "Tanzanie", "UG": "Ouganda", "ET": "Éthiopie", "ZA": "Afrique du Sud", "EG": "Égypte",
    "LY": "Libye", "MR": "Mauritanie", "LB": "Liban", "SA": "Arabie saoudite", "AE": "Émirats arabes unis",
    "QA": "Qatar", "BH": "Bahreïn", "KW": "Koweït", "IL": "Israël", "IR": "Iran", "IQ": "Irak", "IN": "Inde",
    "PK": "Pakistan", "BD": "Bangladesh", "LK": "Sri Lanka", "CN": "Chine", "HK": "Hong Kong", "TW": "Taïwan",
    "JP": "Japon", "KR": "Corée du Sud", "VN": "Viêt Nam", "TH": "Thaïlande", "ID": "Indonésie",
    "PH": "Philippines", "MY": "Malaisie", "SG": "Singapour", "AU": "Australie", "NZ": "Nouvelle-Zélande",
    "KZ": "Kazakhstan", "RE": "La Réunion", "YT": "Mayotte", "GP": "Guadeloupe", "MQ": "Martinique",
    "GF": "Guyane", "NC": "Nouvelle-Calédonie", "PF": "Polynésie française", "WF": "Wallis-et-Futuna",
    "PM": "Saint-Pierre-et-Miquelon", "MC": "Monaco", "AD": "Andorre",
}
SECTEURS = {
    "Transport, logistique, chaîne logistique et stockage": "Transport & logistique",
    "Technologie, médias et télécommunications": "Tech, médias, télécoms",
    "Services d'hébergement et de restauration": "Hébergement & restauration",
    "Services immobiliers et de location de biens matériels": "Immobilier & location",
    "Hôpitaux et services de santé": "Santé",
    "Arts, spectacles et activités récréatives": "Arts & loisirs",
    "Agriculture, sylviculture et pêche": "Agriculture",
    "Services administratifs et de soutien": "Services administratifs",
}
FONCTIONS = {
    "Services à la communauté et Services sociaux": "Services à la communauté",
    "Management de projets et de programmes": "Gestion de projets",
    "Armée et Services de protection": "Armée & protection",
}
NIVEAUX = {"PDG": "PDG · VP", "VP": "PDG · VP"}


def pourcentages(lignes, renommer=None, exclure=("Autres",)):
    """Lignes [libellé, part entre 0 et 1] -> [(libellé, %)] triées, libellés renommés et regroupés."""
    total, ordre = {}, []
    for l in lignes or []:
        if len(l) < 2:
            continue
        nom = str(l[0] or "").strip().replace("’", "'")
        v = num(l[1])
        if v is None or not nom or nom in exclure:
            continue
        nom = renommer(nom) if renommer else nom
        if nom not in total:
            ordre.append(nom)
            total[nom] = 0.0
        total[nom] += v
    items = [(n, round(total[n] * 100, 2)) for n in ordre]
    items.sort(key=lambda x: -x[1])
    return items


def top_lignes(items, lignes_max=6, noms_max=4, autres="autres"):
    """Regroupe les ex aequo sur une ligne (« Portugal · Italie · Espagne ») comme dans les rapports."""
    rows, i = [], 0
    while i < len(items) and len(rows) < lignes_max:
        j = i
        while j + 1 < len(items) and items[j + 1][1] == items[i][1]:
            j += 1
        noms = [n for n, _ in items[i:j + 1]]
        if len(noms) > noms_max and len(rows) >= 5:
            break  # longue traîne d'ex aequo : on s'arrête là plutôt que d'afficher une ligne fourre-tout
        lib = " · ".join(noms) if len(noms) <= noms_max else "%s et %d %s" % (" · ".join(noms[:3]), len(noms) - 3, autres)
        rows.append([lib, items[i][1]])
        i = j + 1
    return rows


def nom_pays(code):
    return PAYS.get(code.upper(), code) if len(code) == 2 else code


def nom_lieu(texte):
    return texte.split(",")[0].strip()


def audience_reseau(dossier: Path, conf, reseau):
    """Bloc « Démographie : pays et villes » (Facebook, Instagram) à partir des répartitions Metricool."""
    groupes = []
    pays = charger(dossier, "audience_%s_pays" % reseau, conf.get("audience_%s_pays" % reseau, {}).get("metrics", []))
    if pays:
        groupes.append({"title": "Top des pays", "items": top_lignes(pourcentages(pays, nom_pays), 7, 4, "autres pays")})
    villes = charger(dossier, "audience_%s_villes" % reseau, conf.get("audience_%s_villes" % reseau, {}).get("metrics", []))
    if villes:
        groupes.append({"title": "Top des villes", "items": top_lignes(pourcentages(villes, nom_lieu), 7, 4, "autres villes")})
    groupes = [g for g in groupes if g["items"]]
    return [{"title": "Démographie : pays et villes", "groups": groupes}] if groupes else None


def audience_linkedin(dossier: Path, conf):
    def lire(nom):
        return charger(dossier, nom, conf.get(nom, {}).get("metrics", []))
    blocs = []
    emplacement = []
    if lire("audience_linkedin_pays"):
        emplacement.append({"title": "Top pays", "items": top_lignes(pourcentages(lire("audience_linkedin_pays")), 6)})
    if lire("audience_linkedin_zones"):
        emplacement.append({"title": "Principaux emplacements",
                            "items": top_lignes(pourcentages(lire("audience_linkedin_zones"), nom_lieu), 6)})
    if emplacement:
        blocs.append({"title": "Emplacement des abonnés", "groups": emplacement})
    profil = []
    if lire("audience_linkedin_secteurs"):
        profil.append({"title": "Secteurs", "items": top_lignes(pourcentages(lire("audience_linkedin_secteurs"),
                                                                             lambda n: SECTEURS.get(n, n)), 6)})
    if lire("audience_linkedin_fonctions"):
        profil.append({"title": "Fonctions", "items": top_lignes(pourcentages(lire("audience_linkedin_fonctions"),
                                                                              lambda n: FONCTIONS.get(n, n)), 6)})
    if lire("audience_linkedin_niveaux"):
        profil.append({"title": "Niveaux de responsabilité",
                       "items": top_lignes(pourcentages(lire("audience_linkedin_niveaux"), lambda n: NIVEAUX.get(n, n)), 6)})
    if profil:
        blocs.append({"title": "Profil des abonnés", "groups": profil})
    return blocs or None


def concurrents(lignes, champs, colonnes, soi, ordre_prefere):
    """Tableau des concurrents : Pick & Smile en tête puis les comptes suivis dans Metricool."""
    rows = []
    for l in lignes or []:
        r = dict(zip(champs, l))
        nom = str(r.get("display") or r.get("name") or r.get("screen") or "").split("|")[0].strip()
        if not nom:
            continue
        row = {"name": nom}
        for c in colonnes:
            v = num(r.get(c))
            row[c] = None if v is None else (entier(v) if c in ("followers", "posts", "reels") else round(v, 2))
        rows.append(row)
    if not rows:
        return None
    rang = {n: i for i, n in enumerate(ordre_prefere)}
    rows.sort(key=lambda r: (rang.get(r["name"], len(rang)), -(r.get("followers") or 0)))
    moi = {"name": "Pick & Smile", "self": True}
    moi.update({c: soi.get(c) for c in colonnes})
    return {"columns": colonnes, "rows": [moi] + rows, "note": A_REDIGER}


def hashtags(lignes, limite=5):
    rows = []
    for l in lignes or []:
        if len(l) < 4 or not l[0]:
            continue
        rows.append({"tag": str(l[0]).strip(), "posts": entier(num(l[1])), "views": entier(num(l[2])),
                     "likes": entier(num(l[3]))})
    rows.sort(key=lambda r: (-(r["views"] or 0), -(r["posts"] or 0), r["tag"]))
    return {"rows": rows[:limite]} if rows else None


def blocs_complementaires(dossier: Path, mois_obj):
    """Ajoute audience, concurrents et hashtags au mois (Facebook, Instagram, LinkedIn) quand les fichiers existent."""
    conf_all = config()["metricool"]
    conf = conf_all["requetes"]
    ordre = conf_all.get("concurrents", {})

    def kv(res, k):
        v = ((mois_obj.get(res) or {}).get("kpi") or {}).get(k)
        return v.get("v") if isinstance(v, dict) else v
    if "facebook" in mois_obj:
        aud = audience_reseau(dossier, conf, "facebook")
        if aud:
            mois_obj["facebook"]["audience"] = aud
        lignes = charger(dossier, "concurrents_facebook", conf.get("concurrents_facebook", {}).get("metrics", []))
        if lignes:
            soi = {k: kv("facebook", k) for k in ("followers", "posts", "reactions", "engagement")}
            t = concurrents(lignes, ["name", "followers", "posts", "reactions", "engagement"],
                            ["followers", "posts", "reactions", "engagement"], soi, ordre.get("facebook", []))
            if t:
                mois_obj["facebook"]["competitors"] = t
    if "instagram" in mois_obj:
        aud = audience_reseau(dossier, conf, "instagram")
        if aud:
            mois_obj["instagram"]["audience"] = aud
        lignes = charger(dossier, "hashtags_instagram", conf.get("hashtags_instagram", {}).get("metrics", []))
        t = hashtags(lignes)
        if t:
            mois_obj["instagram"]["hashtags"] = t
        lignes = charger(dossier, "concurrents_instagram", conf.get("concurrents_instagram", {}).get("metrics", []))
        if lignes:
            soi = {k: kv("instagram", k) for k in ("followers", "posts", "reels", "engagement")}
            t = concurrents(lignes, ["screen", "display", "followers", "posts", "reels", "engagement"],
                            ["followers", "posts", "reels", "engagement"], soi, ordre.get("instagram", []))
            if t:
                mois_obj["instagram"]["competitors"] = t
    if "linkedin" in mois_obj:
        aud = audience_linkedin(dossier, conf)
        if aud:
            mois_obj["linkedin"]["audience"] = aud
    return mois_obj


def preparer(mois, dossier: Path):
    conf = config()["metricool"]["requetes"]
    sortie = {"id": mois, "status": "draft", "autoPills": True,
              "overview": {"facebook": {"note": A_REDIGER}, "instagram": {"note": A_REDIGER},
                           "linkedin": {"note": A_REDIGER}, "ads": {"note": A_REDIGER}}}

    fb = charger(dossier, "facebook", conf["facebook"]["metrics"])
    if fb:
        sortie["facebook"] = {"kpi": kpis_facebook(fb, conf["facebook"]["metrics"]), "analysis": A_REDIGER}
        posts = charger(dossier, "posts_facebook", conf["posts_facebook"]["metrics"])
        if posts:
            def tf(r):
                return {"date": date_iso(r["date"]), "title": titre_par_defaut(r["texte"]), "texte": r["texte"],
                        "url": r["url"], "reach": entier(r["reach"]), "reactions": entier(r["reactions"]),
                        "comments": entier(r["comments"]), "shares": entier(r["shares"]),
                        "clicks": entier(r["clicks"]), "engagement": arrondi(r["engagement"])}
            sortie["facebook"]["posts"] = table_posts(
                posts, ["date", "texte", "url", "type", "reach", "reactions", "comments", "shares", "clicks", "engagement"],
                "engagement", ["reach", "reactions", "comments", "shares", "clicks", "engagement"], 5, tf)

    ig = charger(dossier, "instagram", conf["instagram"]["metrics"])
    if ig:
        sortie["instagram"] = {"kpi": kpis_instagram(ig, conf["instagram"]["metrics"]), "analysis": A_REDIGER}
        posts = charger(dossier, "posts_instagram", conf["posts_instagram"]["metrics"])
        if posts:
            def ti(r):
                return {"date": date_iso(r["date"]), "title": titre_par_defaut(r["texte"]), "texte": r["texte"],
                        "url": r["url"], "format": FORMATS_IG.get(r["type"], r["type"]),
                        "views": entier(r["views"]), "reach": entier(r["reach"]), "likes": entier(r["likes"]),
                        "engagement": arrondi(r["engagement"])}
            sortie["instagram"]["posts"] = table_posts(
                posts, ["date", "texte", "url", "type", "views", "reach", "engagement", "interactions", "likes", "comments", "shares", "saves"],
                "engagement", ["format", "views", "reach", "likes", "engagement"], 5, ti)
        reels = charger(dossier, "reels_instagram", conf["reels_instagram"]["metrics"])
        if reels:
            def tr(r):
                return {"date": date_iso(r["date"]), "title": titre_par_defaut(r["texte"]), "texte": r["texte"],
                        "url": r["url"], "views": entier(r["views"]), "reach": entier(r["reach"]),
                        "likes": entier(r["likes"]), "engagement": arrondi(r["engagement"])}
            t = table_posts(reels, ["date", "texte", "url", "views", "reach", "engagement", "interactions", "likes"],
                            "views", ["views", "reach", "likes", "engagement"], 6, tr)
            if t["rows"]:
                sortie["instagram"]["reels"] = t

    li = charger(dossier, "linkedin", conf["linkedin"]["metrics"])
    if li:
        sortie["linkedin"] = {"kpi": kpis_linkedin(li, conf["linkedin"]["metrics"]), "analysis": A_REDIGER}
        posts = charger(dossier, "posts_linkedin", conf["posts_linkedin"]["metrics"])
        if posts:
            def tl(r):
                return {"date": date_iso(r["date"]), "title": titre_par_defaut(r["texte"]), "texte": r["texte"],
                        "url": r["url"], "impressions": entier(r["impressions"]), "reactions": entier(r["reactions"]),
                        "clicks": entier(r["clicks"]), "engagement": arrondi(r["engagement"])}
            t = table_posts(posts, ["date", "texte", "url", "impressions", "reactions", "clicks", "comments", "shares", "engagement"],
                            "engagement", ["impressions", "reactions", "clicks", "engagement"], 6, tl)
            t["engagementUnit"] = "%"
            sortie["linkedin"]["posts"] = t

    pub = charger(dossier, "publicite", conf["publicite"]["metrics"])
    if pub:
        meta, tiktok = kpis_publicite(pub, conf["publicite"]["metrics"])
        sortie["ads"] = {"meta": {"kpi": meta}, "tiktok": {"kpi": tiktok}, "analysis": A_REDIGER}
        cm = charger(dossier, "campagnes_meta", conf["campagnes_meta"]["metrics"])
        if cm:
            def tm(r):
                if not r.get("impressions"):
                    return None
                impr, clics, dep = r["impressions"], r.get("clicks") or 0, r.get("spend") or 0
                return {"name": (r["name"] or "").strip(), "impressions": entier(impr), "reach": entier(r.get("reach")),
                        "clicks": entier(clics), "cpm": round(dep / impr * 1000, 2),
                        "cpc": round(dep / clics, 2) if clics else None, "spend": arrondi(dep)}
            t = table_posts(cm, ["name", "impressions", "reach", "clicks", "spend"], "impressions",
                            ["impressions", "reach", "clicks", "cpm", "cpc", "spend"], 6, tm)
            if t["rows"]:
                sortie["ads"]["meta"]["campaigns"] = t
        ct = charger(dossier, "campagnes_tiktok", conf["campagnes_tiktok"]["metrics"])
        if ct:
            def tt(r):
                if not r.get("impressions"):
                    return None
                impr, clics, dep = r["impressions"], r.get("clicks") or 0, r.get("spend") or 0
                return {"name": (r["name"] or "").strip(), "impressions": entier(impr), "clicks": entier(clics),
                        "cpc": arrondi(r.get("cpc")) if r.get("cpc") is not None else (round(dep / clics, 2) if clics else None),
                        "ctr": arrondi(r.get("ctr")) if r.get("ctr") is not None else round(clics / impr * 100, 2),
                        "spend": arrondi(dep)}
            t = table_posts(ct, ["name", "impressions", "clicks", "cpc", "ctr", "spend"], "impressions",
                            ["impressions", "clicks", "cpc", "ctr", "spend"], 6, tt)
            if t["rows"]:
                sortie["ads"]["tiktok"]["campaigns"] = t

    blocs_complementaires(dossier, sortie)
    sortie["takeaways"] = {"wins": [A_REDIGER], "priorities": [A_REDIGER]}
    return sortie


def comparer(mois_obj):
    """Affiche les chiffres du mois face au mois précédent (si le mot de passe est disponible)."""
    import os
    if not os.environ.get("PS_MOT_DE_PASSE"):
        return
    from commun import lire_donnees
    donnees = lire_donnees()
    precedents = [m for m in donnees["months"] if m["id"] < mois_obj["id"]]
    if not precedents:
        return
    prec = precedents[-1]
    print("\nComparaison avec %s :" % prec["id"])

    def val(x):
        return x.get("v") if isinstance(x, dict) else x
    for res in ("facebook", "instagram", "linkedin"):
        for k, v in (mois_obj.get(res, {}).get("kpi") or {}).items():
            pv = val((prec.get(res, {}).get("kpi") or {}).get(k))
            print("  %-10s %-18s %10s   (avant : %s)" % (res, k, v, pv))
    for sous in ("meta", "tiktok"):
        for k, v in (mois_obj.get("ads", {}).get(sous, {}).get("kpi") or {}).items():
            pv = val(((prec.get("ads") or {}).get(sous, {}).get("kpi") or {}).get(k))
            print("  %-10s %-18s %10s   (avant : %s)" % (sous, k, v, pv))


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sp = ap.add_subparsers(dest="cmd", required=True)
    r = sp.add_parser("requetes")
    r.add_argument("mois")
    p = sp.add_parser("preparer")
    p.add_argument("mois")
    p.add_argument("--brut", required=True)
    p.add_argument("--sortie", required=True)
    a = ap.parse_args()
    conf = config()["metricool"]
    if a.cmd == "requetes":
        debut, fin = periode(a.mois, conf["fuseau"])
        print(json.dumps({"brandId": conf["brandId"], "from": debut, "to": fin,
                          "fichiers": {nom: q["metrics"] for nom, q in conf["requetes"].items()}},
                         ensure_ascii=False, indent=1))
        return 0
    mois = preparer(a.mois, Path(a.brut))
    Path(a.sortie).write_text(json.dumps(mois, ensure_ascii=False, indent=1), encoding="utf-8")
    print("Mois %s préparé dans %s" % (a.mois, a.sortie))
    comparer(mois)
    return 0


if __name__ == "__main__":
    sys.exit(main())
