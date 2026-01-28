# Blueprint Extractor - Upgrade Plan

**Objectif:** Amener le skill au niveau de l'API Plans_Vision
**Date:** 2025-01-28
**Status:** 🚧 EN COURS

---

## Phase 1: Core Extraction (PyMuPDF) ✅ PRIORITÉ

### Task 1.1: extract_pdf_vectors.py
- [ ] Extraire texte + bboxes avec PyMuPDF (fitz)
- [ ] Extraire paths vectoriels (lignes, arcs, rectangles)
- [ ] Convertir coordonnées PDF → pixels PNG
- [ ] Output: JSON structuré par page
- [ ] Tests: test_extract_pdf_vectors.py

### Task 1.2: room_detector.py
- [ ] Détecter numéros de locaux (pattern: 3 chiffres, A-xxx, B-xxx)
- [ ] Associer nom de local au numéro (proximity search)
- [ ] Calculer bbox du local (expand from number position)
- [ ] Confidence scoring basé sur pattern match
- [ ] Tests: test_room_detector.py

### Task 1.3: door_detector.py
- [ ] Détecter portes via arcs dans paths vectoriels
- [ ] Extraire swing angle, direction
- [ ] Associer numéro de porte si présent
- [ ] Tests: test_door_detector.py

### Task 1.4: dimension_detector.py
- [ ] Détecter cotes (pattern: XX'-YY" ou XX'-YY ZZ/WW")
- [ ] Extraire start/end points des lignes de cote
- [ ] Parser valeur en pouces totaux
- [ ] Tests: test_dimension_detector.py

---

## Phase 2: Page Selection Automatique

### Task 2.1: page_classifier.py
- [ ] Classifier pages: LEGEND / PLAN / DETAIL / OTHER
- [ ] Level 1: Token scoring (chercher mots-clés)
- [ ] Level 2: Vision AI fallback
- [ ] Level 3: First N pages fallback
- [ ] Tests: test_page_classifier.py

### Task 2.2: page_selector.py
- [ ] Sélectionner 5 pages optimales pour analyse
- [ ] Priorité: 1 LEGEND + 4 PLAN
- [ ] Diversifier les étages/blocs
- [ ] Tests: test_page_selector.py

---

## Phase 3: Pipeline 4 Agents Formalisé

### Task 3.1: agent_guide_builder.py
- [ ] Input: 5 pages sélectionnées
- [ ] Output: provisional_guide.md + candidate_rules.json
- [ ] Prompt engineering pour extraction patterns
- [ ] Tests: test_guide_builder.py

### Task 3.2: agent_guide_applier.py
- [ ] Input: provisional_guide + 3 validation pages
- [ ] Output: validation_reports.json
- [ ] Status par règle: CONFIRMED/CONTRADICTED/VARIATION
- [ ] Tests: test_guide_applier.py

### Task 3.3: agent_self_validator.py
- [ ] Input: provisional_guide + validation_reports
- [ ] Output: confidence_report.json
- [ ] Score 0.0-1.0, can_generate_final bool
- [ ] Tests: test_self_validator.py

### Task 3.4: agent_consolidator.py
- [ ] Input: provisional_guide + confidence_report
- [ ] Output: stable_guide.md + stable_rules.json
- [ ] Rejection si confidence < 0.7
- [ ] Tests: test_consolidator.py

### Task 3.5: pipeline_orchestrator.py
- [ ] Orchestrer les 4 agents en séquence
- [ ] Gestion erreurs et retries
- [ ] Progress callback
- [ ] Tests: test_pipeline.py

---

## Phase 4: Cleanup & Polish

### Task 4.1: Supprimer code obsolète
- [ ] Retirer dépendances SAM2
- [ ] Retirer OCR (pytesseract, easyocr)
- [ ] Nettoyer imports inutilisés
- [ ] Mettre à jour requirements.txt

### Task 4.2: Mettre à jour SKILL.md
- [ ] Documenter nouveau workflow
- [ ] Exemples d'utilisation
- [ ] API des scripts

### Task 4.3: Tests d'intégration
- [ ] Test end-to-end sur PDF réel
- [ ] Benchmark performance
- [ ] Valider output JSON schema

---

## Phase 5: GitHub Release

### Task 5.1: Préparer repo
- [ ] .gitignore (output/, .venv/, __pycache__/)
- [ ] README.md
- [ ] LICENSE (MIT)
- [ ] requirements.txt final
- [ ] pyproject.toml

### Task 5.2: Push
- [ ] Créer repo github.com/Omer-Omerco/blueprint-extractor
- [ ] Initial commit
- [ ] Tag v2.0.0

---

## Dispatching

| Task | Assigné à | Status |
|------|-----------|--------|
| 1.1 extract_pdf_vectors | Claude Code #1 | ✅ DONE |
| 1.2 room_detector | Claude Code #1 | ✅ DONE |
| 1.3 door_detector | Claude Code #2 | ✅ DONE (limitation: PDFs sans arcs 90°) |
| 1.4 dimension_detector | Claude Code #2 | ✅ DONE |
| 2.1 page_classifier | Claude Code #3 | ✅ DONE |
| 2.2 page_selector | Claude Code #3 | ✅ DONE |
| 3.x Pipeline agents | Claude Code #4 | ✅ DONE |
| 4.x Cleanup | Main (moi) | ⏳ |
| 5.x GitHub | Main (moi) | ⏳ |

## E2E Test Results (2025-01-28)
- **207 tests passent**
- extract_pdf_vectors: 278 texts, 36742 drawings ✅
- room_detector: 48 rooms, 204 trouvé ✅
- dimension_detector: 94 dimensions ✅
- page_classifier: 35 pages classifiées ✅
- page_selector: 5 pages sélectionnées ✅
- door_detector: 0 portes (PDF test n'a pas d'arcs 90°) ⚠️

---

## Fichiers de test existants à préserver
- test_extract_pages.py ✅
- test_build_rag.py ✅
- test_query_rag.py ✅
- test_validation.py ✅
- test_confidence.py ✅
- test_alerts.py ✅
- test_render.py ✅
- test_integration.py ✅
