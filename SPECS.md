# Blueprint Extractor - Specifications

## Overview
Skill ClawdBot pour l'analyse intelligente de plans de construction et l'extraction de données vers un RAG complet.

## Contexte
- **Industrie:** Construction commerciale/industrielle au Québec
- **Unités:** PIEDS ET POUCES (impérial) - JAMAIS métrique
- **Formats:** PDF de plans architecturaux, structuraux, mécaniques, électriques

## Architecture 4-Agents

### Agent 1: GUIDE BUILDER
- Input: 5 pages sélectionnées (LEGEND first, puis PLAN)
- Action: Analyser images, identifier patterns, symboles
- Output: 
  - provisional_guide (markdown)
  - observations: [{type, description, page}]
  - candidate_rules: [{rule, confidence}]
  - legend_extractions: [{symbol, meaning}]

### Agent 2: GUIDE APPLIER
- Input: provisional_guide + 3-5 validation pages
- Action: Tester chaque règle sur chaque page
- Output: validation_reports
  - CONFIRMED: règle validée
  - CONTRADICTED: règle invalide
  - NOT_TESTABLE: pas applicable
  - VARIATION: légère variation

### Agent 3: SELF-VALIDATOR
- Input: provisional_guide + validation_reports
- Action: Analyser stabilité des règles
- Output: ConfidenceReport
  - can_generate_final: bool
  - confidence_score: 0.0 - 1.0
  - stable_count / partial_count / unstable_count

### Agent 4: CONSOLIDATOR
- Input: provisional_guide + ConfidenceReport
- Action: Générer guide stable + payloads machine-executable
- Output: ConsolidatorResult
  - stable_guide: markdown
  - stable_rules_json: [{kind, token_type, pattern, ...}]

## Extraction Pipeline

### Objets à extraire:
1. **ROOMS (Locaux)**
   - id, name, number, bbox, confidence
   - dimensions en pieds-pouces (ex: 25'-6" x 30'-0")
   - superficie en pi²

2. **DOORS (Portes)**
   - id, number, bbox, swing_angle, confidence

3. **WINDOWS (Fenêtres)**
   - id, length, orientation, confidence

4. **DIMENSIONS**
   - id, value_text (format: X'-Y"), start, end, confidence

## Output RAG Structure

```
project-name/
├── index.json              # Index principal searchable
├── guide.md                # Guide stable généré
├── rooms.json              # Tous les locaux avec dimensions
├── doors.json              # Toutes les portes
├── dimensions.json         # Toutes les cotes
├── legend.json             # Symboles et significations
└── pages/
    ├── page-001.json       # Données par page
    ├── page-002.json
    └── ...
```

## Format des dimensions (IMPORTANT)

```json
{
  "width": "25'-6\"",
  "depth": "30'-0\"", 
  "area_sqft": 765,
  "raw_values": ["25'-6\"", "30'-0\""]
}
```

## Intégration ClawdBot

Le skill doit:
1. Accepter un chemin vers un PDF ou dossier de PDFs
2. Extraire les pages en images haute résolution
3. Exécuter le pipeline 4-agents
4. Générer le RAG complet
5. Permettre des queries sur les données extraites

## Dépendances suggérées
- pdftoppm / poppler (extraction PDF → images)
- Vision AI (Claude, GPT-4V) pour analyse des plans
- PyMuPDF ou pdfplumber pour extraction texte
- jq pour manipulation JSON

## Commandes du skill

```bash
# Analyser un projet
blueprint-extract /path/to/plans.pdf --output ./rag-output/

# Query le RAG
blueprint-query "dimensions classe 204" --project ./rag-output/

# Lister les locaux
blueprint-rooms --project ./rag-output/
```

## Références
- Plans test: ~/Library/CloudStorage/GoogleDrive-omer@omerco.com/Mon disque/Projet Ecole Mario/
- Exemple: C25-256 _Architecture_plan_Construction.pdf (35 pages)
