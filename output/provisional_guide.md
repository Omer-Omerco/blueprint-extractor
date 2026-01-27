# Guide Provisoire — École Enfant-Jésus

**Projet:** Réhabilitation de l'École Enfant-Jésus, Sorel-Tracy  
**Client:** Centre de services scolaire de Sorel-Tracy (CSSST 23-333)  
**Architecte:** Francis Lussier Architecture S.A.  
**Dossier:** 24014

## Conventions Identifiées

### 1. Numérotation des Locaux

**Pattern:** `[BLOC]-[NUMÉRO]` ou `[NUMÉRO]` seul

| Format | Exemple | Signification |
|--------|---------|---------------|
| `B-28` | Bloc B, Local 28 | Local avec préfixe de bloc |
| `202` | Local 202 | Numéro seul (2ème étage, local 02) |
| `C-40` | Bloc C, Local 40 | Corridor dans Bloc C |
| `VT-E` | Vestibule E | Code spécial vestibule |

**Blocs identifiés:** A, B, C, D

### 2. Noms de Locaux (français québécois)

| Nom sur plan | Type |
|--------------|------|
| CLASSE | Salle de classe |
| CORRIDOR | Circulation |
| BUREAU | Bureau administratif |
| BUREAU DIRECTION | Direction |
| SALLE DES PROFS | Salle du personnel |
| CONCIERGERIE | Local concierge |
| CHAUFFERIE | Mécanique chauffage |
| SALLE MÉCANIQUE | Local technique |
| VESTIBULE | Entrée |
| TOILETTES | Sanitaires |

### 3. Dimensions (Pieds-Pouces)

**Format standard:** `X'-Y"` ou `X'-Y 1/2"`

**Exemples trouvés:**
- `14'-1 1/2"` (14 pieds 1 pouce et demi)
- `10'-8"` (10 pieds 8 pouces)
- `28'-0"` (28 pieds)
- `21'-4"` (21 pieds 4 pouces)
- `5'-4 1/2"` (5 pieds 4 pouces et demi)

**Échelle:** 1/8" = 1'-0" (standard)

### 4. Symboles — Démolition

| Symbole | Signification |
|---------|---------------|
| Ligne pointillée | Cloison à démolir |
| Ligne tiretée | Élément existant à conserver |
| Hachures croisées (X) | Zone de démolition |
| Cercle avec X | Point spécifique démolition |

### 5. Symboles — Portes

| Symbole | Type |
|---------|------|
| Arc 90° + ligne | Porte simple battante |
| Deux arcs opposés | Porte double |
| Arc pointillé | Porte à démolir |
| Rectangle + seuil | Porte extérieure |

### 6. Symboles — Quincaillerie Électrifiée

| Symbole | Description |
|---------|-------------|
| Cercle + "B" | Bouton d'activation |
| Rectangle + flèche | Ouvre-porte motorisé |
| Triangle | Interphone IP |
| Carré | Contact magnétique |
| Losange | Serrure électrifiée |

---

## Règles d'Extraction (Candidates)

```json
[
  {
    "rule_id": "R001",
    "target": "room_number",
    "pattern": "[A-D]-\\d{2,3}|\\d{3}",
    "confidence": 0.85,
    "description": "Numéro de local avec ou sans préfixe de bloc"
  },
  {
    "rule_id": "R002",
    "target": "room_name",
    "pattern": "CLASSE|CORRIDOR|BUREAU|VESTIBULE|TOILETTES|CHAUFFERIE",
    "confidence": 0.90,
    "description": "Nom de local en majuscules"
  },
  {
    "rule_id": "R003",
    "target": "dimension",
    "pattern": "\\d{1,3}'-\\d{1,2}(\\s+\\d/\\d)?\"",
    "confidence": 0.88,
    "description": "Dimension pieds-pouces avec fractions optionnelles"
  },
  {
    "rule_id": "R004",
    "target": "door",
    "pattern": "arc_90_degrees",
    "confidence": 0.82,
    "description": "Porte = arc de 90° partant d'une ouverture murale"
  },
  {
    "rule_id": "R005",
    "target": "demolition",
    "pattern": "dashed_line_or_cross_hatch",
    "confidence": 0.85,
    "description": "Éléments à démolir = pointillés ou hachures"
  }
]
```

---

## Pages Analysées

1. **A-000** — Page de garde, index des dessins
2. **A-050** — Plan d'implantation, légende symboles site
3. **A-051** — Notes générales, codes, quincaillerie
4. **A-100** — Bloc A, plans 1er/2ème étage (démolition)
5. **A-101** — Blocs B/C, plan 1er étage (démolition)

---

## Incertitudes

- [ ] Format exact superficie (pi² ou m²?) — à valider
- [ ] Symboles fenêtres pas encore identifiés clairement
- [ ] Hauteurs de plafond non visibles sur plans analysés
- [ ] Distinction murs porteurs vs cloisons à confirmer

---

*Guide généré le 2026-01-27 par Clawdbot (Agent 1: Guide Builder)*
