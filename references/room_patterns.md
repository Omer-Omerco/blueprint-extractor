# Room Patterns - Plans Québécois

## Noms de Locaux en Français Québécois

### Locaux Pédagogiques (Écoles)
| Nom | Variantes | Code |
|-----|-----------|------|
| CLASSE | SALLE DE CLASSE, CL. | CL |
| MATERNELLE | PRÉMATERNELLE | MAT |
| GYMNASE | GYM, SALLE DE GYM | GYM |
| BIBLIOTHÈQUE | BIBLIO, MÉDIATHÈQUE | BIB |
| LABORATOIRE | LABO, LAB. | LAB |
| ATELIER | AT. | AT |
| MUSIQUE | SALLE DE MUSIQUE | MUS |
| ARTS | ARTS PLASTIQUES | ART |
| INFORMATIQUE | SALLE INFORMATIQUE | INF |
| CAFÉTÉRIA | CAFÉ, CANTINE | CAF |
| AUDITORIUM | SALLE POLYVALENTE | AUD |

### Locaux Administratifs
| Nom | Variantes | Code |
|-----|-----------|------|
| BUREAU | BUR. | BUR |
| SECRÉTARIAT | SECR. | SEC |
| DIRECTION | DIR. | DIR |
| SALLE DE RÉUNION | RÉUNION, CONF. | REU |
| SALLE DES PROFS | ENSEIGNANTS | ENS |
| ACCUEIL | RÉCEPTION | ACC |
| ARCHIVES | ARCH. | ARC |

### Locaux de Service
| Nom | Variantes | Code |
|-----|-----------|------|
| CORRIDOR | CORR., CIRC. | COR |
| VESTIBULE | VEST., ENTRÉE | VES |
| ESCALIER | ESC. | ESC |
| ASCENSEUR | ASC., ÉLÉV. | ASC |
| TOILETTE | T., W.C., S.B. | TOI |
| TOILETTE HOMMES | T.H., W.C.H. | TOI-H |
| TOILETTE FEMMES | T.F., W.C.F. | TOI-F |
| TOILETTE ACCESSIBLE | T.ACC., T.UNIV. | TOI-A |
| CONCIERGE | CONC., JANITEUR | CON |
| RANGEMENT | RANG., STORAGE | RAN |
| DÉPÔT | DÉP. | DEP |

### Locaux Techniques
| Nom | Variantes | Code |
|-----|-----------|------|
| SALLE MÉCANIQUE | MÉC., MÉCA. | MEC |
| CHAUFFERIE | CHAUF. | CHA |
| SALLE ÉLECTRIQUE | ÉLEC., S.ÉLEC. | ELE |
| TÉLÉCOM | TÉLÉC., TI | TEL |
| ENTRÉE ÉLECTRIQUE | E.ÉLEC. | EEL |
| VIDE SANITAIRE | V.S. | VS |
| ENTREPOSAGE | ENTR. | ENT |
| CHUTE À DÉCHETS | DÉCHETS | DEC |

### Locaux Spécialisés
| Nom | Variantes | Code |
|-----|-----------|------|
| CUISINE | CUIS. | CUI |
| BUANDERIE | BUAND. | BUA |
| VESTIAIRE | VEST. | VES |
| DOUCHE | DOUCH. | DOU |
| INFIRMERIE | INF. | INF |
| PSYCHOLOGUE | PSYCH. | PSY |

---

## Patterns de Numérotation

### Format Standard: BLOC + ÉTAGE + NUMÉRO

```
[BLOC][ÉTAGE][NUMÉRO]
```

**Exemples:**
- `101` → Bloc implicite, Étage 1, Local 01
- `A-201` → Bloc A, Étage 2, Local 01
- `B204` → Bloc B, Étage 2, Local 04
- `SS-05` → Sous-sol, Local 05

### Regex de Numérotation
```regex
^([A-Z])?[-]?([0-9S]{1,2})([0-9]{2})(?:[-]([0-9A-Z]+))?$
```

**Groupes:**
1. Bloc (optionnel): A, B, C...
2. Étage: 1, 2, 3, S (sous-sol), SS
3. Numéro séquentiel: 01-99
4. Suffixe (optionnel): -1, -A, -B

### Codes d'Étage

| Code | Signification |
|------|---------------|
| `0` ou `R` | Rez-de-chaussée |
| `1` | Premier étage (niveau rue) |
| `2` | Deuxième étage |
| `S` ou `SS` | Sous-sol |
| `M` | Mezzanine |
| `T` | Toit/Terrasse |
| `P` | Penthouse |

### Exemples de Numérotation

| Numéro | Décodage |
|--------|----------|
| `101` | Étage 1, Local 01 |
| `102` | Étage 1, Local 02 |
| `201` | Étage 2, Local 01 |
| `204-1` | Étage 2, Local 04, Sous-division 1 |
| `204-A` | Étage 2, Local 04, Section A |
| `A-101` | Bloc A, Étage 1, Local 01 |
| `B-205` | Bloc B, Étage 2, Local 05 |
| `S01` | Sous-sol, Local 01 |
| `SS-03` | Sous-sol, Local 03 |
| `M01` | Mezzanine, Local 01 |

---

## Patterns de Texte OCR

### Pattern Complet Nom + Numéro
```regex
^([A-ZÀÂÄÉÈÊËÎÏÔÙÛÜÇ\s\-\.]+)\s*[-–—]?\s*(\d{3}(?:[-][0-9A-Z]+)?)$
```

**Exemples détectés:**
- `CLASSE 101`
- `CORRIDOR - 102`
- `SALLE MÉCANIQUE 001`
- `TOILETTE H. 103-A`

### Pattern Superficie
```regex
(\d+(?:[,\.]\d+)?)\s*(?:pi²|p\.c\.|SF|PC)
```

**Exemples:**
- `750 pi²`
- `1,200 p.c.`
- `850.5 SF`

---

## Catégorisation par Usage

### Code du Bâtiment (CNB)
| Groupe | Usage | Exemples |
|--------|-------|----------|
| A-1 | Réunion | Théâtre, cinéma |
| A-2 | Réunion | Église, école, restaurant |
| B | Détention | Prison |
| C | Habitation | Résidence, dortoir |
| D | Affaires | Bureau, banque |
| E | Commerce | Magasin |
| F-1 | Industrie (risque moyen) | Atelier |
| F-2 | Industrie (risque faible) | Entrepôt |
| F-3 | Industrie (risque très faible) | Stockage |

---

## Notes d'Extraction

### Priorité de Détection
1. **Numéro de local** - Identifiant unique
2. **Nom du local** - Type de pièce
3. **Superficie** - En pi²
4. **Dimensions** - Largeur × Profondeur

### Nettoyage OCR Courant
- Supprimer les espaces multiples
- Normaliser les accents (É, È, Ê → E pour matching)
- Gérer les abréviations (CORR. → CORRIDOR)
- Ignorer les annotations temporaires (clouded items)
