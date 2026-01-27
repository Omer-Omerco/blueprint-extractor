# Blueprint Extractor

🏗️ Skill ClawdBot pour l'analyse intelligente de plans de construction québécois.

## Fonctionnalités

- **Extraction PDF** → Images haute résolution (300 DPI)
- **Pipeline 4-agents** → Analyse vision AI avec validation croisée
- **RAG JSON** → Index searchable des données extraites
- **Unités québécoises** → Pieds et pouces (25'-6")

## Installation

### Dépendances système

```bash
# macOS
brew install poppler

# Ubuntu/Debian
apt-get install poppler-utils
```

### Dépendances Python

```bash
pip install anthropic
```

## Usage

### 1. Extraire les pages d'un PDF

```bash
python scripts/extract_pages.py /path/to/plans.pdf -o ./pages/

# Options
-p, --pages     Plage de pages (ex: 1-5, 1,3,5, 1-3,7-9)
--dpi           Résolution (défaut: 300)
-q, --quiet     Mode silencieux
```

### 2. Analyser avec le pipeline

```bash
python scripts/analyze_project.py ./pages/ -o ./analysis/
```

### 3. Extraire les objets

```bash
python scripts/extract_objects.py ./analysis/ -o ./rag/
```

### 4. Construire le RAG

```bash
python scripts/build_rag.py ./rag/
```

### 5. Rechercher

```bash
python scripts/query_rag.py ./rag/ "dimensions classe 204"
```

## Architecture

```
┌─────────────────┐
│   PDF Plans     │
└────────┬────────┘
         ▼
┌─────────────────┐
│ extract_pages   │ → Images PNG haute résolution
└────────┬────────┘
         ▼
┌─────────────────────────────────────────────┐
│            PIPELINE 4-AGENTS                │
├─────────────────────────────────────────────┤
│ Agent 1: Guide Builder    → Guide provisoire│
│ Agent 2: Guide Applier    → Validation      │
│ Agent 3: Self-Validator   → Score confiance │
│ Agent 4: Consolidator     → Guide final     │
└────────┬────────────────────────────────────┘
         ▼
┌─────────────────┐
│ extract_objects │ → Rooms, Doors, Dimensions
└────────┬────────┘
         ▼
┌─────────────────┐
│   build_rag     │ → Index JSON searchable
└────────┬────────┘
         ▼
┌─────────────────┐
│   query_rag     │ → Recherche sémantique
└─────────────────┘
```

## Structure RAG

```json
{
  "rooms": [
    {
      "id": "room-204",
      "name": "CLASSE",
      "number": "204",
      "dimensions": {
        "width": "16'-0\"",
        "depth": "12'-6 5/8\"",
        "area_sqft": 200
      },
      "bloc": "B",
      "floor": 2
    }
  ]
}
```

## Documentation

- [SKILL.md](SKILL.md) — Documentation ClawdBot
- [SPECS.md](SPECS.md) — Spécifications fonctionnelles
- [API_SCHEMA.md](API_SCHEMA.md) — Architecture pipeline
- [docs/DEVELOPMENT.md](docs/DEVELOPMENT.md) — Journal de développement

## Références

- [dimension_patterns.md](references/dimension_patterns.md) — Patterns pieds-pouces
- [room_patterns.md](references/room_patterns.md) — Noms locaux québécois
- [symbol_patterns.md](references/symbol_patterns.md) — Symboles architecturaux

## Développement

Développé par Omer 🦉 avec une équipe de 3 sub-agents:
- Agent 1: PDF Extractor
- Agent 2: Pattern References
- Agent 3: Vision Prompts

Voir [docs/DEVELOPMENT.md](docs/DEVELOPMENT.md) pour le journal complet.

## Licence

Propriétaire — Omerco
