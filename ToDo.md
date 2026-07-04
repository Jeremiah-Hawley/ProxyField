# ProxyField Reliability Roadmap

## Phase 1: Core Reliability Fixes

### Spec 1: Image Quality via PIL Upscaling
**Problem:** Scryfall images are too pixelated/blurry when printed at card size.

**Solution:** Upscale images using PIL before adding to PDF.

**Requirements:**
- **Target resolution:** Calculate based on 1200 DPI for standard MTG card (63mm × 88mm)
  - Width: 63mm = 2.48" → 2.48 × 1200 = ~2976px
  - Height: 88mm = 3.46" → 3.46 × 1200 = ~4152px
- **Upscaling algorithm:**
  - Use LANCZOS if "Add to Collection" checkbox is ON (highest quality, slower)
  - Use BICUBIC if "Add to Collection" checkbox is OFF (good quality, faster)
- **Caching:**
  - If "Add to Collection" ON: Cache upscaled images to `./Storage/CardArt/` named by Scryfall ID
  - If "Add to Collection" OFF: Generate on-the-fly, don't cache
- **Timing:** Upscale AFTER fetching from Scryfall, BEFORE pairing with card back
- **Fallback:** If upscaling fails, use original image (with warning to user)

**Implementation Notes:**
- Moxfield API returns Scryfall ID directly in card data — extract and pass to Scryfall request (saves parsing)
- PIL `Image.resize()` with `Image.LANCZOS` / `Image.BICUBIC` resample filters
- Check if upscaled image already exists locally before upscaling (keyed by Scryfall ID)
- **Error handling:** If upscaling fails, abort with clear error message to user (don't fall back to unupscaled)

---

### Spec 2: Tokens Functionality
**Problem:** Token parsing is incomplete; Moxfield API returns non-token items mixed with tokens.

**Solution:** Filter Moxfield token board correctly and fetch token images from Scryfall.

**Requirements:**
- **Parsing:** Only include items where `isToken == true` (case-insensitive comparison)
- **Fetching:** For each valid token:
  - Query Scryfall API with fuzzy search (same as regular cards)
  - Handle double-faced tokens (almost all tokens are double-sided)
- **Printing:** Print tokens at same size as regular cards (same grid/PDF layout)
- **Flag behavior:** When `--tokens` flag is used, include ALL tokens (no filtering by token type)
- **Integration:** Tokens should go through the same image upscaling pipeline as regular cards
- **Layout:** Append tokens to end of deck, don't create new page (flow naturally into grid)

**Implementation Notes:**
- Current `get_tokens_for_pdf()` is incomplete; needs to be rewritten or fixed from older branch
- Token fetching should use the same `get_scryfall_images()` function as regular cards
- Append token list to main deck_list before building PDF (tokens go at the end, no page break)

**Status:** Code exists in older branch/version; may need recovery or rewrite

---

### Spec 3: Dead Code Cleanup
**Problem:** Multiple incomplete/broken functions and variables with bad scoping.

**Solution:** Mark broken code as non-functional and fix variable scoping issues.

**Broken Code to Preserve (Mark as Non-Functional):**
1. `read_decklist_file()` (line 141) — broken variable names (`url_input`, `dl_path` undefined; `decklength` typo)
2. `get_token_scryfall_imagesfall_images()` (line 172) — function name typo, stub implementation
3. Commented-out token image fetching code (lines 47–98)

**Mark as non-functional:**
- Add clear `# [NON-FUNCTIONAL]` comment at function definition
- Document why in a brief comment (e.g., "variable names undefined", "stub implementation")
- Do NOT delete or fully remove

**Variable Scoping Issues to Fix:**
1. `land_filter` (line 35) — declared globally, modified in `ProxyField()` locally (line 383)
2. `token_filter` (declared implicitly in `ProxyField()`, used in `get_tokens_for_pdf()`)
3. `DECK_SIZE` (line 32) — assigned in `read_url()` (line 137) but never used

**Fix approach:**
- Convert `land_filter` and `token_filter` to proper function parameters instead of globals
- Update all callers to pass these as arguments
- Remove unused `DECK_SIZE` variable entirely

**Implementation Notes:**
- Functions affected: `read_url()`, `build_pdf()`, `PFGUI()`, internal functions
- This is primarily refactoring for code clarity; no behavior change

---

## Next Steps

- User approves/adjusts specs above
- Write implementation plan
- Execute Phase 1
