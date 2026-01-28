# Rapport de Vérification Double-Blind du Ground Truth

**Date:** 2025-07-27
**Modèle:** claude-sonnet-4-20250514 (via image tool)
**Méthode:** Crops des bboxes envoyés à Claude Vision pour identification indépendante

## Résumé Exécutif

⚠️ **RÉSULTAT CRITIQUE: Le ground truth ne peut PAS être vérifié spatialement via les bboxes actuels.**

Les bounding boxes dans `rooms_complete.json` ne pointent pas vers les bons emplacements sur les images des pages PDF. La vérification visuelle indépendante montre que les crops ne contiennent généralement pas le room ID attendu.

## Statistiques

| Métrique | Valeur |
|----------|--------|
| Rooms dans le GT | 99 |
| Rooms vérifiées | 30 |
| Échantillon | 30.3% |
| **Matches complets (ID+Nom)** | **0 / 30 (0.0%)** |
| Matches ID seul | 1 / 30 (3.3%) |
| Matches nom (type similar) | 10 / 30 (33.3%) |
| Crops illisibles (conf < 0.2) | 7 / 30 (23.3%) |
| **Score de fiabilité spatiale** | **0.0%** |

## Analyse Détaillée des 30 Rooms Vérifiées

| # | GT ID | GT Nom | Vision ID | Vision Nom | ID | Nom | Conf |
|---|-------|--------|-----------|------------|-----|-----|------|
| 1 | A-213 | ORTHOPÉDAGOGUE + ORTHOPHONIE | 208 | CLASSE | ❌ | ❌ | 0.9 |
| 2 | A-107 | CLASSE | _(vide)_ | _(vide)_ | ❌ | ❌ | 0.1 |
| 3 | A-101 | CLASSE | A-100 | VESTIBULE | ❌ | ❌ | 0.75 |
| 4 | A-117 | CLASSE | A-110 | CHAUFFERIE | ❌ | ❌ | 0.82 |
| 5 | A-115 | SALLE PROFESSEURS | A-118 | SALLE PROFESSEURS | ❌ | ✅ | 0.75 |
| 6 | A-114 | DÉPÔT | 012 | CORRIDOR | ❌ | ❌ | 0.9 |
| 7 | A-108 | CLASSE | _(vide)_ | _(vide)_ | ❌ | ❌ | 0.1 |
| 8 | A-106 | CLASSE | A-108 | CLASSE | ❌ | ✅ | 0.75 |
| 9 | A-207 | CORRIDOR | 210 | CORRIDOR | ❌ | ✅ | 0.85 |
| 10 | A-105 | CLASSE | A-108 | CLASSE | ❌ | ✅ | 0.75 |
| 11 | A-200 | VESTIBULE | 209 | _(vide)_ | ❌ | ❌ | 0.3 |
| 12 | A-102 | SECRÉTARIAT | A-102 | VESTIBULE | ✅ | ❌ | 0.5 |
| 13 | A-100 | VESTIBULE | _(vide)_ | _(vide)_ | ❌ | ❌ | 0.1 |
| 14 | B-106 | CLASSE | 135 | CLASSE MATERNELLE | ❌ | ✅ | 0.9 |
| 15 | B-114 | CLASSE | A-133 | CLASSE | ❌ | ✅ | 0.7 |
| 16 | B-115 | CLASSE | A-130 | CLASSE | ❌ | ✅ | 0.75 |
| 17 | B-146 | CLASSE | A-500 | UNKNOWN | ❌ | ❌ | 0.15 |
| 18 | B-102 | CLASSE MATERNELLE | A-132 | CLASSE | ❌ | ✅ | 0.75 |
| 19 | B-201 | ORTHOPATHOLOGIE ECE | _(vide)_ | _(vide)_ | ❌ | ❌ | 0.05 |
| 20 | B-113 | CLASSE | A-133 | CLASSE | ❌ | ✅ | 0.62 |
| 21 | B-148 | CLASSE | A-104 | TRAPPE D'ACCÈS | ❌ | ❌ | 0.2 |
| 22 | B-140 | CLASSE MATERNELLE | A-113 | LOCAL | ❌ | ❌ | 0.3 |
| 23 | B-205 | CORRIDOR | A-147 | WC FILLES | ❌ | ❌ | 0.75 |
| 24 | B-142 | CLASSE | A-800 | _(vide)_ | ❌ | ❌ | 0.15 |
| 25 | B-125 | CORRIDOR | D-136 | WC GARÇONS | ❌ | ❌ | 0.75 |
| 26 | B-109 | CLASSE | B-131 | CLASSE MATERNELLE | ❌ | ✅ | 0.92 |
| 27 | C-149 | LOCAL TECHNICIEN(NE) | _(vide)_ | _(vide)_ | ❌ | ❌ | 0.0 |
| 28 | C-101 | CORRIDOR | C-151 | BLOC C | ❌ | ❌ | 0.3 |
| 29 | C-103 | RANGEMENT | A-800 | MÉCANIQUE | ❌ | ❌ | 0.3 |
| 30 | C-107 | LOCAL TECHNIQUE | A-102 | UNKNOWN | ❌ | ❌ | 0.25 |

## Diagnostic

### Cause Racine
Les bounding boxes dans `rooms_complete.json` **ne correspondent pas** aux emplacements réels des labels de rooms sur les images des pages PDF. Les crops montrent systématiquement :
- Des rooms DIFFÉRENTES de celles attendues
- Des zones de notes/spécifications plutôt que des plans
- Des zones vides ou illisibles

### Ce qui fonctionne vs ce qui ne fonctionne pas

| Aspect | Fiabilité | Note |
|--------|-----------|------|
| Liste des room IDs | **INCONNUE** | Ne peut être vérifié via les bboxes |
| Room names/types | **INCONNUE** | Idem |
| Bounding boxes | **TRÈS FAIBLE** | 0% de correspondance spatiale |
| Page association | **FAIBLE** | Seules 2 pages (010, 012) sont référencées |

### Observations Clés

1. **Tous les rooms de Bloc B** ont des bboxes pointant vers des rooms de **Bloc A** (ex: B-114 → A-133, B-115 → A-130). Cela suggère que les bboxes de page-010.png (Bloc A?) ont été appliquées aux rooms du Bloc B.

2. **Les rooms du Bloc C** pointent vers des zones de notes/spécifications, pas des plans.

3. **10/30 rooms** ont un type/nom similaire (CLASSE → CLASSE), ce qui suggère que les noms de rooms dans le GT sont probablement corrects (extraits du texte), mais les bboxes sont décalées.

## Recommandations

1. **Ne PAS utiliser les bboxes** de `rooms_complete.json` comme ground truth spatial
2. **Vérifier la liste de rooms** via les documents de nomenclature/devis (source textuelle indépendante)
3. **Recalibrer les bboxes** en utilisant une méthode de recherche spatiale correcte (par page et par bloc)
4. Marquer les rooms comme `"vision_verified": false` dans le GT

## Conclusion

Le ground truth de `emj.json` a été construit par validation circulaire (auto-enrichissement depuis les extractions PyMuPDF). La vérification double-blind par Vision AI révèle que les **bounding boxes sont fondamentalement incorrects** (0% de match). 

La liste de rooms elle-même (IDs et noms) peut être correcte car elle provient de l'extraction textuelle, mais cela ne peut pas être confirmé spatialement. Une vérification via les documents de nomenclature/devis est nécessaire.
