# Page-Streaming PDF Generation — Design Spec

**Goal:** Enable ProxyField to generate PDFs for 100+ card decks while keeping peak RAM under 2GB.

**Problem:** Current `build_pdf()` fetches and holds ALL images in RAM before drawing any pages, consuming ~49.5 MB per upscaled image. A 100-card deck requires ~4.9GB RAM, causing OOM and performance degradation.

**Solution:** Process one page (9 cards) at a time: fetch → draw front/back pages → discard images → repeat. Peak RAM: ~445MB (9 images × 49.5MB).

---

## Architecture

### Current Flow (Memory Bottleneck)
```
build_pdf():
  all_images = []
  for each card in deck:
    imgs = fetch_card_images()  ← All held in memory
    all_images.append(imgs)
  
  for each page:
    draw_pages_from(all_images)  ← Then draw (after all fetched)
```

### Proposed Flow (Streaming)
```
build_pdf():
  for each page:
    page_images = fetch_page_cards(page_num)  ← Fetch 9 cards
    draw_page_pair(page_images)                ← Draw front + back
    del page_images                            ← Discard, free RAM
    report_progress()
```

---

## Functions

### 1. `fetch_page_cards(deck_list, page_num, remote, use_upscaling, upscale_algorithm)`

**Purpose:** Fetch images for one page (9 cards).

**Inputs:**
- `deck_list: list[dict]` — Full deck (name + scryfall_id per card)
- `page_num: int` — 0-indexed page number
- `remote: bool` — Use Scryfall only or local first
- `use_upscaling: bool` — Enable 1200 DPI upscaling
- `upscale_algorithm: str` — "LANCZOS" or "BICUBIC"

**Returns:** `list[list[Image.Image]]` — 9 image pairs (may be < 9 if final page)
- Each pair: `[front_image, back_image]`
- Structure mirrors current `all_images` format

**Implementation:** Extract from current `build_pdf()` lines 434-454
- Calculate card start/end for this page: `start = page_num * 9`, `end = start + 9`
- Loop through `deck_list[start:end]` calling `get_card_images()` (unchanged)
- Return collected image pairs
- On error: raise exception (calling code handles abort)

**Memory:** Holds only 9 images (one page) at a time.

---

### 2. `draw_page_pair(canvas, page_images, page_width, page_height, card_w, card_h, x_margin, y_margin, gap)`

**Purpose:** Draw front page, then back page for one page's cards.

**Inputs:**
- `canvas: reportlab.pdfgen.canvas.Canvas` — PDF canvas object
- `page_images: list[list[Image.Image]]` — 9 image pairs from `fetch_page_cards()`
- Layout params: `page_width, page_height, card_w, card_h, x_margin, y_margin, gap`

**Returns:** None (modifies canvas in-place)

**Side effects:**
- Draws 9-card grid on current page (fronts)
- Calls `canvas.showPage()` (finalize front page)
- Draws 9-card back-grid (mirrored/reversed per current logic)
- Calls `canvas.showPage()` (finalize back page)

**Implementation:** Extract from current `build_pdf()` lines 456-474
- Front cards: `[imgs[0] for imgs in page_images]`
- Back cards: Build reversed/mirrored grid (reuse current logic, lines 466-472)
- Call `draw_card_grid()` twice (front, then back)
- Call `canvas.showPage()` after each grid

**Memory:** No additional memory (canvas writes directly to PDF file).

---

### 3. `build_pdf()` — Refactored

**Signature:** (unchanged from current)
```python
def build_pdf(
    deck_list: list[dict],
    remote: bool,
    output_path: str = "proxies.pdf",
    progress_var: tk.DoubleVar = None,
    use_upscaling: bool = False,
    upscale_algorithm: str = BICUBIC_ALGORITHM
) -> None:
```

**New Implementation:**

```python
def build_pdf(...):
    # Setup (unchanged)
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
            page_images = fetch_page_cards(
                deck_list,
                page_num,
                remote,
                use_upscaling,
                upscale_algorithm
            )
            
            # Draw front + back pages
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
            
            # Discard images and free RAM
            del page_images
            
            # Report progress
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

**Memory:** Peak ~445MB (9 images × 49.5MB + overhead)

---

## Error Handling

**Current behavior (preserved):**
- If any card fails to fetch → abort immediately
- Print error message with card name and page number

**Improved message:**
- Old: `"Could not find an image for 'Card Name'. Aborting."`
- New: `"Page 3: Could not find an image for 'Card Name'. Aborting."`

---

## Progress Reporting

**Per-page granularity (as requested):**
```
Building PDF: 108 cards, 12 front page(s) + 12 back page(s)...
Page 1 of 12 (front+back) complete
Page 2 of 12 (front+back) complete
...
Page 12 of 12 (front+back) complete

PDF saved to: test_with_tokens.pdf
```

**Progress bar (GUI mode):**
- Linear: `0% → 90%` as pages complete
- Final: `90% → 100%` as PDF is saved

---

## Testing

### Unit Tests

**Test `fetch_page_cards()`:**
- Mock deck with 27 cards (3 pages)
- Verify page 0 returns cards 0-8
- Verify page 1 returns cards 9-17
- Verify page 2 returns cards 18-26
- Verify error handling (card fetch failure)

**Test `draw_page_pair()`:**
- Create canvas, 9 image pairs (use test PNGs)
- Call `draw_page_pair()`
- Verify canvas has 2 pages drawn (front + back)
- Verify no images retained after return

### Integration Tests

**Small deck (12 cards = 1 full page + 1 partial):**
- Generate PDF with tokens enabled
- Verify 2 pages (1 full front + 1 full back, then 1 partial front + 1 partial back)
- Verify PDF is valid and readable
- Verify peak RAM < 1GB

**Large deck (100+ cards):**
- Generate PDF
- Monitor peak RAM (should be < 2GB)
- Verify PDF pages count = `ceil(100 / 9) * 2`

---

## Impact on Existing Code

**Unchanged:**
- `get_card_images()` — Image fetching logic
- `extract_images_from_scryfall_data()` — Image extraction
- `get_scryfall_images()` — Scryfall API calls
- `upscale_image()` — Upscaling logic
- `draw_card_grid()` — Grid drawing (reused)

**Removed/Deprecated:**
- Current `build_pdf()` lines 432-454 (all-images loop) — replaced by `fetch_page_cards()`
- Current `build_pdf()` lines 456-474 (page-drawing loop) — replaced by `draw_page_pair()`

**New:**
- `fetch_page_cards()` function
- `draw_page_pair()` function

---

## Success Criteria

✅ Support 100+ card decks
✅ Peak RAM < 2GB
✅ Per-page progress reporting
✅ Page layout unchanged (front/back pairing preserved)
✅ All existing features work (tokens, upscaling, caching, local art)
✅ Error handling improved with page context
