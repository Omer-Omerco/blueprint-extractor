# Blueprint-Extractor Test Coverage Report

**Date:** 2025-07-13  
**Total tests:** 735 passed, 2 skipped, 0 failures  
**Previous:** 519 tests → **+216 new tests added**

## Test Files Summary

| Test File | Tests | Script Covered |
|-----------|-------|---------------|
| `test_room_detector.py` | 40 | `room_detector.py` |
| `test_dimension_detector.py` | 33 | `dimension_detector.py` |
| `test_door_detector.py` | 41 | `door_detector.py` |
| `test_page_classifier.py` | 22 | `page_classifier.py` |
| `test_page_selector.py` | 16 | `page_selector.py` |
| `test_crop_extractor.py` | 15 | `crop_extractor.py` |
| `test_query_rag.py` | 37 | `query_rag.py` |
| `test_build_rag.py` | 21 | `build_rag.py` |
| `test_extract_objects.py` | 13 | `extract_objects.py` |
| `test_extract_pages.py` | 9 | `extract_pages.py` |
| `test_extract_pdf_vectors.py` | 23 | `extract_pdf_vectors.py` |
| `test_extract_products.py` | 26 | `extract_products.py` |
| `test_alerts.py` | 11 | `alerts.py` |
| `test_analyze_project.py` | 17 | `analyze_project.py` |
| `test_confidence.py` | 18 | `confidence.py` |
| `test_pipeline.py` | 27 | `agents/` (4-agent pipeline) |
| `test_run_pipeline.py` | 8 | `run_pipeline.py` |
| `test_render.py` | 13 | rendering utilities |
| `test_integration.py` | 14 | E2E integration |
| `test_validation.py` | 32 | `cross_validate.py` + `validate_gt.py` (original) |
| **`test_cross_validate.py`** ✨ | **~45** | `cross_validate.py` (comprehensive) |
| **`test_validate_gt.py`** ✨ | **~50** | `validate_gt.py` (comprehensive) |
| **`test_pipeline_orchestrator.py`** ✨ | **~25** | `pipeline_orchestrator.py` |
| **`test_extract_bbox.py`** ✨ | **~20** | `extract_bbox.py` |
| **`test_extract_sections.py`** ✨ | **~25** | `extract_sections.py` |
| **`test_fix_bboxes.py`** ✨ | **~15** | `fix_bboxes.py` |
| **`test_render_room.py`** ✨ | **~15** | `render_room.py` |

✨ = New test file added in this audit

## Scripts Coverage

### Fully Tested ✅

| Script | Test Coverage | Notes |
|--------|-------------|-------|
| `room_detector.py` | ✅ Comprehensive | Edge cases, real data, fuzzy matching |
| `dimension_detector.py` | ✅ Comprehensive | Pieds-pouces formats, fractions, edge cases |
| `door_detector.py` | ✅ Comprehensive | Arc detection, labels, swing angles |
| `page_classifier.py` | ✅ Good | All page types classified |
| `page_selector.py` | ✅ Good | Optimal selection logic |
| `crop_extractor.py` | ✅ Good | Crop generation |
| `query_rag.py` | ✅ Comprehensive | Fuzzy search, multilingual |
| `build_rag.py` | ✅ Good | Index building |
| `extract_objects.py` | ✅ Good | Object detection |
| `extract_pages.py` | ✅ Good | PDF page extraction |
| `extract_pdf_vectors.py` | ✅ Good | Vector extraction |
| `extract_products.py` | ✅ Good | Product extraction |
| `alerts.py` | ✅ Good | Alert system |
| `analyze_project.py` | ✅ Good | Project analysis |
| `confidence.py` | ✅ Good | Confidence scoring |
| `cross_validate.py` | ✅ Comprehensive | ✨ All functions, edge cases, data classes |
| `validate_gt.py` | ✅ Comprehensive | ✨ All functions, metrics, fuzzy matching |
| `pipeline_orchestrator.py` | ✅ Good | ✨ All 4 stages, success/failure/error paths, save |
| `extract_bbox.py` | ✅ Good | ✨ Load, patterns, fallback, update |
| `extract_sections.py` | ✅ Good | ✨ Font analysis, sections, CSI codes, room refs |
| `fix_bboxes.py` | ✅ Good | ✨ Span extraction, room finding, multi-part IDs |
| `render_room.py` | ✅ Good | ✨ Highlight, crop, card, floor rendering |
| `run_pipeline.py` | ✅ Basic | CLI integration |
| `agents/` (4 agents) | ✅ Good | Guide builder, applier, validator, consolidator |

### Not Tested (By Design) ⚠️

| Script | Reason |
|--------|--------|
| `verify_gt_vision.py` | Requires live Anthropic API + real PDF images. Integration-only script. |

## Skipped Tests

- `test_validation.py::TestWithRealData::test_real_cross_validation` — Devis data not available in test env
- One other skip related to missing real data files

## Test Quality Assessment

### Independence from Ground Truth
- ✅ Tests use **synthetic fixtures** (not GT data) for unit tests
- ✅ GT-dependent tests are clearly separated in `TestWithRealData` classes
- ✅ No circular validation: tests validate logic, not just GT matching

### Edge Cases Covered
- Empty inputs (empty rooms, empty devis, empty blocks)
- Case insensitivity (room names, IDs)
- Quebec-specific formats (pieds-pouces, French names)
- Fuzzy matching (synonyms: WC/TOILETTES, RANGEMENT/REMISE)
- Fallback behaviors (no OCR, no bbox, no PIL)
- Error handling (unknown rooms, missing pages, API failures)

### What Could Be Added (Future)
1. **Property-based tests** for dimension parsing (hypothesis library)
2. **Snapshot tests** for rendered images
3. **Performance benchmarks** for large PDFs
4. **verify_gt_vision.py** — mock-based tests for the Vision API flow
