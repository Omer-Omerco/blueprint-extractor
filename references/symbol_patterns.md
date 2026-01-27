# Symbol Patterns - Plans Architecturaux Québécois

## Symboles Standards

### Murs

| Symbole | Description | Détection Visuelle |
|---------|-------------|-------------------|
| █████ | Mur existant | Ligne épaisse continue, rempli noir |
| ▓▓▓▓▓ | Mur à construire | Ligne épaisse, parfois hachuré |
| ░░░░░ | Mur à démolir | Ligne pointillée ou hachuré X |
| ┃ ┃ | Mur intérieur | Double ligne parallèle |
| ║ ║ | Mur extérieur | Double ligne plus épaisse |
| ╳╳╳╳ | Démolition | Hachures croisées ou cloudé |

### Patterns de Démolition
```
Lignes pointillées: ---- ---- ----
Hachures croisées:  ╳ ╳ ╳ ╳ ╳
Cloud/Nuage:        ☁ (contour ondulé)
Couleur:            Souvent en ROUGE ou JAUNE
```

---

## Portes

### Types de Portes

| Symbole | Type | Description |
|---------|------|-------------|
| ⌒ | Porte simple | Arc de 90° indiquant le sens d'ouverture |
| ⌓ | Porte double | Deux arcs opposés |
| ⊏ | Porte coulissante | Ligne avec flèche directionnelle |
| ⟲ | Porte pivotante | Cercle avec pivot central |
| ⫽ | Porte pliante | Ligne en accordéon |

### Annotations de Portes
```
P-01   → Numéro de porte (référence à schedule)
3'-0"  → Largeur
A      → Type (selon légende)
90°    → Angle d'ouverture
```

### Pattern de Porte (Arc)
```
     ╭────╮
     │    │
     │    │  ← Cadre
─────╯    ╰─────
      ╲
       ╲   ← Arc d'ouverture (rayon = largeur porte)
        ╲
```

---

## Fenêtres

### Types de Fenêtres

| Symbole | Type | Description |
|---------|------|-------------|
| ═══ | Fenêtre fixe | Trois lignes parallèles dans le mur |
| ⊞ | Fenêtre à battant | Croix ou X dans le cadre |
| ↔ | Fenêtre coulissante | Flèches horizontales |
| ↕ | Fenêtre guillotine | Flèches verticales |

### Annotations de Fenêtres
```
F-01   → Numéro de fenêtre
4'-0" × 5'-0"  → Largeur × Hauteur
2'-6" A.F.F.   → Hauteur d'allège (Above Finished Floor)
```

### Pattern de Fenêtre
```
████╔═══╗████
    ║   ║      ← Vitrage (lignes fines)
████╚═══╝████
```

---

## Symboles de Référence

### Numéros de Détail/Coupe

```
    ╭───╮
    │ 5 │   ← Numéro de détail
    ├───┤
    │A-3│   ← Feuille de référence
    ╰───╯
```

### Cercle de Référence
```
    ( 5 )     → Numéro de détail
    ─────     → Ligne de coupe
    A-301     → Feuille où voir le détail
```

### Flèche de Coupe
```
    ◄─────────────►
    ↓             ↓
   A-3           A-3
   
Direction de vue ───►
```

### Symboles de Niveau

```
    ▽ 100'-0"   → Niveau de référence (benchmark)
    △ +12'-0"   → Élévation relative
    ○ FFE       → Finished Floor Elevation
```

---

## Symboles Électriques/Mécaniques

### Électrique

| Symbole | Description |
|---------|-------------|
| ⊕ | Luminaire au plafond |
| ◎ | Luminaire encastré |
| ⊙ | Prise de courant |
| ⊛ | Prise double |
| ▣ | Panneau électrique |
| ⚡ | Interrupteur |

### Mécanique (CVAC)

| Symbole | Description |
|---------|-------------|
| □ | Diffuseur d'air |
| ○ | Grille de retour |
| ⊞ | Registre |
| ═══ | Conduit |
| ─── | Tuyauterie |

### Plomberie

| Symbole | Description |
|---------|-------------|
| ◇ | Drain de plancher |
| ⊡ | Lavabo |
| ⬭ | Toilette |
| ⬬ | Urinoir |

---

## Annotations Textuelles

### Abréviations Courantes

| Abrév. | Signification |
|--------|---------------|
| EX. | Existant |
| NOUV. | Nouveau |
| DÉM. | À démolir |
| TYP. | Typique |
| SIM. | Similaire |
| V.I.F. | Vérifier in field |
| N.T.S. | Not to scale |
| MIN. | Minimum |
| MAX. | Maximum |
| APPROX. | Approximatif |
| RÉF. | Référence |
| VOIR | Voir détail/plan |
| N/A | Non applicable |

### Notes de Construction

| Note | Signification |
|------|---------------|
| PHASE 1 | Travaux première phase |
| PHASE 2 | Travaux deuxième phase |
| ALT. | Alternatif/Option |
| COND. | Conditionnel |
| PROP. | Proposé |
| APPR. | Approuvé |

---

## Patterns de Détection Visuelle

### Contours de Démolition (Cloud)
```
Caractéristiques:
- Contour ondulé/nuageux autour des éléments
- Couleur: souvent rouge ou magenta
- Texte: "DÉM." ou "À DÉMOLIR" à proximité
- Hachures croisées à l'intérieur
```

### Nouveau vs Existant
```
EXISTANT:
- Lignes grises ou noires fines
- Parfois en arrière-plan (light gray)

NOUVEAU:
- Lignes noires épaisses
- Remplissage solid
- Annotation "NOUV." possible
```

### Limites de Travaux
```
─ ─ ─ ─ ─   Ligne tiretée: limite de contrat
─ · ─ · ─   Ligne mixte: limite de propriété
═══════════  Ligne double: limite de phase
```

---

## Extraction de Symboles

### Ordre de Priorité
1. **Murs** - Structure de base
2. **Portes** - Ouvertures principales
3. **Fenêtres** - Ouvertures secondaires
4. **Annotations** - Numéros et notes
5. **Symboles MEP** - Si présents

### Tips OCR/Vision
- Les symboles sont souvent standardisés (CAD blocks)
- Chercher les répétitions pour identifier les patterns
- Les légendes définissent les symboles spécifiques au projet
- La couleur peut indiquer le statut (existant/nouveau/démolir)

---

## Légende Standard (Template)

```
LÉGENDE DES SYMBOLES

███████  MUR EXISTANT À CONSERVER
▓▓▓▓▓▓▓  MUR NOUVEAU
╳╳╳╳╳╳╳  MUR EXISTANT À DÉMOLIR

⌒        PORTE (arc = sens ouverture)
═══      FENÊTRE
◇        DRAIN DE PLANCHER

⊕        LUMINAIRE
⊙        PRISE ÉLECTRIQUE

─────    LIMITE DES TRAVAUX
─ ─ ─    DÉMOLITION

NOTE: SE RÉFÉRER AUX PLANS SPÉCIALISÉS
      POUR DÉTAILS MEP
```
