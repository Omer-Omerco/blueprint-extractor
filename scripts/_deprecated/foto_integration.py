#!/usr/bin/env python3
"""
FOTO Integration — Lier les photos FOTO aux locaux du RAG

Ce module permet de:
1. Matcher une photo FOTO à un local de l'école
2. Récupérer toutes les photos associées à un local
3. Générer des rapports photos par local
4. (Bonus) Utiliser Vision AI pour identifier le local depuis une photo

Usage:
    from foto_integration import match_photo_to_room, get_photos_for_room
    
    result = match_photo_to_room(photo_metadata)
    photos = get_photos_for_room("A-204")
"""

import json
import re
import os
from pathlib import Path

try:
    import requests
    HAS_REQUESTS = True
except ImportError:
    HAS_REQUESTS = False
from typing import Optional, Dict, List, Any
from datetime import datetime

# Paths
SCRIPT_DIR = Path(__file__).parent
OUTPUT_DIR = SCRIPT_DIR.parent / "output"
ROOMS_FILE = OUTPUT_DIR / "rooms_complete.json"
FOTO_ACTIVITY_FILE = Path("/Users/omer/clawd/memory/foto-activity.md")
PHOTO_ROOM_LINKS_FILE = OUTPUT_DIR / "photo_room_links.json"

# FOTO API
FOTO_API_BASE = "https://foto-gestion.vercel.app/api/v1"
FOTO_API_KEY = os.getenv("FOTO_API_KEY") or "25c1df363faf0807bc1ec929ef47bddb2714724b4480efb7f0ef14b977323577"

# GPS coordinates de l'école Enfant-Jésus (Sorel-Tracy)
# À ajuster avec les vraies coordonnées du bâtiment
SCHOOL_GPS = {
    "lat": 46.0410,  # Sorel-Tracy approximatif
    "lon": -73.1173,
    "radius_m": 100  # Rayon pour considérer "sur site"
}


def load_rooms() -> Dict[str, Any]:
    """Charge la base de données des locaux."""
    if not ROOMS_FILE.exists():
        return {"rooms": [], "project": {}}
    
    with open(ROOMS_FILE, 'r', encoding='utf-8') as f:
        return json.load(f)


def load_photo_room_links() -> Dict[str, str]:
    """Charge les liens photo→local existants."""
    if not PHOTO_ROOM_LINKS_FILE.exists():
        return {}
    
    with open(PHOTO_ROOM_LINKS_FILE, 'r', encoding='utf-8') as f:
        return json.load(f)


def save_photo_room_links(links: Dict[str, str]):
    """Sauvegarde les liens photo→local."""
    with open(PHOTO_ROOM_LINKS_FILE, 'w', encoding='utf-8') as f:
        json.dump(links, f, indent=2, ensure_ascii=False)


def extract_room_id_from_text(text: str) -> Optional[str]:
    """
    Extrait un numéro de local depuis du texte.
    
    Patterns reconnus:
    - A-204, B-101, C-001
    - Local A204, local A-204
    - #A-204
    - Classe A-107
    """
    if not text:
        return None
    
    text = text.upper()
    
    # Pattern principal: Bloc-Numéro (A-204, B-101, etc.)
    patterns = [
        r'\b([A-C])-?(\d{3}(?:-\d+)?)\b',  # A-204, A204, A-102-1
        r'LOCAL\s*([A-C])-?(\d{3})\b',      # Local A204
        r'CLASSE\s*([A-C])-?(\d{3})\b',     # Classe A107
        r'#\s*([A-C])-?(\d{3})\b',          # #A-204
    ]
    
    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            block = match.group(1)
            number = match.group(2)
            # Normaliser: A-204 (avec tiret)
            if '-' in number:
                return f"{block}-{number}"
            return f"{block}-{number}"
    
    return None


def calculate_gps_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Calcule la distance en mètres entre deux points GPS (formule Haversine)."""
    from math import radians, sin, cos, sqrt, atan2
    
    R = 6371000  # Rayon de la Terre en mètres
    
    lat1, lon1, lat2, lon2 = map(radians, [lat1, lon1, lat2, lon2])
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    
    a = sin(dlat/2)**2 + cos(lat1) * cos(lat2) * sin(dlon/2)**2
    c = 2 * atan2(sqrt(a), sqrt(1-a))
    
    return R * c


def is_on_school_site(lat: float, lon: float) -> bool:
    """Vérifie si les coordonnées GPS sont sur le site de l'école."""
    distance = calculate_gps_distance(
        lat, lon,
        SCHOOL_GPS["lat"], SCHOOL_GPS["lon"]
    )
    return distance <= SCHOOL_GPS["radius_m"]


def match_photo_to_room(photo_metadata: dict) -> dict:
    """
    À partir des métadonnées d'une photo FOTO, trouve le local le plus probable.
    
    Args:
        photo_metadata: Dict avec:
            - photo_id: str (UUID de la photo)
            - notes: str (notes/description de la photo)
            - gps_lat: float (optional)
            - gps_lon: float (optional)
            - project_name: str (optional)
            - ai_description: str (optional)
    
    Returns:
        {
            "photo_id": str,
            "matched_room": "A-204" or None,
            "match_confidence": 0.0-1.0,
            "match_method": "notes" | "gps" | "manual" | "vision" | None,
            "match_details": str
        }
    """
    photo_id = photo_metadata.get("photo_id", "unknown")
    notes = photo_metadata.get("notes", "")
    ai_desc = photo_metadata.get("ai_description", "")
    gps_lat = photo_metadata.get("gps_lat")
    gps_lon = photo_metadata.get("gps_lon")
    
    result = {
        "photo_id": photo_id,
        "matched_room": None,
        "match_confidence": 0.0,
        "match_method": None,
        "match_details": ""
    }
    
    # 1. Chercher dans les notes (haute confiance)
    room_from_notes = extract_room_id_from_text(notes)
    if room_from_notes:
        # Vérifier que le local existe
        rooms_data = load_rooms()
        room_ids = [r["id"] for r in rooms_data.get("rooms", [])]
        
        if room_from_notes in room_ids:
            result["matched_room"] = room_from_notes
            result["match_confidence"] = 0.95
            result["match_method"] = "notes"
            result["match_details"] = f"Trouvé '{room_from_notes}' dans les notes"
            return result
        else:
            # Local mentionné mais pas dans la DB
            result["matched_room"] = room_from_notes
            result["match_confidence"] = 0.7
            result["match_method"] = "notes"
            result["match_details"] = f"'{room_from_notes}' mentionné mais non validé dans RAG"
            return result
    
    # 2. Chercher dans la description AI
    room_from_ai = extract_room_id_from_text(ai_desc)
    if room_from_ai:
        rooms_data = load_rooms()
        room_ids = [r["id"] for r in rooms_data.get("rooms", [])]
        
        result["matched_room"] = room_from_ai
        result["match_confidence"] = 0.8 if room_from_ai in room_ids else 0.6
        result["match_method"] = "vision"
        result["match_details"] = f"Extrait '{room_from_ai}' de la description AI"
        return result
    
    # 3. Vérifier si sur site (GPS)
    if gps_lat and gps_lon:
        on_site = is_on_school_site(gps_lat, gps_lon)
        if on_site:
            result["match_confidence"] = 0.3
            result["match_method"] = "gps"
            result["match_details"] = f"Sur site école ({gps_lat:.4f}, {gps_lon:.4f}) mais local non identifié"
        else:
            result["match_details"] = f"Hors site ({gps_lat:.4f}, {gps_lon:.4f})"
    
    # 4. Vérifier les liens manuels existants
    links = load_photo_room_links()
    if photo_id in links:
        result["matched_room"] = links[photo_id]
        result["match_confidence"] = 1.0
        result["match_method"] = "manual"
        result["match_details"] = "Lien manuel existant"
        return result
    
    return result


def link_photo_to_room(photo_id: str, room_id: str) -> bool:
    """
    Crée un lien manuel entre une photo et un local.
    
    Args:
        photo_id: UUID de la photo FOTO
        room_id: ID du local (ex: "A-204")
    
    Returns:
        True si succès
    """
    links = load_photo_room_links()
    links[photo_id] = room_id
    save_photo_room_links(links)
    return True


def get_photos_for_room(room_id: str) -> list:
    """
    Retourne toutes les photos FOTO associées à un local.
    
    Cherche dans:
    1. Les liens manuels (photo_room_links.json)
    2. L'activité FOTO (foto-activity.md)
    3. L'API FOTO si disponible
    
    Args:
        room_id: ID du local (ex: "A-204")
    
    Returns:
        Liste de dicts avec infos photo:
        [
            {
                "photo_id": "uuid",
                "drive_url": "https://...",
                "date": "2026-01-27",
                "notes": "...",
                "match_method": "manual"|"notes"|"vision"
            }
        ]
    """
    photos = []
    room_id_upper = room_id.upper()
    
    # 1. Liens manuels
    links = load_photo_room_links()
    for photo_id, linked_room in links.items():
        if linked_room.upper() == room_id_upper:
            photos.append({
                "photo_id": photo_id,
                "drive_url": None,  # À enrichir
                "date": None,
                "notes": None,
                "match_method": "manual"
            })
    
    # 2. Parser foto-activity.md
    if FOTO_ACTIVITY_FILE.exists():
        activity_photos = parse_foto_activity_for_room(room_id_upper)
        photos.extend(activity_photos)
    
    # 3. Dédupliquer par photo_id
    seen = set()
    unique_photos = []
    for p in photos:
        if p["photo_id"] not in seen:
            seen.add(p["photo_id"])
            unique_photos.append(p)
    
    return unique_photos


def parse_foto_activity_for_room(room_id: str) -> list:
    """Parse le fichier foto-activity.md pour trouver les photos d'un local."""
    photos = []
    
    if not FOTO_ACTIVITY_FILE.exists():
        return photos
    
    content = FOTO_ACTIVITY_FILE.read_text(encoding='utf-8')
    
    # Parser les entrées (format markdown)
    entries = re.split(r'###\s+\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}', content)
    dates = re.findall(r'###\s+(\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2})', content)
    
    for i, entry in enumerate(entries[1:], 0):  # Skip header
        if i >= len(dates):
            continue
            
        date_str = dates[i]
        
        # Extraire photo_id
        photo_id_match = re.search(r'\*\*Photo ID:\*\*\s*([a-f0-9-]+)', entry)
        photo_id = photo_id_match.group(1) if photo_id_match else None
        
        # Extraire drive URL
        drive_match = re.search(r'\[Voir photo\]\((https://[^)]+)\)', entry)
        drive_url = drive_match.group(1) if drive_match else None
        
        # Extraire notes
        notes_match = re.search(r'\*\*Notes:\*\*\s*"?([^"*\n]+)"?', entry)
        notes = notes_match.group(1).strip() if notes_match else None
        
        # Vérifier si le local est mentionné
        room_found = extract_room_id_from_text(entry)
        
        if room_found and room_found.upper() == room_id.upper():
            photos.append({
                "photo_id": photo_id or f"activity_{i}",
                "drive_url": drive_url,
                "date": date_str.split()[0] if date_str else None,
                "notes": notes,
                "match_method": "notes"
            })
    
    return photos


def get_room_info(room_id: str) -> Optional[Dict]:
    """Récupère les infos d'un local depuis le RAG."""
    rooms_data = load_rooms()
    
    for room in rooms_data.get("rooms", []):
        if room["id"].upper() == room_id.upper():
            return room
    
    return None


def generate_room_photo_report(room_id: str) -> str:
    """
    Génère un rapport complet avec:
    - Infos du local (du RAG)
    - Photos FOTO associées
    
    Args:
        room_id: ID du local (ex: "A-204")
    
    Returns:
        Rapport en markdown
    """
    room_info = get_room_info(room_id)
    photos = get_photos_for_room(room_id)
    
    report = f"# 📍 Rapport Local {room_id}\n\n"
    
    # Section infos local
    if room_info:
        report += "## 📋 Informations\n\n"
        report += f"- **ID:** {room_info['id']}\n"
        report += f"- **Nom:** {room_info['name']}\n"
        report += f"- **Bloc:** {room_info['block']}\n"
        report += f"- **Étage:** {room_info['floor']}\n"
        report += f"- **Confiance RAG:** {room_info.get('confidence', 'N/A')}\n"
        if room_info.get('validated_by'):
            report += f"- **Validé par:** {room_info['validated_by']}\n"
        report += "\n"
    else:
        report += f"⚠️ Local {room_id} non trouvé dans le RAG\n\n"
    
    # Section photos
    report += "## 📸 Photos FOTO\n\n"
    
    if photos:
        report += f"**{len(photos)} photo(s) trouvée(s)**\n\n"
        for i, photo in enumerate(photos, 1):
            report += f"### Photo {i}\n"
            report += f"- **ID:** `{photo['photo_id']}`\n"
            if photo.get('date'):
                report += f"- **Date:** {photo['date']}\n"
            if photo.get('drive_url'):
                report += f"- **Lien:** [Voir photo]({photo['drive_url']})\n"
            if photo.get('notes'):
                report += f"- **Notes:** {photo['notes']}\n"
            report += f"- **Matching:** {photo['match_method']}\n\n"
    else:
        report += "❌ Aucune photo associée à ce local.\n\n"
        report += "*Pour associer une photo:*\n"
        report += "```python\n"
        report += f'link_photo_to_room("photo-uuid", "{room_id}")\n'
        report += "```\n"
    
    # Timestamp
    report += f"\n---\n*Généré le {datetime.now().strftime('%Y-%m-%d %H:%M')}*\n"
    
    return report


def fetch_foto_photos(project_id: Optional[str] = None, limit: int = 100) -> list:
    """
    Récupère les photos depuis l'API FOTO.
    
    Args:
        project_id: Filtrer par projet (optional)
        limit: Nombre max de résultats
    
    Returns:
        Liste de documents (photos) avec métadonnées
    """
    if not HAS_REQUESTS:
        print("⚠️ Module 'requests' non disponible. Installer avec: pip install requests")
        return []
    
    headers = {"Authorization": f"Bearer {FOTO_API_KEY}"}
    
    url = f"{FOTO_API_BASE}/data?table=documents&limit={limit}"
    if project_id:
        url += f"&project_id={project_id}"
    
    try:
        response = requests.get(url, headers=headers, timeout=30)
        response.raise_for_status()
        data = response.json()
        return data.get("data", [])
    except Exception as e:
        print(f"Erreur API FOTO: {e}")
        return []


def analyze_photo_with_vision(photo_url: str, room_list: List[str]) -> Optional[str]:
    """
    [BONUS] Utilise Vision AI pour identifier le local depuis une photo.
    
    Compare les éléments visibles dans la photo avec les caractéristiques
    connues des locaux (à implémenter avec GPT-4V ou Claude Vision).
    
    Args:
        photo_url: URL de la photo (Google Drive ou autre)
        room_list: Liste des IDs de locaux possibles
    
    Returns:
        ID du local identifié ou None
    """
    # TODO: Implémenter avec l'API Vision de votre choix
    # Prompt suggéré:
    # "Cette photo a été prise dans un des locaux suivants d'une école:
    #  {room_list}. Analyse les éléments visibles (numéro de porte, 
    #  affichage, configuration de la pièce) et identifie le local.
    #  Réponds uniquement avec l'ID du local (ex: A-204) ou 'inconnu'."
    
    return None  # Placeholder


# === CLI ===

if __name__ == "__main__":
    import sys
    
    if len(sys.argv) < 2:
        print("Usage:")
        print("  python foto_integration.py match <notes> [lat] [lon]")
        print("  python foto_integration.py photos <room_id>")
        print("  python foto_integration.py report <room_id>")
        print("  python foto_integration.py link <photo_id> <room_id>")
        print("  python foto_integration.py list-rooms")
        sys.exit(1)
    
    command = sys.argv[1]
    
    if command == "match":
        notes = sys.argv[2] if len(sys.argv) > 2 else ""
        lat = float(sys.argv[3]) if len(sys.argv) > 3 else None
        lon = float(sys.argv[4]) if len(sys.argv) > 4 else None
        
        result = match_photo_to_room({
            "photo_id": "cli-test",
            "notes": notes,
            "gps_lat": lat,
            "gps_lon": lon
        })
        print(json.dumps(result, indent=2, ensure_ascii=False))
    
    elif command == "photos":
        room_id = sys.argv[2]
        photos = get_photos_for_room(room_id)
        print(json.dumps(photos, indent=2, ensure_ascii=False))
    
    elif command == "report":
        room_id = sys.argv[2]
        report = generate_room_photo_report(room_id)
        print(report)
    
    elif command == "link":
        photo_id = sys.argv[2]
        room_id = sys.argv[3]
        link_photo_to_room(photo_id, room_id)
        print(f"✅ Photo {photo_id} liée au local {room_id}")
    
    elif command == "list-rooms":
        rooms_data = load_rooms()
        for room in rooms_data.get("rooms", [])[:20]:
            print(f"  {room['id']}: {room['name']} (Bloc {room['block']}, Étage {room['floor']})")
        total = len(rooms_data.get("rooms", []))
        if total > 20:
            print(f"  ... et {total - 20} autres")
    
    else:
        print(f"Commande inconnue: {command}")
        sys.exit(1)
