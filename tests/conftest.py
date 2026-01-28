"""
Pytest fixtures for blueprint-extractor tests.
Provides realistic Quebec construction data.
"""

import json
import pytest
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch


# =============================================================================
# Path fixtures
# =============================================================================

@pytest.fixture
def fixtures_dir():
    """Path to fixtures directory."""
    return Path(__file__).parent / "fixtures"


@pytest.fixture
def sample_manifest(fixtures_dir):
    """Load sample manifest."""
    with open(fixtures_dir / "sample_manifest.json") as f:
        return json.load(f)


@pytest.fixture
def sample_guide(fixtures_dir):
    """Load sample guide."""
    with open(fixtures_dir / "sample_guide.json") as f:
        return json.load(f)


@pytest.fixture
def temp_dir():
    """Create a temporary directory."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def temp_pages_dir(temp_dir, sample_manifest):
    """Create a temp directory with manifest and fake page images."""
    pages_dir = temp_dir / "pages"
    pages_dir.mkdir()
    
    # Write manifest
    with open(pages_dir / "manifest.json", "w") as f:
        json.dump(sample_manifest, f)
    
    # Create fake PNG files (1x1 pixel transparent PNG)
    # Minimal valid PNG header
    png_header = bytes([
        0x89, 0x50, 0x4E, 0x47, 0x0D, 0x0A, 0x1A, 0x0A,  # PNG signature
        0x00, 0x00, 0x00, 0x0D, 0x49, 0x48, 0x44, 0x52,  # IHDR chunk
        0x00, 0x00, 0x00, 0x01, 0x00, 0x00, 0x00, 0x01,  # 1x1 pixels
        0x08, 0x06, 0x00, 0x00, 0x00, 0x1F, 0x15, 0xC4,  # RGBA, etc
        0x89, 0x00, 0x00, 0x00, 0x0A, 0x49, 0x44, 0x41,  # IDAT chunk
        0x54, 0x78, 0x9C, 0x63, 0x00, 0x01, 0x00, 0x00,  # Compressed data
        0x05, 0x00, 0x01, 0x0D, 0x0A, 0x2D, 0xB4, 0x00,  
        0x00, 0x00, 0x00, 0x49, 0x45, 0x4E, 0x44, 0xAE,  # IEND chunk
        0x42, 0x60, 0x82
    ])
    
    for i in range(1, 13):
        page_file = pages_dir / f"page-{i:03d}.png"
        page_file.write_bytes(png_header)
    
    # Update manifest paths to use temp dir
    manifest = sample_manifest.copy()
    for page in manifest["pages"]:
        page["path"] = str(pages_dir / page["filename"])
    
    with open(pages_dir / "manifest.json", "w") as f:
        json.dump(manifest, f)
    
    yield pages_dir


@pytest.fixture
def temp_output_dir(temp_dir):
    """Create a temp output directory."""
    output_dir = temp_dir / "output"
    output_dir.mkdir()
    return output_dir


@pytest.fixture
def sample_pdf(temp_dir):
    """Create a simple test PDF file."""
    try:
        import fitz
    except ImportError:
        pytest.skip("PyMuPDF not installed")
    
    pdf_path = temp_dir / "sample.pdf"
    
    # Create a simple PDF with one page
    doc = fitz.open()
    page = doc.new_page(width=612, height=792)  # Letter size
    
    # Add some content
    text_point = fitz.Point(100, 100)
    page.insert_text(text_point, "Test Blueprint Page", fontsize=12)
    
    # Add a rectangle to simulate a room
    rect = fitz.Rect(50, 50, 200, 200)
    page.draw_rect(rect, color=(0, 0, 0), width=1)
    
    # Save
    doc.save(str(pdf_path))
    doc.close()
    
    return pdf_path


# =============================================================================
# Quebec construction data fixtures
# =============================================================================

@pytest.fixture
def quebec_rooms():
    """Sample Quebec-style rooms with pieds-pouces dimensions."""
    return [
        {
            "id": "room-101",
            "name": "CLASSE",
            "number": "101",
            "dimensions": {
                "width": "25'-6\"",
                "depth": "30'-0\"",
                "area_sqft": 765
            },
            "confidence": 0.95,
            "page": 2
        },
        {
            "id": "room-102",
            "name": "CLASSE",
            "number": "102",
            "dimensions": {
                "width": "25'-6\"",
                "depth": "28'-6\"",
                "area_sqft": 727
            },
            "confidence": 0.92,
            "page": 2
        },
        {
            "id": "room-103",
            "name": "CORRIDOR",
            "number": "103",
            "dimensions": {
                "width": "8'-0\"",
                "depth": "120'-0\"",
                "area_sqft": 960
            },
            "confidence": 0.88,
            "page": 3
        },
        {
            "id": "room-104",
            "name": "S.D.B.",
            "number": "104",
            "dimensions": {
                "width": "12'-0\"",
                "depth": "15'-6\"",
                "area_sqft": 186
            },
            "confidence": 0.90,
            "page": 3
        },
        {
            "id": "room-105",
            "name": "RANGEMENT",
            "number": "105",
            "dimensions": {
                "width": "8'-6 1/2\"",
                "depth": "10'-3\"",
                "area_sqft": 87
            },
            "confidence": 0.85,
            "page": 4
        }
    ]


@pytest.fixture
def quebec_doors():
    """Sample doors from Quebec plans."""
    return [
        {"id": "door-P01", "number": "P01", "swing_angle": 90, "confidence": 0.95, "page": 2},
        {"id": "door-P02", "number": "P02", "swing_angle": 90, "confidence": 0.93, "page": 2},
        {"id": "door-P03", "number": "P03", "swing_angle": 180, "confidence": 0.88, "page": 3},
        {"id": "door-P04", "number": "P04", "swing_angle": 90, "confidence": 0.91, "page": 4}
    ]


@pytest.fixture
def quebec_dimensions():
    """Sample dimensions in Quebec pieds-pouces format."""
    return [
        {"id": "dim-001", "value_text": "25'-6\"", "value_inches": 306, "context": "largeur classe 101", "confidence": 0.95, "page": 2},
        {"id": "dim-002", "value_text": "30'-0\"", "value_inches": 360, "context": "profondeur classe 101", "confidence": 0.94, "page": 2},
        {"id": "dim-003", "value_text": "12'-0\"", "value_inches": 144, "context": "largeur S.D.B.", "confidence": 0.92, "page": 3},
        {"id": "dim-004", "value_text": "8'-6 1/2\"", "value_inches": 102.5, "context": "largeur rangement", "confidence": 0.88, "page": 4},
        {"id": "dim-005", "value_text": "8'-0\"", "value_inches": 96, "context": "hauteur plafond standard", "confidence": 0.96, "page": 1}
    ]


@pytest.fixture
def quebec_legend():
    """Sample legend symbols from Quebec plans."""
    return [
        {"symbol": "▢", "meaning": "Prise électrique 120V", "category": "électrique", "page": 1},
        {"symbol": "△", "meaning": "Sortie de secours", "category": "sécurité", "page": 1},
        {"symbol": "○", "meaning": "Luminaire encastré", "category": "électrique", "page": 1},
        {"symbol": "⬡", "meaning": "Détecteur de fumée", "category": "sécurité", "page": 1}
    ]


# =============================================================================
# Mock fixtures for API calls
# =============================================================================

@pytest.fixture
def mock_anthropic_client():
    """Mock Anthropic client for testing without API calls."""
    mock_client = MagicMock()
    
    # Default response for agent calls
    mock_response = MagicMock()
    mock_response.content = [MagicMock(text=json.dumps({
        "observations": [],
        "candidate_rules": [],
        "legend_extractions": [],
        "provisional_guide": "# Guide Test"
    }))]
    
    mock_client.messages.create.return_value = mock_response
    
    return mock_client


@pytest.fixture
def mock_subprocess_pdfinfo():
    """Mock subprocess for pdfinfo command."""
    with patch('subprocess.run') as mock_run:
        mock_result = MagicMock()
        mock_result.stdout = "Pages:          12\nFile size:      1234567 bytes\n"
        mock_result.returncode = 0
        mock_run.return_value = mock_result
        yield mock_run


# =============================================================================
# RAG fixtures
# =============================================================================

@pytest.fixture
def sample_rag_index(quebec_rooms, quebec_doors, quebec_dimensions, quebec_legend):
    """Build a sample RAG index for testing queries."""
    entries = []
    
    for room in quebec_rooms:
        entries.append({
            "type": "room",
            "id": room["id"],
            "name": room["name"],
            "number": room["number"],
            "page": room["page"],
            "dimensions": room["dimensions"],
            "confidence": room["confidence"],
            "search_text": f"{room['name'].lower()} {room['number']} local pièce salle {room['dimensions'].get('area_sqft', '')} pi²"
        })
    
    for door in quebec_doors:
        entries.append({
            "type": "door",
            "id": door["id"],
            "number": door["number"],
            "page": door["page"],
            "swing_angle": door["swing_angle"],
            "confidence": door["confidence"],
            "search_text": f"porte {door['number']} door"
        })
    
    for dim in quebec_dimensions:
        entries.append({
            "type": "dimension",
            "id": dim["id"],
            "value_text": dim["value_text"],
            "value_inches": dim["value_inches"],
            "context": dim["context"],
            "page": dim["page"],
            "confidence": dim["confidence"],
            "search_text": f"dimension cote {dim['value_text']} {dim['context']}"
        })
    
    for sym in quebec_legend:
        entries.append({
            "type": "symbol",
            "symbol": sym["symbol"],
            "meaning": sym["meaning"],
            "category": sym.get("category", ""),
            "page": sym.get("page"),
            "search_text": f"symbole légende {sym['symbol']} {sym['meaning']}"
        })
    
    return {
        "version": "1.0",
        "project": "/projects/ecole-quebec/plans.pdf",
        "stats": {
            "rooms": len(quebec_rooms),
            "doors": len(quebec_doors),
            "dimensions": len(quebec_dimensions),
            "symbols": len(quebec_legend),
            "total_entries": len(entries)
        },
        "entries": entries
    }


@pytest.fixture
def temp_rag_dir(temp_dir, sample_rag_index):
    """Create a temp RAG directory with index."""
    rag_dir = temp_dir / "rag"
    rag_dir.mkdir()
    
    with open(rag_dir / "index.json", "w") as f:
        json.dump(sample_rag_index, f, ensure_ascii=False)
    
    return rag_dir
