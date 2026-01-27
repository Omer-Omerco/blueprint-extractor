---
name: blueprint-extractor
description: Analyse de plans de construction (PDF) et extraction vers RAG JSON. Utiliser pour extraire dimensions, locaux, portes, fenêtres de plans architecturaux. Supporte format Québec (pieds-pouces). Pipeline 4-agents vision AI.
---

# Blueprint Extractor

Extrait les données des plans de construction vers un RAG JSON searchable.

## Cas d'usage

- "Quelles sont les dimensions de la classe 204?"
- "Liste tous les locaux du Bloc A"
- "Trouve les portes du corridor principal"
- "Superficie totale de l'étage 2"

## Quick Start

```bash
# 1. Extraire les pages du PDF
python scripts/extract_pages.py /path/to/plans.pdf --output ./extracted/

# 2. Analyser avec le pipeline 4-agents
python scripts/analyze_project.py ./extracted/ --output ./analysis/

# 3. Extraire les objets (rooms, doors, dimensions)
python scripts/extract_objects.py ./analysis/ --output ./rag/

# 4. Construire le RAG
python scripts/build_rag.py ./rag/

# 5. Query
python scripts/query_rag.py ./rag/ "dimensions classe 204"
```

## Unités — IMPORTANT

**TOUJOURS en pieds et pouces (impérial québécois):**
- Dimensions: `25'-6"`, `±8'-0"`, `12'-6 5/8"`
- Superficie: `pi²` (pieds carrés)

Voir `references/dimension_patterns.md` pour les patterns regex.

## Pipeline 4-Agents

Le skill utilise 4 agents vision pour analyser les plans:

### Agent 1: Guide Builder
Analyse 5 pages sélectionnées (LEGEND first), extrait patterns et règles.

### Agent 2: Guide Applier  
Valide les règles sur 3-5 pages supplémentaires.

### Agent 3: Self-Validator
Calcule un score de confiance (0.0-1.0).

### Agent 4: Consolidator
Génère le guide final et les règles JSON.

Voir `assets/prompts/` pour les prompts de chaque agent.

## Output RAG

```
project-rag/
├── index.json          # Index principal
├── guide.md            # Guide stable
├── rooms.json          # Locaux avec dimensions
├── doors.json          # Portes
├── dimensions.json     # Toutes les cotes
├── legend.json         # Symboles
└── pages/
    └── page-XXX.json   # Données par page
```

### Format Room

```json
{
  "id": "room-204",
  "name": "CLASSE",
  "number": "204",
  "dimensions": {
    "width": "25'-6\"",
    "depth": "30'-0\"",
    "area_sqft": 765
  },
  "bloc": "B",
  "floor": 2
}
```

## Dépendances

- `poppler` (pdftoppm) — extraction PDF
- `anthropic` SDK — Claude vision API
- Python 3.10+

```bash
# macOS
brew install poppler
pip install anthropic

# Ubuntu
apt-get install poppler-utils
pip install anthropic
```

## Références

- `references/dimension_patterns.md` — Patterns pieds-pouces
- `references/room_patterns.md` — Noms locaux québécois
- `references/symbol_patterns.md` — Symboles plans archi
