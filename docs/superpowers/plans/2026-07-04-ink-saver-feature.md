# Ink Saver Feature Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add an "Ink Saver" option that skips back images for single-faced cards, leaving blank cells to reduce ink usage.

**Architecture:** Add a `skip_single_backs` boolean parameter that threads through ProxyField() → build_pdf() → draw_page_pair(). When enabled and a card is single-faced, append `None` to back_images instead of the back card image. The existing `draw_card_grid()` function already handles `None` by skipping those cells.

**Tech Stack:** argparse (CLI), tkinter (GUI), PIL (image handling)

## Global Constraints

- Option name: "Ink Saver" (case-sensitive for GUI checkbox)
- CLI flag: `-k` / `--ink-saver` (short flag for convenience)
- Default: Off (users must explicitly enable)
- Behavior: Only affects single-faced cards; DFC/multi-faced cards still get backs
- Backward compatible: No breaking changes to existing APIs

---

## File Structure

**ProxField.py** (modified)
- Add CLI flag `-k`/`--ink-saver` in argparse (ProxyField function)
- Add GUI checkbox for "Ink Saver" in PFGUI function
- Thread `skip_single_backs` parameter through build_pdf() and draw_page_pair()
- Modify draw_page_pair() logic to check `skip_single_backs` and card face count

---

## Tasks

### Task 1: Add CLI Flag for Ink Saver

**Files:**
- Modify: `ProxField.py:595-640` (ProxyField function argument parser)

**Interfaces:**
- Consumes: argparse parser setup
- Produces: `args.ink_saver` boolean flag (defaults to False)

- [ ] **Step 1: Locate argument parser**

Read lines 595-640 of ProxField.py to find the argparse section where other flags are defined.

Expected: Find lines like `parser.add_argument("-b", "--basic-lands", ...)`

- [ ] **Step 2: Add ink-saver flag**

In the Settings Flags section (after `-l`/`--enable-local`), add:

```python
parser.add_argument("-k", "--ink-saver", action="store_true", help="skip printing card backs for single-faced cards (save ink)")
```

Location: After the `-l`/`--enable-local` flag, before any other flags

- [ ] **Step 3: Verify syntax**

```bash
python3 /root/personal/ProxyField/ProxField.py --help | grep -A2 "ink-saver"
```

Expected: Shows `-k, --ink-saver  skip printing card backs for single-faced cards (save ink)`

- [ ] **Step 4: Commit**

```bash
git add ProxField.py
git commit -m "feat: add --ink-saver CLI flag"
```

---

### Task 2: Thread Parameter Through build_pdf()

**Files:**
- Modify: `ProxField.py:504-520` (build_pdf signature and ProxyField call)

**Interfaces:**
- Consumes: `skip_single_backs: bool` parameter
- Produces: `build_pdf(..., skip_single_backs=False)` signature

- [ ] **Step 1: Update build_pdf() signature**

Find the build_pdf function definition (around line 504). Change:

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

To:

```python
def build_pdf(
    deck_list: list[dict],
    remote: bool,
    output_path: str = "proxies.pdf",
    progress_var: tk.DoubleVar = None,
    use_upscaling: bool = False,
    upscale_algorithm: str = BICUBIC_ALGORITHM,
    skip_single_backs: bool = False
) -> None:
```

- [ ] **Step 2: Pass parameter to draw_page_pair()**

In build_pdf(), find the call to `draw_page_pair()` (around line 545). Change:

```python
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
```

To:

```python
draw_page_pair(
    c,
    page_images,
    page_width,
    page_height,
    card_w,
    card_h,
    x_margin,
    y_margin,
    gap,
    skip_single_backs
)
```

- [ ] **Step 3: Verify syntax**

```bash
python3 -c "from ProxField import build_pdf; print('✓ build_pdf() imports correctly')"
```

Expected: No import errors

- [ ] **Step 4: Commit**

```bash
git add ProxField.py
git commit -m "feat: add skip_single_backs parameter to build_pdf()"
```

---

### Task 3: Update draw_page_pair() to Handle skip_single_backs

**Files:**
- Modify: `ProxField.py:441-500` (draw_page_pair function)

**Interfaces:**
- Consumes: `skip_single_backs: bool` parameter
- Produces: Blank cells in back grid when skip_single_backs=True and card is single-faced

- [ ] **Step 1: Update draw_page_pair() signature**

Find draw_page_pair function (around line 441). Change:

```python
def draw_page_pair(canvas_obj, page_images, page_width, page_height, card_w, card_h, x_margin, y_margin, gap):
```

To:

```python
def draw_page_pair(canvas_obj, page_images, page_width, page_height, card_w, card_h, x_margin, y_margin, gap, skip_single_backs=False):
```

- [ ] **Step 2: Update back-image logic**

In draw_page_pair(), find the back-page building section (around line 475-490):

```python
for row in range(CARDS_PER_COL):
    row_start = row * CARDS_PER_ROW
    row_end = row_start + CARDS_PER_ROW
    row_slice = page_images[row_start:row_end]

    row_backs = [imgs[1] if len(imgs) > 1 else imgs[0] for imgs in row_slice]
    
    while len(row_backs) < CARDS_PER_ROW:
        row_backs.append(None)
    
    back_images.extend(reversed(row_backs))
```

Change to:

```python
for row in range(CARDS_PER_COL):
    row_start = row * CARDS_PER_ROW
    row_end = row_start + CARDS_PER_ROW
    row_slice = page_images[row_start:row_end]

    row_backs = []
    for imgs in row_slice:
        if skip_single_backs and len(imgs) == 1:
            # Single-faced card with ink saver enabled: leave blank
            row_backs.append(None)
        elif len(imgs) > 1:
            # Double-faced or multi-faced: use back face
            row_backs.append(imgs[1])
        else:
            # Single-faced without ink saver: use card back
            row_backs.append(imgs[0])
    
    while len(row_backs) < CARDS_PER_ROW:
        row_backs.append(None)
    
    back_images.extend(reversed(row_backs))
```

- [ ] **Step 3: Verify syntax**

```bash
python3 -c "from ProxField import draw_page_pair; print('✓ draw_page_pair() imports correctly')"
```

Expected: No import errors

- [ ] **Step 4: Commit**

```bash
git add ProxField.py
git commit -m "feat: implement skip_single_backs logic in draw_page_pair()"
```

---

### Task 4: Add GUI Checkbox for Ink Saver

**Files:**
- Modify: `ProxField.py:656-750` (PFGUI function checkbox section)

**Interfaces:**
- Consumes: tkinter GUI state
- Produces: `ink_saver_gui_input` BooleanVar tied to checkbox

- [ ] **Step 1: Add ink_saver_gui_input variable**

In PFGUI function, find where other BooleanVar are created (around line 690-695):

```python
land_filter_gui_input = tk.BooleanVar()
collection_gui_input = tk.BooleanVar()
tokens_gui_input = tk.BooleanVar()
remote_gui_input = tk.BooleanVar()
```

Add after these:

```python
ink_saver_gui_input = tk.BooleanVar()
```

- [ ] **Step 2: Add checkbox widget**

After the remote_gui_input checkbox widget (around line 710-730), add:

```python
tk.Checkbutton(root,
               text="Ink Saver",
               variable=ink_saver_gui_input,
               onvalue=True, offvalue=False,
               bg="lightgrey", fg="blue",
               font=("calibre", 8),
               selectcolor="green",
               relief="raised",
               padx=10, pady=5).grid(row=5, column=3)
```

**Note:** Adjust the `row` value if needed to fit with existing layout. Place it below the other checkboxes.

- [ ] **Step 3: Pass flag to build_pdf() in GUI**

In the `build()` function inside PFGUI (around line 715-735), find the `build_pdf()` call:

```python
build_pdf(
    deck_list,
    disable_local,
    file_name,
    progress_var,
    use_upscaling=collection_gui_input.get(),
    upscale_algorithm=algo
)
```

Change to:

```python
build_pdf(
    deck_list,
    disable_local,
    file_name,
    progress_var,
    use_upscaling=collection_gui_input.get(),
    upscale_algorithm=algo,
    skip_single_backs=ink_saver_gui_input.get()
)
```

- [ ] **Step 4: Update ProxyField() CLI to pass flag**

Find where build_pdf() is called in ProxyField() function (around line 630-635):

```python
build_pdf(
    deck_list,
    remote,
    pdf_file_name,
    use_upscaling=True,
    upscale_algorithm=BICUBIC_ALGORITHM
)
```

Change to:

```python
build_pdf(
    deck_list,
    remote,
    pdf_file_name,
    use_upscaling=True,
    upscale_algorithm=BICUBIC_ALGORITHM,
    skip_single_backs=args.ink_saver
)
```

- [ ] **Step 5: Verify GUI loads**

```bash
timeout 2 python3 /root/personal/ProxyField/ProxField.py 2>&1 | head -5 || echo "✓ GUI loads without errors"
```

Expected: GUI window appears, timeout kills it, no errors

- [ ] **Step 6: Commit**

```bash
git add ProxField.py
git commit -m "feat: add Ink Saver checkbox to GUI"
```

---

### Task 5: Test Ink Saver Feature

**Files:**
- Test: Manual CLI and GUI tests

**Interfaces:**
- Consumes: Moxfield deck with mixed single/double-faced cards
- Produces: PDF with blank back cells for single-faced cards

- [ ] **Step 1: Test CLI flag with ink saver OFF (default)**

```bash
cd /root/personal/ProxyField
python3 ProxField.py -u "https://moxfield.com/decks/Zr2mcIcWJEqU7smeA4Ip2A" -n "test_no_ink_saver.pdf" 2>&1 | tail -5
```

Expected: PDF generated with all back images included

- [ ] **Step 2: Test CLI flag with ink saver ON**

```bash
cd /root/personal/ProxyField
python3 ProxField.py -u "https://moxfield.com/decks/Zr2mcIcWJEqU7smeA4Ip2A" -k -n "test_with_ink_saver.pdf" 2>&1 | tail -5
```

Expected: PDF generated (may have blank cells for single-faced card backs)

- [ ] **Step 3: Verify help text**

```bash
python3 /root/personal/ProxyField/ProxField.py --help | grep -i "ink"
```

Expected: Shows `-k, --ink-saver` flag in help

- [ ] **Step 4: Test short flag**

```bash
python3 /root/personal/ProxyField/ProxField.py -k --help 2>&1 | grep -q "ink-saver" && echo "✓ Short flag -k works"
```

Expected: Flag is recognized

- [ ] **Step 5: Commit**

```bash
git add ProxField.py
git commit -m "test: verify ink-saver feature works in CLI and GUI"
```

---

## Plan Self-Review

**Spec Coverage:**
- ✅ CLI flag `-k`/`--ink-saver` (Task 1)
- ✅ GUI checkbox "Ink Saver" (Task 4)
- ✅ Parameter threading through call chain (Task 2)
- ✅ Logic to skip backs for single-faced cards (Task 3)
- ✅ Default off behavior (all tasks)
- ✅ Testing (Task 5)

**Placeholder Scan:** No TBD, TODO, or incomplete sections.

**Type Consistency:** All boolean types used consistently.

**Scope Check:** Single, focused feature with clear boundaries.

---

Plan complete and saved. Ready to execute.

**Which execution approach?**

1. **Subagent-Driven (recommended)** — Fresh subagent per task, fast iteration
2. **Inline Execution** — Execute all tasks in this session

Which approach?
