# Blueprint Extractor

Analyse de plans de construction québécois avec extraction vers JSON/RAG.

## ⚠️ RÈGLE ABSOLUE — ZÉRO HALLUCINATION

**JAMAIS inventer d'information.** C'est un projet de construction réel — des erreurs peuvent coûter cher ou être dangereuses.

### Si tu ne trouves pas l'info dans le RAG:
```
❌ INTERDIT: "La peinture est probablement du latex..."
✅ CORRECT:  "Je n'ai pas trouvé cette information dans les documents. 
             Vérifie avec l'architecte ou le devis section XX."
```

### Si tu n'es pas sûr à 100%:
```
❌ INTERDIT: "Le local 204 mesure 25'-6\" x 30'-0\""
✅ CORRECT:  "Selon le plan A-150, le local 204 semble mesurer ~25' x 30', 
             mais je te recommande de vérifier sur le plan."
```

### Toujours citer tes sources:
```
"Selon le devis section 09 91 00, page 45..."
"D'après le plan A-150..."
"Je n'ai pas trouvé cette info — vérifie avec [professionnel]"
```

## Trigger

Utiliser quand l'utilisateur demande d'analyser des plans de construction, blueprints, plans architecturaux, ou d'extraire des informations de PDF de plans.

## Vue d'ensemble

Ce skill extrait les données structurées (locaux, portes, fenêtres, dimensions) de plans de construction PDF en utilisant un pipeline vision à 4 agents.

**Important:** Toutes les dimensions sont en **PIEDS ET POUCES** (standard Québec).

## Workflow

### Étape 1: Extraction des pages (script)

```bash
cd /Users/omer/clawd/skills/blueprint-extractor
source .venv/bin/activate
python scripts/extract_pages.py "/chemin/vers/plans.pdf" -o ./output/pages -p 1-10
```

Ceci génère des images PNG haute résolution (300 DPI) + `manifest.json`.

### Étape 2: Sélection des pages clés

Parmi les pages extraites, identifier visuellement:
1. **LEGEND** (légende des symboles) — priorité maximale
2. **PLANS D'ÉTAGE** (floor plans) — pages avec locaux numérotés

Sélectionner 5 pages max pour l'analyse initiale.

### Étape 3: Pipeline 4 Agents (toi-même)

**Tu ES les 4 agents.** Exécute-les en séquence:

#### Agent 1: Guide Builder
Charge les 5 pages sélectionnées avec le tool `image` et analyse:
- Symboles et leur signification (légende)
- Patterns de cotation (dimensions pieds-pouces)
- Conventions visuelles (portes = arcs, fenêtres = lignes parallèles)
- Noms de locaux (CLASSE, CORRIDOR, S.D.B., etc.)

**Output:** `provisional_guide` (markdown) + `candidate_rules` (JSON)

#### Agent 2: Guide Applier
Charge 3 AUTRES pages et valide chaque règle:
- CONFIRMED: la règle fonctionne
- CONTRADICTED: la règle est fausse
- VARIATION: légère différence acceptable

**Output:** `validation_reports` par page

#### Agent 3: Self-Validator
Analyse les rapports de validation:
- `confidence_score`: 0.0 - 1.0
- `can_generate_final`: true si confidence ≥ 0.7
- `stable_rules`: liste des règles confirmées

#### Agent 4: Consolidator
Génère le guide final:
- `stable_guide.md`: guide markdown lisible
- `stable_rules.json`: règles machine-executable

### Étape 4: Extraction des objets

Pour CHAQUE page, extrais avec vision:

```json
{
  "rooms": [
    {
      "id": "101",
      "name": "CLASSE",
      "dimensions": "25'-6\" x 30'-0\"",
      "area_sqft": 765,
      "page": 3
    }
  ],
  "doors": [
    {
      "id": "P-01",
      "type": "simple",
      "width": "3'-0\"",
      "swing_angle": 90,
      "page": 3
    }
  ],
  "windows": [...],
  "dimensions": [...]
}
```

### Étape 5: Build RAG (script)

```bash
python scripts/build_rag.py ./output -o ./output/rag
```

### Étape 6: Query (script ou toi)

```bash
python scripts/query_rag.py ./output/rag "classe 204"
```

Ou toi directement: lis `./output/rag/index.json` et réponds aux questions.

## Référence Patterns

### Dimensions (pieds-pouces)
- Standard: `25'-6"` (25 pieds 6 pouces)
- Avec fraction: `12'-6 5/8"`
- Conversion: `(pieds × 12) + pouces = pouces totaux`

### Noms de locaux québécois
| Abrév. | Nom complet |
|--------|-------------|
| S.D.B. | Salle de bain |
| W.C. | Toilettes |
| CORR. | Corridor |
| RANG. | Rangement |
| MÉC. | Salle mécanique |
| ÉLEC. | Salle électrique |

### Symboles courants
- **Porte:** Arc 90° avec ligne (direction d'ouverture)
- **Fenêtre:** 3 lignes parallèles dans l'épaisseur du mur
- **Mur existant:** Ligne pleine épaisse
- **Mur à démolir:** Hachuré ou pointillé

## Fichiers du skill

```
blueprint-extractor/
├── SKILL.md                 # Ce fichier
├── scripts/
│   ├── extract_pages.py     # PDF → images (seul script nécessaire en externe)
│   ├── build_rag.py         # Construit l'index RAG
│   └── query_rag.py         # Requêtes RAG
├── references/
│   ├── dimension_patterns.md
│   ├── room_patterns.md
│   └── symbol_patterns.md
├── assets/prompts/          # Prompts pour les 4 agents (référence)
└── tests/                   # Suite de tests pytest
```

## Exemple d'utilisation

**User:** "Analyse le plan de l'école Enfant-Jésus"

**Toi:**
1. Extrais les pages: `python scripts/extract_pages.py "/path/to/C25-256.pdf" -o ./output/pages`
2. Charge 5 pages avec `image` tool
3. Exécute le pipeline 4 agents
4. Sauvegarde les résultats en JSON
5. Build le RAG
6. Réponds aux questions: "La classe 204 fait 25'-6\" x 30'-0\" (765 pi²)"

## Notes

- Les tests passent: `pytest tests/ -v` (129 tests)
- Toujours utiliser pieds-pouces, JAMAIS le métrique
- Confiance minimale pour générer le guide final: 0.7
