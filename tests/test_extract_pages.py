"""
Tests for extract_pages.py
PDF to PNG extraction functionality.
"""

import json
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock

import sys
sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

from extract_pages import get_page_count, extract_single_page, extract_pages


class TestGetPageCount:
    """Tests for get_page_count function."""
    
    def test_parse_pdfinfo_output(self, mock_subprocess_pdfinfo):
        """Should parse page count from pdfinfo output."""
        count = get_page_count(Path("/fake/test.pdf"))
        assert count == 12
    
    def test_returns_zero_on_missing_pages_line(self):
        """Should return 0 if Pages: line is not found."""
        with patch('subprocess.run') as mock_run:
            mock_result = MagicMock()
            mock_result.stdout = "File size: 1234567 bytes\n"
            mock_result.returncode = 0
            mock_run.return_value = mock_result
            
            count = get_page_count(Path("/fake/test.pdf"))
            assert count == 0
    
    def test_handles_multiline_pdfinfo(self):
        """Should handle full pdfinfo output."""
        with patch('subprocess.run') as mock_run:
            mock_result = MagicMock()
            mock_result.stdout = """Title:          Plans Architecturaux
Author:         Firme ABC
Creator:        AutoCAD
Producer:       Adobe PDF Library
CreationDate:   Mon Jan 15 10:30:00 2024
ModDate:        Mon Jan 15 10:30:00 2024
Pages:          24
Encrypted:      no
Page size:      612 x 792 pts (letter)
File size:      5678901 bytes
"""
            mock_result.returncode = 0
            mock_run.return_value = mock_result
            
            count = get_page_count(Path("/fake/plans.pdf"))
            assert count == 24


class TestExtractSinglePage:
    """Tests for extract_single_page function."""
    
    def test_calls_pdftoppm_with_correct_args(self, temp_dir):
        """Should call pdftoppm with correct parameters."""
        with patch('subprocess.run') as mock_run:
            mock_run.return_value = MagicMock(returncode=0)
            
            pdf_path = Path("/fake/test.pdf")
            output_dir = temp_dir
            
            extract_single_page(pdf_path, output_dir, page_num=5, dpi=300)
            
            mock_run.assert_called_once()
            args = mock_run.call_args[0][0]
            
            assert "pdftoppm" in args
            assert "-png" in args
            assert "-r" in args
            assert "300" in args
            assert "-f" in args
            assert "5" in args
            assert "-l" in args
    
    def test_renames_output_file(self, temp_dir):
        """Should rename pdftoppm output to expected format."""
        with patch('subprocess.run') as mock_run:
            mock_run.return_value = MagicMock(returncode=0)
            
            # Create file that pdftoppm would create
            expected_pdftoppm_output = temp_dir / "page-003-3.png"
            expected_pdftoppm_output.touch()
            
            result = extract_single_page(
                Path("/fake/test.pdf"),
                temp_dir,
                page_num=3,
                dpi=300
            )
            
            assert result is not None
            assert result.name == "page-003.png"
    
    def test_returns_none_on_failure(self, temp_dir):
        """Should return None if pdftoppm fails."""
        with patch('subprocess.run') as mock_run:
            mock_run.return_value = MagicMock(returncode=1)
            
            result = extract_single_page(
                Path("/fake/test.pdf"),
                temp_dir,
                page_num=1,
                dpi=300
            )
            
            assert result is None


class TestExtractPages:
    """Tests for main extract_pages function."""
    
    def test_creates_manifest(self, temp_dir):
        """Should create manifest.json with extraction results."""
        with patch('subprocess.run') as mock_run:
            # Mock pdfinfo
            pdfinfo_result = MagicMock()
            pdfinfo_result.stdout = "Pages:          3\n"
            pdfinfo_result.returncode = 0
            
            # Mock pdftoppm
            pdftoppm_result = MagicMock()
            pdftoppm_result.returncode = 0
            
            def run_side_effect(args, **kwargs):
                if "pdfinfo" in args:
                    return pdfinfo_result
                # Create fake output file
                for i in range(1, 4):
                    page_file = temp_dir / "output" / f"page-{i:03d}-{i}.png"
                    page_file.parent.mkdir(exist_ok=True)
                    page_file.touch()
                return pdftoppm_result
            
            mock_run.side_effect = run_side_effect
            
            # Create fake PDF
            pdf_path = temp_dir / "test.pdf"
            pdf_path.touch()
            
            output_dir = temp_dir / "output"
            
            manifest = extract_pages(str(pdf_path), str(output_dir), dpi=300)
            
            assert manifest["page_count"] == 3
            assert manifest["dpi"] == 300
            assert len(manifest["pages"]) == 3
            
            # Check manifest file was created
            manifest_path = output_dir / "manifest.json"
            assert manifest_path.exists()
    
    def test_tracks_failed_pages(self, temp_dir):
        """Should track pages that failed to extract."""
        with patch('subprocess.run') as mock_run:
            # Mock pdfinfo
            pdfinfo_result = MagicMock()
            pdfinfo_result.stdout = "Pages:          3\n"
            pdfinfo_result.returncode = 0
            
            call_count = [0]
            
            def run_side_effect(args, **kwargs):
                if "pdfinfo" in args:
                    return pdfinfo_result
                
                call_count[0] += 1
                result = MagicMock()
                
                # Fail on page 2
                if call_count[0] == 2:
                    result.returncode = 1
                else:
                    result.returncode = 0
                    # Create output for successful pages
                    page_num = 1 if call_count[0] == 1 else 3
                    page_file = temp_dir / "output" / f"page-{page_num:03d}-{page_num}.png"
                    page_file.parent.mkdir(exist_ok=True)
                    page_file.touch()
                
                return result
            
            mock_run.side_effect = run_side_effect
            
            pdf_path = temp_dir / "test.pdf"
            pdf_path.touch()
            
            manifest = extract_pages(str(pdf_path), str(temp_dir / "output"), dpi=300)
            
            assert 2 in manifest["failed_pages"]
            assert manifest["page_count"] == 2  # Only 2 successful


class TestDPIOptions:
    """Tests for DPI configuration."""
    
    @pytest.mark.parametrize("dpi", [150, 200, 300, 600])
    def test_supports_various_dpi(self, temp_dir, dpi):
        """Should support various DPI values."""
        with patch('subprocess.run') as mock_run:
            pdfinfo_result = MagicMock()
            pdfinfo_result.stdout = "Pages:          1\n"
            pdfinfo_result.returncode = 0
            
            pdftoppm_result = MagicMock()
            pdftoppm_result.returncode = 0
            
            def run_side_effect(args, **kwargs):
                if "pdfinfo" in args:
                    return pdfinfo_result
                
                # Verify DPI is passed correctly
                assert str(dpi) in args
                
                page_file = temp_dir / "output" / "page-001-1.png"
                page_file.parent.mkdir(exist_ok=True)
                page_file.touch()
                return pdftoppm_result
            
            mock_run.side_effect = run_side_effect
            
            pdf_path = temp_dir / "test.pdf"
            pdf_path.touch()
            
            manifest = extract_pages(str(pdf_path), str(temp_dir / "output"), dpi=dpi)
            assert manifest["dpi"] == dpi
