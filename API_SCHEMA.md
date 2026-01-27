# API Schema - Blueprint Extractor

Basé sur le diagramme Plans Vision API.

## 1. Pipeline d'Analyse

```
POST /projects/{id}/analyze
    │
    ▼
┌─────────────────────────────────────────┐
│ VALIDATION                              │
│ ├─ Check project exists                 │
│ ├─ Check status != VALIDATED            │
│ ├─ Check status != PROCESSING           │
│ └─ Check pages count > 0                │
└─────────────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────────────┐
│ PAGE SELECTION (3 niveaux fallback)     │
│                                         │
│ Level 1: Vision AI (5 pages max)        │
│    ↓ fail                               │
│ Level 2: Token Scoring (PyMuPDF)        │
│    ↓ fail                               │
│ Level 3: First N Pages                  │
└─────────────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────────────┐
│ AGENT 1: GUIDE BUILDER                  │
│ Input: 5 SelectedPage                   │
│ Output: provisional_guide + JSON        │
└─────────────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────────────┐
│ AGENT 2: GUIDE APPLIER                  │
│ Input: guide + validation pages         │
│ Output: validation_reports              │
└─────────────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────────────┐
│ AGENT 3: SELF-VALIDATOR                 │
│ Input: guide + reports                  │
│ Output: ConfidenceReport                │
└─────────────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────────────┐
│ AGENT 4: CONSOLIDATOR                   │
│ Input: guide + confidence               │
│ Output: stable_guide + rules_json       │
└─────────────────────────────────────────┘
```

## 2. Pipeline d'Extraction

```
POST /v2/projects/{id}/extract
    │
    ▼
┌─────────────────────────────────────────┐
│ ÉTAPE 1: CLASSIFY PAGES                 │
│ Pour chaque page: LEGEND/PLAN/OTHER     │
└─────────────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────────────┐
│ ÉTAPE 2: EXTRACT OBJECTS (par page)     │
│                                         │
│ ┌─────────┐ ┌─────────┐ ┌─────────┐    │
│ │ ROOMS   │ │ DOORS   │ │DIMENSIONS│   │
│ │Extractor│ │Extractor│ │Extractor │   │
│ └─────────┘ └─────────┘ └─────────┘    │
└─────────────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────────────┐
│ ÉTAPE 3: BUILD INDEX                    │
│ Indexer tous les objets                 │
│ Persister en fichiers JSON              │
└─────────────────────────────────────────┘
```

## 3. Structures de données

### Room
```json
{
  "id": "room-204",
  "name": "CLASSE",
  "number": "204",
  "bbox": [100, 200, 300, 400],
  "dimensions": {
    "width": "25'-6\"",
    "depth": "30'-0\"",
    "area_sqft": 765
  },
  "confidence": 0.95,
  "page": 4,
  "sniper_mode": false
}
```

### Door
```json
{
  "id": "door-204-1",
  "number": "204-1",
  "bbox": [150, 250, 160, 290],
  "swing_angle": 90,
  "confidence": 0.88,
  "page": 4
}
```

### Dimension
```json
{
  "id": "dim-001",
  "value_text": "25'-6\"",
  "value_inches": 306,
  "start": [100, 200],
  "end": [406, 200],
  "confidence": 0.92,
  "page": 4
}
```

### Legend Symbol
```json
{
  "symbol": "---X---",
  "meaning": "Mur à démolir",
  "category": "demolition",
  "page": 1
}
```

## 4. Statuts projet

- `PENDING` - Créé, en attente d'upload
- `UPLOADED` - Pages uploadées
- `PROCESSING` - Analyse en cours
- `VALIDATED` - Guide stable généré
- `PROVISIONAL_ONLY` - Guide instable
- `EXTRACTED` - Objets extraits
- `ERROR` - Erreur pipeline

## 5. Codes d'erreur

| Code | Description |
|------|-------------|
| PROJECT_NOT_FOUND | Projet inexistant |
| NO_PAGES | Aucune page uploadée |
| ALREADY_VALIDATED | Projet déjà validé |
| GUIDE_BUILDER_FAILED | Échec Agent 1 |
| ALL_VALIDATIONS_FAILED | Échec Agent 2 |
| SELF_VALIDATOR_FAILED | Échec Agent 3 |
| CONSOLIDATOR_FAILED | Échec Agent 4 |
| VISION_TIMEOUT | Timeout API vision |
