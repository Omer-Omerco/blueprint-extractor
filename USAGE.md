# Comment j'utilise ce skill pour le projet École Enfant-Jésus

## Contexte

**Mario** (surintendant Omerco) pose des questions sur le projet.  
**Moi** (Omer/Clawdbot) je réponds en utilisant le RAG.

## Types de questions Mario

### 1. Questions sur les locaux
```
"C'est quoi le local 204?"
→ RAG: rooms_extracted.json
→ Réponse: "Local 204 = CLASSE, Bloc A, 2ème étage"
```

### 2. Questions sur les finitions
```
"Quelle peinture pour les classes?"
→ RAG: chunks.json (section 09 91 00)
→ Réponse: "Peinture latex acrylique, 2 couches, fini coquille d'œuf"
```

### 3. Questions sur les matériaux
```
"C'est quoi comme plancher dans le gymnase?"
→ RAG: local_index.json (gymnase → sections)
→ Chercher: section revêtement de sol
→ Réponse: "Plancher de bois franc érable, système flottant"
```

### 4. Questions sur les spécifications
```
"Les portes doivent être comment?"
→ RAG: chunks.json (section 08 XX XX)
→ Réponse: "Portes en bois, cadres métalliques, quincaillerie grade 1"
```

### 5. Questions sur les produits
```
"On peut utiliser quel ciment-colle?"
→ RAG: products (section carrelage)
→ Réponse: "Mapei Kerabond T ou équivalent approuvé"
```

## Workflow de réponse

```
Question Mario
    │
    ▼
┌─────────────────┐
│ 1. Identifier   │ Local? Matériau? Produit?
│    le type      │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ 2. Chercher     │ RAG query (chunks + local_index)
│    dans RAG     │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ 3. Croiser      │ Plans + Devis
│    les sources  │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ 4. Répondre     │ Avec sources citées
│    clairement   │
└─────────────────┘
```

## Règles de réponse

1. **JAMAIS inventer** — Si pas dans le RAG, dire "Je n'ai pas trouvé cette info"
2. **Citer les sources** — "Selon le devis section 09 91 00..."
3. **Unités québécoises** — Pieds-pouces, pi², etc.
4. **Vocabulaire chantier** — Parler comme un professionnel

## Exemple complet

**Mario:** "C'est quoi les specs pour la peinture du corridor 105?"

**Moi:**
```
Pour le corridor 105 (Bloc A, 1er étage):

Selon le devis section 09 91 00 - Peinturage:
- Murs: Peinture latex acrylique, fini coquille d'œuf
- Plafond: Peinture latex, fini mat
- Préparation: 1 couche d'apprêt + 2 couches de finition

Produits acceptés:
- Sherwin-Williams ProMar 200
- Benjamin Moore Ultra Spec 500
- Ou équivalent approuvé

Source: Devis architecture, pages 45-48
```

## Fichiers RAG utilisés

```
output/rag/
├── unified_index.json   # Index principal
├── chunks.json          # Chunks texte pour recherche
├── local_index.json     # Local → sections
└── products.json        # Produits par section
```
