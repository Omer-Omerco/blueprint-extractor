# Blueprint-Extractor — TODO Béton 🏗️
*Objectif: skill solide comme du béton pour demain matin (29 jan 2026)*

## Phase 1: Ground Truth Gold Standard ⏳
- [ ] Trouver le tableau des locaux/finis dans le PDF d'archi
- [ ] Cross-référencer avec le devis (365 pages)
- [ ] Créer `ground_truth/emj_gold.json` avec sources documentées
- [ ] Comparer GT gold vs extraction actuelle → rapport d'écarts
- [ ] Remplacer `emj.json` par le GT gold validé
- **Agent:** `blueprint-gt-rebuild` (lancé)

## Phase 2: Cross-Validation Plans ↔ Devis
- [ ] Améliorer `cross_validate.py` pour utiliser le nouveau GT
- [ ] Mapper les mentions de locaux du devis aux locaux des plans
- [ ] Score de cross-validation > 80% (actuellement 0%)
- [ ] Tests pour la cross-validation

## Phase 3: Fix Extraction Bugs
- [ ] Analyser le rapport d'écarts GT gold vs extraction
- [ ] Fixer les rooms manqués dans `room_detector.py`
- [ ] Fixer les noms incorrects
- [ ] Fixer les faux positifs (rooms en trop)

## Phase 4: Tests Béton
- [ ] Tous les tests passent (519+)
- [ ] Tests de régression avec GT gold
- [ ] Accuracy > 95% sur GT gold
- [ ] Push GitHub avec tout clean

## Fichiers clés
- PDF archi: `/Users/omer/Mon disque/Projet Ecole Mario/01_ARCHITECTURE/C25-256 _Architecture_plan_Construction.pdf`
- Devis archi: `/Users/omer/Mon disque/Projet Ecole Mario/01_ARCHITECTURE/Devis architecture_365 pages.pdf`
- GT actuel: `ground_truth/emj.json` (99 rooms, 0 verified)
- Skill: `/Users/omer/clawd/skills/blueprint-extractor/`
