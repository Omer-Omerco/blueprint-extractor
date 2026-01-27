# Dimension Patterns - Plans Québécois

## Format Standard: Pieds-Pouces (Impérial)

Au Québec, les plans de construction utilisent le système impérial:
- **Pieds** (') et **Pouces** (")
- Fractions de pouces: 1/2, 1/4, 1/8, 1/16, 5/8, 3/4, 3/8, 7/8

---

## Patterns Regex

### Pattern Principal (Pieds-Pouces avec Fractions)
```regex
(\d+)'[-\s]?(\d+)(?:\s+(\d+)\/(\d+))?["″]?
```

**Capture:**
- Groupe 1: Pieds (ex: `25`)
- Groupe 2: Pouces (ex: `6`)
- Groupe 3: Numérateur fraction (ex: `5`)
- Groupe 4: Dénominateur fraction (ex: `8`)

### Variantes Courantes

| Pattern | Exemple | Regex |
|---------|---------|-------|
| Standard | `25'-6"` | `(\d+)'[-](\d+)"` |
| Avec espace | `25' 6"` | `(\d+)'\s(\d+)"` |
| Avec fraction | `12'-6 5/8"` | `(\d+)'[-](\d+)\s+(\d+)\/(\d+)"` |
| Tolérance ± | `±8'-0"` | `[±](\d+)'[-](\d+)"` |
| Pieds seuls | `15'-0"` | `(\d+)'[-]0"` |
| Pouces seuls | `6"` | `^(\d+)"$` |
| Fraction seule | `3/4"` | `^(\d+)\/(\d+)"$` |

### Pattern Complet (Tous les Cas)
```regex
[±]?(\d+)'[-\s]?(\d+)(?:\s+(\d+)\/(\d+))?["″]?|^(\d+)["″]$|^(\d+)\/(\d+)["″]$
```

---

## Conversion vers Pouces Totaux

### Formule
```
pouces_totaux = (pieds × 12) + pouces + (numérateur / dénominateur)
```

### Exemples

| Dimension | Calcul | Pouces Totaux |
|-----------|--------|---------------|
| `25'-6"` | (25 × 12) + 6 | **306"** |
| `8'-0"` | (8 × 12) + 0 | **96"** |
| `12'-6 5/8"` | (12 × 12) + 6 + (5/8) | **150.625"** |
| `3'-4 1/2"` | (3 × 12) + 4 + (1/2) | **40.5"** |
| `0'-9 3/4"` | (0 × 12) + 9 + (3/4) | **9.75"** |

### Code de Conversion
```python
def parse_dimension(dim_str):
    """Parse une dimension pieds-pouces vers pouces totaux."""
    import re
    
    # Pattern: pieds'-pouces fraction"
    pattern = r"[±]?(\d+)'[-\s]?(\d+)(?:\s+(\d+)\/(\d+))?[\"″]?"
    match = re.match(pattern, dim_str.strip())
    
    if match:
        feet = int(match.group(1))
        inches = int(match.group(2))
        frac_num = int(match.group(3)) if match.group(3) else 0
        frac_den = int(match.group(4)) if match.group(4) else 1
        
        return (feet * 12) + inches + (frac_num / frac_den)
    
    return None

# Exemples
parse_dimension("25'-6\"")      # → 306.0
parse_dimension("12'-6 5/8\"")  # → 150.625
```

---

## Exemples Réels de Plans Québécois

### Dimensions Courantes - Salles de Classe
- Largeur standard: `28'-0"` à `32'-0"`
- Profondeur: `30'-0"` à `34'-0"`
- Hauteur plafond: `9'-6"` à `10'-0"`

### Dimensions Courantes - Corridors
- Largeur minimale: `8'-0"`
- Largeur standard: `10'-0"` à `12'-0"`

### Dimensions Courantes - Portes
- Simple: `3'-0"` × `7'-0"`
- Double: `6'-0"` × `7'-0"`
- Accessible: `3'-6"` × `7'-0"`

### Dimensions Courantes - Fenêtres
- Standard: `4'-0"` × `5'-0"`
- Allège: `2'-6"` du plancher

### Épaisseurs de Murs
- Mur intérieur standard: `4 5/8"`
- Mur extérieur: `8"` à `12"`
- Mur coupe-feu: `8"` minimum

---

## Symboles de Dimension

| Symbole | Signification |
|---------|---------------|
| `±` | Tolérance/approximation |
| `~` | Environ |
| `TYP.` | Typique (se répète) |
| `V.I.F.` | Vérifier in field |
| `N.T.S.` | Not to scale |
| `É.` | Égal |
| `@` | À (espacement) |
| `c/c` | Centre à centre |
| `h.f.` | Hors-fini |
| `f.f.` | Face à face |

---

## Notes

- Les plans québécois utilisent parfois des guillemets droits (`"`) ou typographiques (`″`)
- Le tiret entre pieds et pouces peut être un trait d'union (`-`) ou un espace
- Toujours valider les dimensions avec le cartouche pour confirmer l'échelle
