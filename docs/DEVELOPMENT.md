# Journal de Développement — Blueprint Extractor

## 2026-01-27 — Création Initiale

### Contexte
Alex a demandé de créer un skill pour analyser les plans de construction et extraire les données vers un RAG. Le cas d'usage initial: trouver les dimensions de la classe 204 dans les plans de l'École Enfants Jésus.

### Architecture Multi-Agents

Le développement a été fait en parallèle avec 4 agents:

| Agent | Rôle | Résultat |
|-------|------|----------|
| **CEO (Omer)** | Coordination, SKILL.md, structure | ✅ |
| **Agent 1** | PDF Extractor - Test & amélioration | ✅ |
| **Agent 2** | Pattern References (QC) | ✅ |
| **Agent 3** | Vision Prompts (4 agents) | ✅ |

### Travail du CEO (Session principale)

1. **Créé le repo Git** `/Users/omer/clawd/skills/blueprint-extractor`
2. **Écrit les specs initiales** `SPECS.md` et `API_SCHEMA.md`
3. **Créé le SKILL.md** principal avec documentation
4. **Dispatché les agents** en parallèle
5. **Testé l'extraction PDF** sur le vrai fichier (35 pages)
6. **Créé les références** de base (dimension, room, symbol patterns)
7. **Créé les prompts** pour les 4 agents vision

### Agent 1 — PDF Extractor (agent1-pdf-extractor)

**Mission:** Tester et améliorer `scripts/extract_pages.py`

**Améliorations apportées:**
- Support des plages de pages (`-p 1-5`, `1,3,5`, `1-3,7-9`)
- Affichage de progression (pourcentage, taille, temps)
- Nommage avec zéro-padding (`page-001.png`)
- Manifest complet avec timing et tailles
- Mode silencieux (`-q/--quiet`)

**Test réalisé:**
```
PDF: C25-256 _Architecture_plan_Construction.pdf
Pages: 35 (format A1)
Résolution: 300 DPI → 9934x7017 pixels
Vitesse: ~5.3s/page
Résultat: ✅ Succès
```

**Commit:** `4b2782b feat: tested and improved extract_pages.py`

### Agent 2 — Pattern References (agent2-patterns)

**Mission:** Créer les fichiers de référence pour l'extraction

**Fichiers créés:**

1. **dimension_patterns.md** (3.5 KB)
   - Regex pour pieds-pouces: `25'-6"`, `±8'-0"`, `12'-6 5/8"`
   - Formules de conversion Python
   - Symboles: `TYP.`, `V.I.F.`, `c/c`, `h.f.`

2. **room_patterns.md** (4.4 KB)
   - 40+ noms de locaux en français québécois
   - Catégories: Pédagogique, Administratif, Service, Technique
   - Pattern numérotation: `[BLOC][ÉTAGE][NUMÉRO]`

3. **symbol_patterns.md** (5.3 KB)
   - Symboles murs, portes, fenêtres
   - 30+ abréviations courantes
   - Légende template standard

**Commit:** `414275e feat: added pattern references for QC construction`

### Agent 3 — Vision Prompts (agent3-prompts)

**Mission:** Créer les prompts pour le pipeline 4-agents

**Fichiers créés:**

| Prompt | Rôle | Output |
|--------|------|--------|
| agent1_guide_builder.md | Analyse initiale → guide provisoire | JSON avec règles |
| agent2_guide_applier.md | Validation sur nouvelles pages | JSON taux succès |
| agent3_self_validator.md | Calcul confiance globale | JSON scores |
| agent4_consolidator.md | Guide final + données | JSON production |

**Points clés:**
- PIEDS ET POUCES spécifié partout
- Format JSON documenté avec exemples
- Gestion abréviations québécoises
- Calcul de confiance avec bonus/malus

**Commit:** `45d98a5 feat: added vision prompts for 4-agent pipeline`

### Décisions Techniques

1. **Unités: Pieds et pouces** — Standard industrie construction Québec
2. **Extraction PDF: pdftoppm** — Meilleure qualité que alternatives Python
3. **Vision AI: Claude** — Meilleure compréhension des plans techniques
4. **Format output: JSON** — Facilite intégration et recherche
5. **Pipeline 4-agents** — Validation croisée pour fiabilité

### Fichiers Finaux

```
blueprint-extractor/
├── SKILL.md                 # Documentation principale ClawdBot
├── SPECS.md                 # Spécifications fonctionnelles
├── API_SCHEMA.md            # Architecture pipeline détaillée
├── docs/
│   └── DEVELOPMENT.md       # Ce fichier
├── scripts/
│   ├── extract_pages.py     # Extraction PDF → images
│   ├── analyze_project.py   # Pipeline 4-agents
│   ├── extract_objects.py   # Extraction rooms/doors/dimensions
│   ├── build_rag.py         # Construction index RAG
│   └── query_rag.py         # Recherche dans RAG
├── references/
│   ├── dimension_patterns.md
│   ├── room_patterns.md
│   └── symbol_patterns.md
└── assets/prompts/
    ├── agent1_guide_builder.md
    ├── agent2_guide_applier.md
    ├── agent3_self_validator.md
    └── agent4_consolidator.md
```

### Prochaines Étapes

- [ ] Tester pipeline complet sur PDF réel
- [ ] Valider extraction dimensions classe 204
- [ ] Optimiser performance (caching, parallélisation)
- [ ] Ajouter support multi-PDF (projet complet)
- [ ] Interface CLI complète
