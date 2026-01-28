---
name: blueprint-extractor
description: Analyse de plans de construction québécois avec extraction de locaux, dimensions, et génération de crops. Utilise PyMuPDF pour extraction vectorielle directe du PDF.
metadata: {"clawdbot":{"emoji":"🏗️","triggers":["blueprint","plan","construction","local","locaux","bbox","crop","étage","bloc","dimension"]}}
---

# Blueprint Extractor

Analyse de plans de construction québécois avec extraction vectorielle via PyMuPDF.

## ⚠️ RÈGLE ABSOLUE — ZÉRO HALLUCINATION

**JAMAIS inventer d'information.** C'est un projet de construction réel — des erreurs peuvent coûter cher ou être dangereuses.

### Si tu ne trouves pas l'info:
```
❌ INTERDIT: "La peinture est probablement du latex..."
✅ CORRECT:  "Je n'ai pas trouvé cette information dans les documents. 
             Vérifie avec l'architecte ou le devis section XX."
```

### Toujours citer tes sources:
```
"Selon le devis section 09 91 00, page 45..."
"D'après le plan A-150..."
```

## Vue d'ensemble

Ce skill extrait les données structurées (locaux, dimensions, portes) de plans de construction PDF en utilisant **PyMuPDF** pour l'extraction vectorielle directe — pas d'OCR nécessaire.

**Avantages vs OCR:**
- ✅ Extraction 100% précise (texte vectoriel du PDF)
- ✅ Rapide (millisecondes vs secondes)
- ✅ Pas de dépendances GPU/ML
- ✅ Bounding boxes pixel-perfect

**Important:** Toutes les dimensions sont en **PIEDS ET POUCES** (standard Québec).

## Scripts Principaux

### 1. Extraction vectorielle
```bash
cd /Users/omer/clawd/skills/blueprint-extractor
source .venv/bin/activate

# Extraire texte + dessins vectoriels d'une page
python scripts/extract_pdf_vectors.py "plans.pdf" -p 12 -o output/vectors.json
```

Output: `{ pages: [{ text_blocks: [...], drawings: [...] }] }`

### 2. Détection de locaux
```bash
python scripts/room_detector.py output/vectors.json -o output/rooms.json
```

Output: `{ rooms: [{ number: "204", name: "CLASSE", bbox: {...} }], stats: {...} }`

### 3. Détection de dimensions
```bash
python scripts/dimension_detector.py output/vectors.json -o output/dimensions.json
```

Output: `{ dimensions: [{ value_text: "25'-6\"", value_inches: 306.0 }] }`

### 4. Classification de pages
```bash
python scripts/page_classifier.py "plans.pdf" -o output/page_types.json
```

Types: LEGEND, PLAN, DETAIL, ELEVATION, OTHER

### 5. Sélection de pages optimales
```bash
python scripts/page_selector.py output/page_types.json -n 5 -o output/selected.json
```

Stratégie: 1 LEGEND + 4 PLAN diversifiés

### 6. Pipeline 4 Agents (orchestré)
```bash
python scripts/pipeline_orchestrator.py --pages p1.png p2.png --output output/
```

Exécute: Guide Builder → Guide Applier → Self-Validator → Consolidator

## Pipeline 4 Agents

Le pipeline analyse les plans en 4 étapes:

| Agent | Input | Output |
|-------|-------|--------|
| **Guide Builder** | 5 pages images | provisional_guide.md + candidate_rules.json |
| **Guide Applier** | guide + 3 pages validation | validation_reports.json |
| **Self-Validator** | guide + reports | confidence_report.json (score 0-1) |
| **Consolidator** | guide + confidence | stable_guide.md + stable_rules.json |

Confiance minimale pour guide final: **0.7**

## Formats de données

### Dimensions (pieds-pouces)
- Standard: `25'-6"` = 306 pouces
- Avec fraction: `12'-6 5/8"` = 150.625 pouces
- Conversion: `(pieds × 12) + pouces`

### Noms de locaux québécois
| Abrév. | Nom complet |
|--------|-------------|
| S.D.B. | Salle de bain |
| W.C. | Toilettes |
| CORR. | Corridor |
| RANG. | Rangement |
| MÉC. | Salle mécanique |

## Structure du skill

```
blueprint-extractor/
├── SKILL.md                     # Ce fichier
├── scripts/
│   ├── extract_pdf_vectors.py   # PDF → texte + dessins (PyMuPDF)
│   ├── room_detector.py         # Détection locaux
│   ├── dimension_detector.py    # Détection dimensions pieds-pouces
│   ├── door_detector.py         # Détection portes (arcs 90°)
│   ├── page_classifier.py       # Classification pages
│   ├── page_selector.py         # Sélection optimale
│   ├── pipeline_orchestrator.py # Pipeline 4 agents
│   └── agents/                  # Modules des 4 agents
├── tests/                       # 207 tests pytest
├── output/                      # Résultats d'extraction
└── requirements.txt             # pymupdf, pillow, numpy
```

## Exemple d'utilisation

**User:** "Analyse le plan de l'école Enfant-Jésus"

**Workflow:**
```bash
# 1. Extraire les vecteurs
python scripts/extract_pdf_vectors.py "C25-256.pdf" -p 1-15 -o output/vectors.json

# 2. Détecter les locaux
python scripts/room_detector.py output/vectors.json -o output/rooms.json

# 3. Détecter les dimensions  
python scripts/dimension_detector.py output/vectors.json -o output/dimensions.json
```

**Réponse:** "Le local 204 est une CLASSE. J'ai détecté 48 locaux et 94 dimensions sur cette page."

## Tests

```bash
source .venv/bin/activate
pytest tests/ -v  # 207 tests
```

## Limitations

- **door_detector:** Détecte les portes via arcs 90°. Certains PDFs représentent les portes différemment (pas d'arcs).
- **Vectoriel seulement:** Ne fonctionne pas sur les PDF scannés (images raster). Utiliser OCR dans ce cas.
