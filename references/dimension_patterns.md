# Patterns de Dimensions — Construction Québec

## Format Standard

Au Québec, les dimensions de construction sont en **pieds et pouces** (impérial).

### Patterns Regex

```regex
# Format standard: 25'-6"
(\d+)'-(\d+)"

# Avec fractions: 12'-6 5/8"
(\d+)'-(\d+)\s*(\d+\/\d+)?"

# Avec symbole ±: ±8'-0"
[±]?\s*(\d+)'-(\d+)[\s\d\/]*"

# Dimension totale (pouces seulement): 306"
(\d+)"
```

### Exemples Réels

| Notation | Pieds | Pouces | Total pouces |
|----------|-------|--------|--------------|
| 25'-6" | 25 | 6 | 306 |
| ±8'-0" | 8 | 0 | 96 |
| 12'-6 5/8" | 12 | 6.625 | 150.625 |
| 16'-0" | 16 | 0 | 192 |
| 30'-0" | 30 | 0 | 360 |

### Conversion

```python
def feet_inches_to_total_inches(feet: int, inches: float) -> float:
    """Convert feet-inches to total inches."""
    return (feet * 12) + inches

def parse_dimension(text: str) -> dict:
    """Parse dimension string like 25'-6" or ±12'-6 5/8"."""
    import re
    
    # Remove ± symbol
    text = text.replace('±', '').strip()
    
    # Match feet'-inches"
    match = re.match(r"(\d+)'-(\d+)\s*(\d+\/\d+)?\"?", text)
    if not match:
        return None
    
    feet = int(match.group(1))
    inches = int(match.group(2))
    
    # Handle fraction
    if match.group(3):
        num, den = match.group(3).split('/')
        inches += int(num) / int(den)
    
    return {
        "feet": feet,
        "inches": inches,
        "total_inches": feet_inches_to_total_inches(feet, inches),
        "original": text
    }
```

### Superficie

- Unité: **pi²** (pieds carrés) ou **sq ft**
- Calcul: largeur (pouces) × profondeur (pouces) ÷ 144

```python
def calculate_area_sqft(width_inches: float, depth_inches: float) -> float:
    """Calculate area in square feet."""
    return (width_inches * depth_inches) / 144
```

### Symboles Courants sur Plans

| Symbole | Signification |
|---------|---------------|
| ± | Dimension approximative |
| E.O. | Égal Opposé |
| C.L. | Centre Ligne |
| T.O.S. | Top of Slab |
| B.O.S. | Bottom of Slab |
