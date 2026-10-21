# Statistiques réseaux sociaux · Pick & Smile

Espace de suivi mensuel des performances Facebook, Instagram, LinkedIn, Meta Ads et TikTok Ads de Pick & Smile, préparé par Sarah Beets, community manager.

La page est protégée par un mot de passe : les chiffres sont chiffrés (AES-256) et ne s'affichent qu'une fois le mot de passe saisi.

## Organisation

| Élément | Rôle |
|---|---|
| `index.html` | la page vue par le client (mois validés uniquement) |
| `apercu/index.html` | la version d'aperçu, avec les mois en attente de validation |
| `data/donnees.enc` | toutes les données, chiffrées |
| `src/` | modèle de la page, polices et visuels de la charte |
| `scripts/` | outils de mise à jour |

## Mise à jour mensuelle

Toutes les commandes demandent le mot de passe dans la variable `PS_MOT_DE_PASSE`.

1. `python3 scripts/metricool.py requetes AAAA-MM` donne la période et les métriques à exporter.
2. Les réponses brutes sont enregistrées dans un dossier de travail (hors du dépôt), un fichier par requête, y compris les répartitions d'audience (`audience_*`), les concurrents (`concurrents_*`) et les hashtags (`hashtags_instagram`).
3. `python3 scripts/metricool.py preparer AAAA-MM --brut DOSSIER --sortie mois.json` calcule les indicateurs et les classements.
4. Les textes (analyses, recommandations, titres des publications, phrase sous chaque tableau des concurrents) sont rédigés dans `mois.json`, puis `python3 scripts/donnees.py verifier mois.json`.
5. `python3 scripts/donnees.py ajouter-mois mois.json` puis `python3 scripts/build.py` : le mois apparaît dans l'aperçu.
6. Après validation : `python3 scripts/donnees.py publier AAAA-MM` puis `python3 scripts/build.py`.

Dépendance Python : `cryptography`.

## Changer le mot de passe

1. `PS_MOT_DE_PASSE=ancien PS_NOUVEAU_MOT_DE_PASSE=nouveau python3 scripts/donnees.py changer-mot-de-passe`
2. `PS_MOT_DE_PASSE=nouveau python3 scripts/build.py`

Les personnes restées connectées devront saisir le nouveau mot de passe à leur prochaine visite.
