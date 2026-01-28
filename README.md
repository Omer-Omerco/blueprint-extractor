# Blueprint Extractor 🏗️

Extraction de données structurées de plans de construction québécois via PyMuPDF.

## Features

- **Extraction vectorielle** — Texte et dessins directement du PDF (pas d'OCR)
- **Détection de locaux** — Numéros et noms (ex: "204", "CLASSE")
- **Détection de dimensions** — Format pieds-pouces québécois (ex: `25'-6"`)
- **Classification de pages** — LEGEND, PLAN, DETAIL, ELEVATION
- **Pipeline 4 agents** — Guide Builder → Applier → Validator → Consolidator

## Quick Start

```bash
# Setup
cd blueprint-extractor
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# Extract vectors from PDF page 12
python scripts/extract_pdf_vectors.py "plans.pdf" -p 12 -o output/vectors.json

# Detect rooms
python scripts/room_detector.py output/vectors.json -o output/rooms.json

# Detect dimensions
python scripts/dimension_detector.py output/vectors.json -o output/dimensions.json
```

## Scripts

| Script | Description |
|--------|-------------|
| `extract_pdf_vectors.py` | PDF → texte + dessins vectoriels |
| `room_detector.py` | Détection numéros/noms de locaux |
| `dimension_detector.py` | Détection dimensions pieds-pouces |
| `door_detector.py` | Détection portes (arcs 90°) |
| `page_classifier.py` | Classification type de page |
| `page_selector.py` | Sélection pages optimales |
| `pipeline_orchestrator.py` | Pipeline complet 4 agents |

## Formats supportés

### Dimensions (Quebec standard)
- `25'-6"` → 306 pouces
- `12'-6 5/8"` → 150.625 pouces
- `8'-0"` → 96 pouces

### Types de pages
- **LEGEND** — Légende des symboles
- **PLAN** — Plans d'étage avec locaux
- **DETAIL** — Détails de construction
- **ELEVATION** — Élévations/façades

## Tests

```bash
pytest tests/ -v  # 207 tests
```

## Requirements

- Python 3.11+
- PyMuPDF (fitz)
- Pillow
- NumPy

## Limitations

- Fonctionne uniquement sur PDFs vectoriels (pas les scans)
- `door_detector` nécessite des arcs 90° standard

## License

MIT

## Author

Omer-Omerco
