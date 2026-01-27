# Patterns de Locaux — Construction Québec

## Nomenclature Standard

### Types de Locaux (français québécois)

| Terme | Anglais | Description |
|-------|---------|-------------|
| CLASSE | Classroom | Salle de classe |
| CORRIDOR | Corridor | Couloir |
| VESTIBULE | Vestibule | Entrée |
| BUREAU | Office | Bureau |
| CHAUFFERIE | Boiler Room | Salle de chaudière |
| GYMNASE | Gymnasium | Gym |
| CAFÉTÉRIA | Cafeteria | Cantine |
| TOILETTE | Restroom | Salle de bain |
| SALLE MÉCANIQUE | Mechanical Room | Local technique |
| SALLE MULTIFONCTIONNELLE | Multi-purpose Room | Salle polyvalente |
| BIBLIOTHÈQUE | Library | Bibliothèque |
| SECRÉTARIAT | Secretary | Accueil |
| DÉPÔT | Storage | Rangement |
| LOCAL TECHNIQUE | Technical Room | Local équipement |
| VESTIAIRE | Locker Room | Vestiaire |
| SERVICE DE GARDE | Daycare | Garderie |
| MATERNELLE | Kindergarten | Pré-scolaire |

### Format de Numérotation

```
[BLOC] + [ÉTAGE] + [NUMÉRO SÉQUENTIEL]
```

#### Exemples

| Numéro | Bloc | Étage | Séquence | Description |
|--------|------|-------|----------|-------------|
| 101 | A | 1 (RDC) | 01 | Premier local RDC |
| 204 | A | 2 | 04 | Quatrième local 2e étage |
| 204-1 | A | 2 | 04 | Sous-division du local 204 |
| B-115 | B | 1 | 15 | Local 15 du Bloc B |

### Regex Patterns

```regex
# Numéro simple: 204
^(\d{3})$

# Avec sous-division: 204-1
^(\d{3})-(\d+)$

# Avec bloc: B-115
^([A-Z])-?(\d{3})$

# Format complet: CLASSE 204
^(CLASSE|BUREAU|LOCAL|CORRIDOR)\s+(\d{3}(?:-\d+)?)$
```

### Structure des Blocs (exemple école)

```
BLOC C (1 étage) — Gymnase, service de garde
    ↓ (liaison)
BLOC B (1 étage) — Vestibule, cafétéria, classes
    ↓ (liaison)
BLOC A (2 étages + vide sanitaire) — Classes, admin
```

### Détection sur Plans

Les locaux sont généralement identifiés par:
1. **Texte centré** dans l'espace du local
2. **Format:** NOM + NUMÉRO (ex: CLASSE 204)
3. **Encadré** ou avec tag de référence

```python
def parse_room_label(text: str) -> dict:
    """Parse room label like 'CLASSE 204' or 'CORRIDOR 211'."""
    import re
    
    # Pattern: NAME NUMBER or just NUMBER
    match = re.match(r"^([A-ZÉÈÊËÀÂÄÙÛÜÔÖÎÏ\s]+)?\s*(\d{3}(?:-\d+)?)$", text.strip())
    if not match:
        return None
    
    name = (match.group(1) or "LOCAL").strip()
    number = match.group(2)
    
    # Extract floor from number
    floor = int(number[0]) if number[0].isdigit() else 1
    
    return {
        "name": name,
        "number": number,
        "floor": floor,
        "bloc": None,  # À déterminer par position
        "original": text
    }
```
