# Architecture — Blueprint Extractor

## Vue d'ensemble

Blueprint Extractor utilise un pipeline de 4 agents vision AI pour analyser les plans de construction et extraire des données structurées.

## Pipeline d'Analyse

```
                    ┌──────────────────────────────────────┐
                    │           PDF PLANS                   │
                    │  (Architecture, Structure, Méca...)   │
                    └─────────────────┬────────────────────┘
                                      │
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                         ÉTAPE 1: EXTRACTION                                  │
│                                                                              │
│   extract_pages.py                                                           │
│   ├─ pdftoppm @ 300 DPI                                                     │
│   ├─ Output: page-001.png, page-002.png, ...                                │
│   └─ Manifest: manifest.json (metadata)                                     │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
                                      │
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                         ÉTAPE 2: SÉLECTION PAGES                             │
│                                                                              │
│   Niveau 1: Vision AI → Identifier LEGEND vs PLAN                           │
│   Niveau 2: Token Scoring → Densité de texte                                │
│   Niveau 3: First N → Fallback                                              │
│                                                                              │
│   Output: 5 pages sélectionnées (LEGEND first)                              │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
                                      │
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                         ÉTAPE 3: PIPELINE 4-AGENTS                           │
│                                                                              │
│   ┌─────────────────────────────────────────────────────────────────────┐   │
│   │ AGENT 1: GUIDE BUILDER                                              │   │
│   │ Input:  5 pages sélectionnées                                       │   │
│   │ Action: Analyser patterns, symboles, conventions                    │   │
│   │ Output: provisional_guide.md + rules_candidates.json                │   │
│   └─────────────────────────────────────────────────────────────────────┘   │
│                                      │                                       │
│                                      ▼                                       │
│   ┌─────────────────────────────────────────────────────────────────────┐   │
│   │ AGENT 2: GUIDE APPLIER                                              │   │
│   │ Input:  provisional_guide + 3-5 nouvelles pages                     │   │
│   │ Action: Tester chaque règle sur chaque page                         │   │
│   │ Output: validation_reports.json                                     │   │
│   │         - CONFIRMED / CONTRADICTED / VARIATION / NOT_TESTABLE       │   │
│   └─────────────────────────────────────────────────────────────────────┘   │
│                                      │                                       │
│                                      ▼                                       │
│   ┌─────────────────────────────────────────────────────────────────────┐   │
│   │ AGENT 3: SELF-VALIDATOR                                             │   │
│   │ Input:  provisional_guide + validation_reports                      │   │
│   │ Action: Calculer stabilité et confiance                             │   │
│   │ Output: confidence_report.json                                      │   │
│   │         - confidence_score: 0.0 - 1.0                               │   │
│   │         - can_generate_final: bool                                  │   │
│   │         - stable_rules / unstable_rules                             │   │
│   └─────────────────────────────────────────────────────────────────────┘   │
│                                      │                                       │
│                                      ▼                                       │
│   ┌─────────────────────────────────────────────────────────────────────┐   │
│   │ AGENT 4: CONSOLIDATOR                                               │   │
│   │ Input:  provisional_guide + confidence_report                       │   │
│   │ Action: Générer guide final et règles machine-executable            │   │
│   │ Output: stable_guide.md + stable_rules.json                         │   │
│   │         OU rejection_message si confiance trop basse                │   │
│   └─────────────────────────────────────────────────────────────────────┘   │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
                                      │
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                         ÉTAPE 4: EXTRACTION OBJETS                           │
│                                                                              │
│   extract_objects.py                                                         │
│   ├─ Pour chaque page:                                                      │
│   │   ├─ Classifier: LEGEND / PLAN / OTHER                                  │
│   │   └─ Extraire:                                                          │
│   │       ├─ ROOMS: id, name, number, dimensions, bbox                      │
│   │       ├─ DOORS: id, number, swing_angle, bbox                           │
│   │       ├─ WINDOWS: id, length, orientation                               │
│   │       └─ DIMENSIONS: id, value_text, start, end                         │
│   └─ Output: extracted_objects.json                                         │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
                                      │
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                         ÉTAPE 5: CONSTRUCTION RAG                            │
│                                                                              │
│   build_rag.py                                                               │
│   ├─ Indexer tous les objets                                                │
│   ├─ Créer relations (room ↔ doors, dimensions ↔ rooms)                     │
│   └─ Output:                                                                │
│       ├─ index.json        # Index principal                                │
│       ├─ rooms.json        # Tous les locaux                                │
│       ├─ doors.json        # Toutes les portes                              │
│       ├─ dimensions.json   # Toutes les cotes                               │
│       └─ pages/*.json      # Données par page                               │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
                                      │
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                         ÉTAPE 6: QUERY                                       │
│                                                                              │
│   query_rag.py "dimensions classe 204"                                       │
│   ├─ Parse query                                                            │
│   ├─ Search index                                                           │
│   └─ Return structured results                                              │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

## Formats de Données

### Dimension (pieds-pouces)

```json
{
  "value_text": "25'-6\"",
  "feet": 25,
  "inches": 6,
  "total_inches": 306,
  "is_approximate": false
}
```

### Room

```json
{
  "id": "room-204",
  "name": "CLASSE",
  "number": "204",
  "bloc": "B",
  "floor": 2,
  "dimensions": {
    "width": "16'-0\"",
    "depth": "12'-6 5/8\"",
    "area_sqft": 200
  },
  "bbox": [x1, y1, x2, y2],
  "page": 4,
  "confidence": 0.92
}
```

### Door

```json
{
  "id": "door-204-1",
  "number": "204-1",
  "type": "swing",
  "swing_angle": 90,
  "bbox": [x1, y1, x2, y2],
  "room_id": "room-204",
  "page": 4,
  "confidence": 0.85
}
```

## Score de Confiance

Le pipeline calcule un score de confiance pour chaque extraction:

| Score | Interprétation | Action |
|-------|----------------|--------|
| 0.9-1.0 | Excellent | Utiliser directement |
| 0.7-0.9 | Bon | Utilisable, vérification recommandée |
| 0.5-0.7 | Moyen | Revue manuelle nécessaire |
| <0.5 | Faible | Ne pas utiliser, analyse manuelle |

## Technologies

- **Vision AI:** Claude (Anthropic) — meilleure compréhension plans techniques
- **Extraction PDF:** pdftoppm (poppler) — qualité optimale
- **Format données:** JSON — interopérable et searchable
- **Unités:** Pieds-pouces (standard Québec)
