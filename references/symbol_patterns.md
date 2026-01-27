# Symboles de Plans Architecturaux — Québec

## Symboles de Démolition

| Symbole | Description | Apparence |
|---------|-------------|-----------|
| ---X--- | Mur à démolir | Ligne avec X espacés |
| ═══════ | Plancher à démolir | Double ligne |
| ░░░░░░░ | Zone hachurée démolition | Hachurage diagonal |
| ▓▓▓▓▓▓▓ | Élément existant à conserver | Hachurage dense |

## Symboles de Portes

| Symbole | Type | Description |
|---------|------|-------------|
| Arc 90° | Porte standard | Arc indique le sens d'ouverture |
| Arc 180° | Porte double | Deux battants |
| Rectangle | Porte coulissante | Pas d'arc |
| Cercle | Porte pivotante | Rotation centrale |

### Détection Géométrique

```python
def detect_door_symbol(elements):
    """Detect door by arc + line pattern."""
    # Une porte = arc de cercle + ligne (battant)
    # L'arc indique l'angle d'ouverture (généralement 90°)
    pass
```

## Symboles de Fenêtres

| Symbole | Type |
|---------|------|
| ═══════ | Fenêtre fixe |
| ══╪══ | Fenêtre ouvrante |
| ══◊══ | Fenêtre à battant |

### Caractéristiques
- Lignes parallèles dans le mur
- Largeur variable (indiquée par cotation)
- Orientées vers l'extérieur

## Notes et Références

| Symbole | Signification |
|---------|---------------|
| ① ② ③ | Note numérotée (cercle) |
| ▲ | Renvoi vers détail |
| ◊ | Note losange |
| ■ | Référence section |

### Tags de Finition (exemple)

```
┌─────┐
│ 23  │  ← Numéro de finition plancher
├─────┤
│ 52  │  ← Numéro de finition mur
└─────┘
```

## Symboles Mécaniques (sur plans archi)

| Symbole | Description |
|---------|-------------|
| ⊗ | Diffuseur plafond |
| ▢ | Grille de retour |
| ◯ | Luminaire |
| ⬡ | Détecteur fumée |

## Échelles Standards

| Échelle | Usage |
|---------|-------|
| 1:100 | Plans d'étage |
| 1:50 | Détails importants |
| 1:20 | Détails construction |
| 1:10 | Détails menuiserie |
| 1:5 | Détails fins |

## Légende Type (LÉGENDE-SYMBOLES)

Les plans incluent généralement une légende en page 1 ou dans un cartouche:

```
LÉGENDE-SYMBOLES — DÉMOLITION PLANCHERS

---X---  Cloison plâtre à démolir
═══════  Éléments à démolir
░░░░░░░  Zone d'intervention amiante
▓▓▓▓▓▓▓  Éléments existants à conserver
```

## Cartouche Standard

```
┌────────────────────────────────────────┐
│ CLIENT:          [Nom client]          │
│ PROJET:          [Nom projet]          │
│ TITRE DU DESSIN: [Description]         │
│ NO DOSSIER:      [24014]               │
│ NO DOSSIER CLIENT: [23-333]            │
│ ÉCHELLE:         [1:100]               │
│ DESSINÉ PAR:     [Initiales]           │
│ VÉRIFIÉ PAR:     [Initiales]           │
│ DATE:            [YYYY-MM-DD]          │
│ DIVISION:        [A]  PAGE: [100]      │
└────────────────────────────────────────┘
```

Ce cartouche permet d'identifier:
- Le projet
- Le type de plan (A=Archi, S=Structure, M=Méca, E=Élec)
- La page/feuille
