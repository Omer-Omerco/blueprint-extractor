# Blueprint Extractor

🏗️ Skill ClawdBot pour l'analyse intelligente de plans de construction québécois.

## Fonctionnalités

- **Extraction PDF** → Images haute résolution (300 DPI)
- **Pipeline 4-agents** → Analyse vision AI avec validation croisée
- **Extraction de produits** → Manufacturiers et modèles depuis devis
- **RAG JSON** → Index searchable des données extraites
- **Unités québécoises** → Pieds et pouces (25'-6", 8'-6 1/2")

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
# Installation standard
pip install anthropic

# Installation développement (avec tests)
pip install -r requirements-dev.txt
```

### Configuration environnement virtuel (recommandé)

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.txt
```

### Variable d'environnement

```bash
export ANTHROPIC_API_KEY="sk-ant-..."
```

## Usage

### 1. Extraire les pages d'un PDF

```bash
python scripts/extract_pages.py /path/to/plans.pdf -o ./pages/

# Options
--dpi           Résolution (défaut: 300)
--json          Sortie manifest JSON
```

### 2. Analyser avec le pipeline 4-agents

```bash
python scripts/analyze_project.py ./pages/ -o ./analysis/

# Options
--model         Modèle Claude (défaut: claude-sonnet-4-20250514)
--max-pages     Limite de pages à analyser
--api-key       Clé API (ou ANTHROPIC_API_KEY)
```

### 3. Extraire les objets

```bash
python scripts/extract_objects.py ./analysis/guide.json --pages ./pages/ -o ./output/

# Options
--max-pages     Limite de pages
--json          Sortie JSON
```

### 4. Construire le RAG

```bash
python scripts/build_rag.py ./output/ -o ./rag/
```

### 5. Rechercher dans le RAG

```bash
# Recherche textuelle
python scripts/query_rag.py ./rag/ "dimensions classe 204"

# Mode interactif
python scripts/query_rag.py ./rag/

# Options
-t, --type      Filtrer par type (room, door, window, dimension, symbol)
-p, --page      Filtrer par numéro de page
-n, --limit     Nombre max de résultats (défaut: 20)
--json          Sortie JSON
```

### 6. Extraire les produits d'un devis (optionnel)

```python
from scripts.extract_products import extract_products_from_raw_text

text = "Armstrong | DUNE-2120 Tuiles acoustiques"
products = extract_products_from_raw_text(text)
# [{'manufacturer': 'Armstrong', 'model': 'DUNE-2120', ...}]
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

## Structure des fichiers

```
blueprint-extractor/
├── scripts/
│   ├── extract_pages.py      # PDF → PNG
│   ├── analyze_project.py    # Pipeline 4-agents
│   ├── extract_objects.py    # Vision → JSON
│   ├── build_rag.py          # JSON → RAG index
│   ├── query_rag.py          # Recherche RAG
│   ├── extract_products.py   # Extraction produits devis
│   ├── extract_sections.py   # Parsing sections CSI
│   ├── parse_devis.py        # Parser devis complet
│   └── build_unified_rag.py  # RAG unifié plans+devis
├── tests/
│   ├── conftest.py           # Fixtures pytest
│   ├── test_*.py             # Tests unitaires et intégration
│   └── fixtures/             # Données de test
├── references/               # Patterns de référence
├── docs/                     # Documentation technique
└── output/                   # Résultats (gitignored)
```

## Structure RAG

```json
{
  "version": "1.0",
  "stats": {
    "rooms": 25,
    "doors": 40,
    "dimensions": 150,
    "total_entries": 215
  },
  "entries": [
    {
      "type": "room",
      "id": "room-204",
      "name": "CLASSE",
      "number": "204",
      "page": 3,
      "dimensions": {
        "width": "25'-6\"",
        "depth": "30'-0\"",
        "area_sqft": 765
      },
      "width_parsed": {
        "feet": 25,
        "inches": 6,
        "total_inches": 306,
        "decimal_feet": 25.5
      },
      "search_text": "classe 204 local pièce salle 765 pi²"
    }
  ]
}
```

## Formats de dimensions supportés

Le parseur supporte les formats pieds-pouces québécois :

| Format | Exemple | Total pouces |
|--------|---------|--------------|
| Standard | `25'-6"` | 306 |
| Zéro pouces | `8'-0"` | 96 |
| Fractions | `8'-6 1/2"` | 102.5 |
| | `10'-3 1/4"` | 123.25 |
| | `12'-6 1/8"` | 150.125 |
| Pieds seuls | `25'` | 300 |

## Tests

### Exécuter tous les tests

```bash
# Activer l'environnement virtuel
source .venv/bin/activate

# Tous les tests
pytest tests/ -v

# Tests avec couverture
pytest tests/ -v --cov=scripts --cov-report=term-missing

# Tests spécifiques
pytest tests/test_build_rag.py -v
pytest tests/test_integration.py -v
pytest tests/test_extract_products.py -v
```

### Structure des tests

- `test_extract_pages.py` — Extraction PDF
- `test_analyze_project.py` — Pipeline 4-agents
- `test_extract_objects.py` — Extraction objets
- `test_build_rag.py` — Construction RAG (inclut parsing dimensions)
- `test_query_rag.py` — Recherche RAG
- `test_extract_products.py` — Extraction produits
- `test_integration.py` — Tests end-to-end

### Couverture actuelle

```
203 tests passés
Couverture: scripts principaux et edge cases québécois
```

## Noms de locaux québécois supportés

Les termes suivants sont reconnus et searchables :

| Code | Signification |
|------|---------------|
| CLASSE | Salle de classe |
| CORRIDOR | Couloir de circulation |
| S.D.B. | Salle de bain |
| RANGEMENT | Espace de rangement |
| GYMNASE | Gymnase |
| CAFÉTÉRIA | Cafétéria |
| SECRÉTARIAT | Bureau secrétariat |
| CONCIERGERIE | Local conciergerie |
| ADMIN | Bureau administratif |

## Documentation

- [SKILL.md](SKILL.md) — Documentation ClawdBot
- [USAGE.md](USAGE.md) — Guide d'utilisation détaillé
- [SPECS.md](SPECS.md) — Spécifications fonctionnelles
- [API_SCHEMA.md](API_SCHEMA.md) — Architecture pipeline
- [docs/DEVELOPMENT.md](docs/DEVELOPMENT.md) — Journal de développement

## Références

- [dimension_patterns.md](references/dimension_patterns.md) — Patterns pieds-pouces
- [room_patterns.md](references/room_patterns.md) — Noms locaux québécois
- [symbol_patterns.md](references/symbol_patterns.md) — Symboles architecturaux

## Développement

Développé par Omer 🦉 avec une équipe de sub-agents:
- Agent 1: PDF Extractor
- Agent 2: Pattern References
- Agent 3: Vision Prompts
- Agent 4: QA Engineer

Voir [docs/DEVELOPMENT.md](docs/DEVELOPMENT.md) pour le journal complet.

## Troubleshooting

### "pdfinfo not found"
```bash
brew install poppler  # macOS
apt-get install poppler-utils  # Linux
```

### "ANTHROPIC_API_KEY not set"
```bash
export ANTHROPIC_API_KEY="sk-ant-..."
```

### Tests échouent
```bash
# Vérifier l'environnement virtuel
source .venv/bin/activate
pip install -r requirements-dev.txt
pytest tests/ -v
```

## Licence

Propriétaire — Omerco
