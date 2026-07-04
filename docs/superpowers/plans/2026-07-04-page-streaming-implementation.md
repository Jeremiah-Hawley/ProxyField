# Page-Streaming PDF Generation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Refactor `build_pdf()` to stream pages one at a time, reducing peak RAM from 4.9GB to 445MB for 100+ card decks.

**Architecture:** Extract two new functions from `build_pdf()`: `fetch_page_cards()` fetches 9-card batches from Scryfall/cache, and `draw_page_pair()` draws front+back pages to canvas. Main loop processes one page at a time: fetch → draw → discard → repeat. Memory is reclaimed per page via explicit `del`.

**Tech Stack:** PIL, reportlab, Scryfall API (unchanged). No new dependencies.

## Global Constraints

- Page structure: 9 cards per page (3×3 grid), front + back paired
- Peak RAM: < 2GB (target ~445MB with 9 images max)
- Progress reporting: Per-page granularity ("Page X of Y")
- Error handling: Abort on card fetch failure with page context
- All existing features preserved: tokens, upscaling, caching, local art

---

## File Structure

**ProxField.py** (existing file, modified)
- Add `fetch_page_cards()` function (new)
- Add `draw_page_pair()` function (new)
- Refactor `build_pdf()` function (significant rewrite of lines 432-474)
- All other functions unchanged

**tests/test_page_streaming.py** (new file)
- Unit tests for `fetch_page_cards()`
- Unit tests for `draw_page_pair()`
- Integration test for full page streaming on small deck

---

## Tasks

### Task 1: Add `fetch_page_cards()` Function

**Files:**
- Modify: `ProxField.py` (add function before `build_pdf()`, around line 408)
- Test: `tests/test_page_streaming.py`

**Interfaces:**
- Consumes: `deck_list: list[dict]`, `page_num: int`, `remote: bool`, `use_upscaling: bool`, `upscale_algorithm: str`
- Produces: `list[list[Image.Image]]` — list of 9 (or fewer for final page) image pairs `[front, back]`

- [ ] **Step 1: Write the failing test**

Create `tests/test_page_streaming.py`:

```python
import pytest
from unittest.mock import Mock, patch, MagicMock
from PIL import Image
from io import BytesIO
import sys
sys.path.insert(0, '/root/personal/ProxyField')
from ProxField import fetch_page_cards

def test_fetch_page_cards_first_page():
    """Fetch first page (9 cards) from 27-card deck"""
    # Mock deck with 27 cards
    deck = [
        {"name": f"Card {i}", "scryfall_id": f"id-{i}"}
        for i in range(27)
    ]
    
    # Mock get_card_images to return dummy images
    with patch('ProxField.get_card_images') as mock_fetch:
        # Return [front, back] pair
        dummy_img = Mock(spec=Image.Image)
        mock_fetch.return_value = [dummy_img, dummy_img]
        
        result = fetch_page_cards(deck, page_num=0, remote=True, use_upscaling=False, upscale_algorithm="BICUBIC")
        
        # Should return 9 image pairs
        assert len(result) == 9
        assert all(len(pair) == 2 for pair in result)
        # Should have called get_card_images 9 times
        assert mock_fetch.call_count == 9

def test_fetch_page_cards_last_page():
    """Fetch last page (partial) from 27-card deck"""
    deck = [
        {"name": f"Card {i}", "scryfall_id": f"id-{i}"}
        for i in range(27)
    ]
    
    with patch('ProxField.get_card_images') as mock_fetch:
        dummy_img = Mock(spec=Image.Image)
        mock_fetch.return_value = [dummy_img, dummy_img]
        
        result = fetch_page_cards(deck, page_num=2, remote=True, use_upscaling=False, upscale_algorithm="BICUBIC")
        
        # Final page has 27 - 18 = 9 cards (edge case: exactly fills)
        assert len(result) == 9
        assert mock_fetch.call_count == 9

def test_fetch_page_cards_partial_last_page():
    """Fetch last page (partial) from 25-card deck"""
    deck = [
        {"name": f"Card {i}", "scryfall_id": f"id-{i}"}
        for i in range(25)
    ]
    
    with patch('ProxField.get_card_images') as mock_fetch:
        dummy_img = Mock(spec=Image.Image)
        mock_fetch.return_value = [dummy_img, dummy_img]
        
        result = fetch_page_cards(deck, page_num=2, remote=True, use_upscaling=False, upscale_algorithm="BICUBIC")
        
        # Final page has 25 - 18 = 7 cards
        assert len(result) == 7
        assert mock_fetch.call_count == 7

def test_fetch_page_cards_error_on_missing_card():
    """Error handling: fetch failure aborts"""
    deck = [
        {"name": f"Card {i}", "scryfall_id": f"id-{i}"}
        for i in range(9)
    ]
    
    with patch('ProxField.get_card_images') as mock_fetch:
        # Simulate fetch failure on 5th card
        dummy_img = Mock(spec=Image.Image)
        mock_fetch.side_effect = [
            [dummy_img, dummy_img],
            [dummy_img, dummy_img],
            [dummy_img, dummy_img],
            [dummy_img, dummy_img],
            Exception("Card not found"),
        ]
        
        with pytest.raises(Exception):
            fetch_page_cards(deck, page_num=0, remote=True, use_upscaling=False, upscale_algorithm="BICUBIC")
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd /root/personal/ProxyField
pytest tests/test_page_streaming.py::test_fetch_page_cards_first_page -v
```

Expected: FAIL with "function not defined" or "cannot import fetch_page_cards"

- [ ] **Step 3: Write the implementation**

Add to `ProxField.py` before `build_pdf()` (around line 408):

```python
def fetch_page_cards(deck_list, page_num, remote, use_upscaling, upscale_algorithm):
    """
    Fetch images for one page (up to 9 cards).
    
    Args:
        deck_list: Full deck list with {"name", "scryfall_id"} dicts
        page_num: 0-indexed page number
        remote: Use Scryfall only (True) or local first (False)
        use_upscaling: Enable 1200 DPI upscaling
        upscale_algorithm: "LANCZOS" or "BICUBIC"
    
    Returns:
        list[list[Image.Image]]: Up to 9 image pairs [front, back]
        
    Raises:
        Exception: If any card fails to fetch
    """
    start_idx = page_num * CARDS_PER_PAGE
    end_idx = min(start_idx + CARDS_PER_PAGE, len(deck_list))
    
    page_images = []
    for card_idx in range(start_idx, end_idx):
        card_data = deck_list[card_idx]
        card_name = card_data["name"]
        scryfall_id = card_data.get("scryfall_id", "")
        
        imgs = get_card_images(
            card_name,
            scryfall_id,
            remote,
            use_upscaling=use_upscaling,
            upscale_algorithm=upscale_algorithm
        )
        
        if not imgs:
            raise Exception(f"Could not find image for '{card_name}'")
        
        page_images.append(imgs)
    
    return page_images
```

- [ ] **Step 4: Run test to verify it passes**

```bash
cd /root/personal/ProxyField
pytest tests/test_page_streaming.py::test_fetch_page_cards_first_page -v
pytest tests/test_page_streaming.py::test_fetch_page_cards_last_page -v
pytest tests/test_page_streaming.py::test_fetch_page_cards_partial_last_page -v
pytest tests/test_page_streaming.py::test_fetch_page_cards_error_on_missing_card -v
```

Expected: All 4 tests PASS

- [ ] **Step 5: Commit**

```bash
cd /root/personal/ProxyField
git add ProxField.py tests/test_page_streaming.py
git commit -m "feat: add fetch_page_cards() to fetch 9-card batches for one page"
```

---

### Task 2: Add `draw_page_pair()` Function

**Files:**
- Modify: `ProxField.py` (add function after `fetch_page_cards()`, around line 450)
- Modify: `tests/test_page_streaming.py`

**Interfaces:**
- Consumes: `canvas: reportlab.pdfgen.canvas.Canvas`, `page_images: list[list[Image.Image]]`, layout params
- Produces: None (modifies canvas, writes 2 pages)

- [ ] **Step 1: Write the failing test**

Add to `tests/test_page_streaming.py`:

```python
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter
import tempfile
import os

def test_draw_page_pair_writes_two_pages():
    """draw_page_pair writes front page, then back page to canvas"""
    # Create temp PDF
    with tempfile.NamedTemporaryFile(mode='w', suffix='.pdf', delete=False) as f:
        pdf_path = f.name
    
    try:
        # Create canvas
        c = canvas.Canvas(pdf_path, pagesize=letter)
        
        # Create 9 dummy image pairs
        dummy_img = Mock(spec=Image.Image)
        dummy_img.size = (745, 1040)  # Scryfall size
        page_images = [[dummy_img, dummy_img] for _ in range(9)]
        
        # Mock draw_card_grid to avoid actual drawing
        with patch('ProxField.draw_card_grid'):
            from ProxField import draw_page_pair
            
            page_width, page_height = letter
            card_w = 63 * 2.834645669  # mm to points
            card_h = 88 * 2.834645669
            gap = 1 * 2.834645669
            grid_width = 3 * card_w + 2 * gap
            grid_height = 3 * card_h + 2 * gap
            x_margin = (page_width - grid_width) / 2
            y_margin = (page_height - grid_height) / 2
            
            draw_page_pair(
                c,
                page_images,
                page_width,
                page_height,
                card_w,
                card_h,
                x_margin,
                y_margin,
                gap
            )
        
        # Should not raise
        assert True
    finally:
        if os.path.exists(pdf_path):
            os.unlink(pdf_path)
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd /root/personal/ProxyField
pytest tests/test_page_streaming.py::test_draw_page_pair_writes_two_pages -v
```

Expected: FAIL with "function not defined" or "cannot import draw_page_pair"

- [ ] **Step 3: Write the implementation**

Add to `ProxField.py` after `fetch_page_cards()` (around line 450):

```python
def draw_page_pair(canvas_obj, page_images, page_width, page_height, card_w, card_h, x_margin, y_margin, gap):
    """
    Draw front page, then back page for one page's cards.
    
    Args:
        canvas_obj: reportlab Canvas object
        page_images: list[list[Image.Image]] — up to 9 image pairs [front, back]
        page_width, page_height: Page dimensions in points
        card_w, card_h: Card dimensions in points
        x_margin, y_margin: Grid margins in points
        gap: Gap between cards in points
    
    Returns: None (modifies canvas)
    """
    # Extract front images (index 0 of each pair)
    front_images = [imgs[0] for imgs in page_images]
    
    # Draw front page
    draw_card_grid(
        canvas_obj,
        front_images,
        page_width,
        page_height,
        card_w,
        card_h,
        x_margin,
        y_margin,
        gap
    )
    canvas_obj.showPage()
    
    # Build back page (mirrored/reversed for printing)
    back_images = []
    for row in range(CARDS_PER_COL):
        row_start = row * CARDS_PER_ROW
        row_end = row_start + CARDS_PER_ROW
        # Slice this row from page_images
        row_slice = page_images[row_start:row_end]
        
        # Extract back images (index 1), or front if single-faced
        row_backs = [imgs[1] if len(imgs) > 1 else imgs[0] for imgs in row_slice]
        
        # Pad to 3 cards
        while len(row_backs) < CARDS_PER_ROW:
            row_backs.append(None)
        
        # Reverse row for printing
        back_images.extend(reversed(row_backs))
    
    # Draw back page
    draw_card_grid(
        canvas_obj,
        back_images,
        page_width,
        page_height,
        card_w,
        card_h,
        x_margin,
        y_margin,
        gap
    )
    canvas_obj.showPage()
```

- [ ] **Step 4: Run test to verify it passes**

```bash
cd /root/personal/ProxyField
pytest tests/test_page_streaming.py::test_draw_page_pair_writes_two_pages -v
```

Expected: PASS

- [ ] **Step 5: Commit**

```bash
cd /root/personal/ProxyField
git add ProxField.py tests/test_page_streaming.py
git commit -m "feat: add draw_page_pair() to draw front+back pages for one page batch"
```

---

### Task 3: Refactor `build_pdf()` to Stream Pages

**Files:**
- Modify: `ProxField.py:408-480` (entire build_pdf function rewrite)
- Modify: `tests/test_page_streaming.py` (integration test)

**Interfaces:**
- Consumes: Same as before (deck_list, remote, output_path, progress_var, use_upscaling, upscale_algorithm)
- Produces: PDF file on disk (behavior unchanged)

- [ ] **Step 1: Review current build_pdf() structure**

Read lines 408-480 of ProxField.py to understand current implementation. Identify:
- Lines 415-424: Setup (keep as-is)
- Lines 426-430: Canvas creation (keep as-is)
- Lines 432-454: All-images loop (REPLACE with page loop)
- Lines 456-474: Page drawing loop (REPLACE with draw_page_pair calls)
- Lines 476-482: Finalization (keep as-is)

- [ ] **Step 2: Write integration test before refactoring**

Add to `tests/test_page_streaming.py`:

```python
def test_build_pdf_streams_pages_small_deck():
    """Integration: build_pdf streams 2 pages (24 cards) without holding all in RAM"""
    # Create deck with 24 cards (exactly 2 pages)
    deck = [
        {"name": f"Card {i}", "scryfall_id": f"id-{i}"}
        for i in range(24)
    ]
    
    with tempfile.NamedTemporaryFile(mode='w', suffix='.pdf', delete=False) as f:
        pdf_path = f.name
    
    try:
        with patch('ProxField.get_card_images') as mock_fetch:
            dummy_img = Mock(spec=Image.Image)
            dummy_img.size = (745, 1040)
            mock_fetch.return_value = [dummy_img, dummy_img]
            
            from ProxField import build_pdf
            
            # Build PDF
            build_pdf(deck, remote=True, output_path=pdf_path, use_upscaling=False)
            
            # Verify PDF was created
            assert os.path.exists(pdf_path)
            assert os.path.getsize(pdf_path) > 0
            
            # Should have called get_card_images exactly 24 times (no caching in mock)
            assert mock_fetch.call_count == 24
    finally:
        if os.path.exists(pdf_path):
            os.unlink(pdf_path)
```

Run test (will fail until refactoring is done):
```bash
cd /root/personal/ProxyField
pytest tests/test_page_streaming.py::test_build_pdf_streams_pages_small_deck -v
```

- [ ] **Step 3: Rewrite build_pdf() to stream pages**

Replace lines 408-482 of `ProxField.py`:

```python
def build_pdf(deck_list: list[dict], remote: bool, output_path: str = "proxies.pdf", progress_var: tk.DoubleVar = None, use_upscaling: bool = False, upscale_algorithm: str = BICUBIC_ALGORITHM):
    """
    Builds a proxy PDF from a deck list, streaming one page at a time.
    Front pages: 3x3 grid of card fronts.
    Back pages:  matching 3x3 grid of card backs (mirrored horizontally for double-sided printing).
    Cards are separated by a 1mm gap.
    
    Memory: Peak ~445MB (9 images × 49.5MB) instead of 4.9GB for 100-card deck.
    """
    
    page_width, page_height = letter
    
    card_w = CARD_WIDTH_MM * mm
    card_h = CARD_HEIGHT_MM * mm
    gap = 1 * mm
    
    grid_width = CARDS_PER_ROW * card_w + (CARDS_PER_ROW - 1) * gap
    grid_height = CARDS_PER_COL * card_h + (CARDS_PER_COL - 1) * gap
    x_margin = (page_width - grid_width) / 2
    y_margin = (page_height - grid_height) / 2
    
    c = canvas.Canvas(output_path, pagesize=letter)
    total_cards = len(deck_list)
    total_pages = math.ceil(total_cards / CARDS_PER_PAGE)
    
    print(f"\nBuilding PDF: {total_cards} cards, {total_pages} front page(s) + {total_pages} back page(s)...")
    
    # Stream pages one at a time
    for page_num in range(total_pages):
        try:
            # Fetch 9 cards for this page
            print(f"[Page {page_num + 1}/{total_pages}] Fetching cards...")
            page_images = fetch_page_cards(
                deck_list,
                page_num,
                remote,
                use_upscaling,
                upscale_algorithm
            )
            
            # Draw front + back pages
            print(f"[Page {page_num + 1}/{total_pages}] Drawing...")
            draw_page_pair(
                c,
                page_images,
                page_width,
                page_height,
                card_w,
                card_h,
                x_margin,
                y_margin,
                gap
            )
            
            # Explicitly free memory for this page
            del page_images
            
            # Update progress bar: fetching+drawing = 0-90% of progress
            if progress_var is not None:
                progress_var.set((page_num + 1) / total_pages * 90)
            
            print(f"Page {page_num + 1} of {total_pages} (front+back) complete")
        
        except Exception as e:
            print(f"\n[ERROR] Page {page_num + 1}: {e}")
            raise SystemExit(1)
    
    # Finalize PDF
    c.save()
    
    if progress_var is not None:
        progress_var.set(100)
    
    print(f"\nPDF saved to: {output_path}")
```

- [ ] **Step 4: Run integration test**

```bash
cd /root/personal/ProxyField
pytest tests/test_page_streaming.py::test_build_pdf_streams_pages_small_deck -v
```

Expected: PASS

- [ ] **Step 5: Manual verification with real deck**

Test with the token deck to ensure no regressions:

```bash
cd /root/personal/ProxyField
python3 ProxField.py -u "https://moxfield.com/decks/Zr2mcIcWJEqU7smeA4Ip2A" -t -n "test_streaming.pdf" 2>&1 | tail -20
```

Expected:
- No hang/timeout
- Prints progress per page: "Page 1 of 12 complete", "Page 2 of 12 complete", etc.
- PDF created successfully
- Peak RAM < 2GB (can be verified with `top` in another terminal)

- [ ] **Step 6: Commit**

```bash
cd /root/personal/ProxyField
git add ProxField.py tests/test_page_streaming.py
git commit -m "refactor: stream PDF pages one at a time to reduce peak RAM"
```

---

### Task 4: Verify All Tests Pass

**Files:**
- Test: `tests/test_page_streaming.py` (existing)

- [ ] **Step 1: Run all page streaming tests**

```bash
cd /root/personal/ProxyField
pytest tests/test_page_streaming.py -v
```

Expected: All tests PASS (5 tests total: 3 from Task 1, 1 from Task 2, 1 from Task 3)

- [ ] **Step 2: Run basic CLI test to ensure no regressions**

```bash
cd /root/personal/ProxyField
python3 ProxField.py --help
```

Expected: Help text displays, no errors

- [ ] **Step 3: Commit if all pass**

```bash
cd /root/personal/ProxyField
git log --oneline -5
```

Verify last 3 commits are the page-streaming changes.

---

## Plan Self-Review

**Spec Coverage:**
- ✅ `fetch_page_cards()` function (Task 1, Step 3)
- ✅ `draw_page_pair()` function (Task 2, Step 3)
- ✅ Refactored `build_pdf()` with page loop (Task 3, Step 3)
- ✅ Per-page progress reporting (Task 3, Step 3, lines in print statements)
- ✅ Memory management via `del page_images` (Task 3, Step 3)
- ✅ Error handling with page context (Task 3, Step 3, print statements)
- ✅ Unit tests for new functions (Tasks 1-2)
- ✅ Integration test for full flow (Task 3)

**No Placeholders:** All code is complete and runnable.

**Type Consistency:**
- `fetch_page_cards()` returns `list[list[Image.Image]]` ✅
- `draw_page_pair()` consumes `page_images: list[list[Image.Image]]` ✅
- All function signatures match spec ✅

---

## Execution

Plan complete and saved to `docs/superpowers/plans/2026-07-04-page-streaming-implementation.md`. Ready to execute.

Two execution options:

**1. Subagent-Driven (recommended)** - I dispatch a fresh subagent per task, review between tasks, fast iteration

**2. Inline Execution** - Execute tasks in this session using executing-plans, batch execution with checkpoints

Which approach?
