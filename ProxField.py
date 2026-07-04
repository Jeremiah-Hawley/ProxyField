#!/usr/bin/python3

import os
import argparse
import math
import requests
import re
import threading
import time

from time import sleep
from reportlab.lib.utils import ImageReader
from PIL import Image
from reportlab.lib.pagesizes import letter
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas
from io import BytesIO
from curl_cffi import requests as curl_requests

import tkinter as tk

SCRYFALL_HEADERS = {"User-Agent": "ProxyField/1.0 (https://github.com/user/ProxyField)"}
from tkinter.ttk import *
from tkinter import filedialog

LOCAL_IMAGE_DIR = "./Storage/CardArt/"
CARD_BACK_PATH = "./Storage/CardArt/Back.png"
CARD_WIDTH_MM   = 63  # standard MTG card size
SLEEP_AMOUNT = 1.5
CARD_HEIGHT_MM  = 88
CARDS_PER_ROW   = 3
CARDS_PER_COL   = 3
CARDS_PER_PAGE  = CARDS_PER_ROW * CARDS_PER_COL
PROGRESS        = 0 #store progress bar value here
UPSCALE_DPI = 1200  # Target DPI for printing
LANCZOS_ALGORITHM = "LANCZOS"
BICUBIC_ALGORITHM = "BICUBIC"
BASIC_LANDS = ["Plains", "Island", "Swamp", "Mountain", "Forest"]
land_filter = False #has to be declared here and changed later

def get_tokens_from_moxfield(moxfield_data: dict) -> list[dict]:
    """
    Extract tokens from Moxfield API data.
    Filters for items where isToken == true (case-insensitive comparison).
    Returns list of dicts: {"name": str, "scryfall_id": str}
    """
    tokens = []
    token_board = moxfield_data.get("tokens", [])

    if not isinstance(token_board, list):
        print(f"  [Tokens] Unexpected token board format: {type(token_board)}")
        return tokens

    for card_entry in token_board:
        # Check if this is actually a token
        is_token = card_entry.get("isToken", False)

        # Handle both string and boolean values for isToken
        if isinstance(is_token, str):
            is_token = is_token.lower() == "true"
        elif not isinstance(is_token, bool):
            is_token = False

        if is_token:
            # Token fields are at the top level of the entry, not nested under "card"
            token_name = card_entry.get("name", "Unknown Token")
            scryfall_id = card_entry.get("scryfall_id", "")

            if token_name and token_name != "Unknown Token":
                tokens.append({"name": token_name, "scryfall_id": scryfall_id})
                print(f"  [Tokens] Found: {token_name}")

    return tokens


def read_url(deck_url: str, land_filter: bool, include_tokens: bool = False) -> list[dict]:
    match = re.search(r"moxfield\.com/decks/([A-Za-z0-9_-]+)", deck_url)
    if match:
        deck_id = match.group(1)
    elif re.fullmatch(r"[A-Za-z0-9_-]+", deck_url):
        deck_id = deck_url
    else:
        raise ValueError(f"Could not extract a deck ID from: {deck_url!r}")

    api_url = f"https://api2.moxfield.com/v2/decks/all/{deck_id}"

    response = curl_requests.get(api_url, impersonate="chrome120", timeout=(2,5))

    if response.status_code == 403:
        raise SystemExit("[ERROR] Moxfield returned 403 Forbidden — the deck may be private.")
    if response.status_code == 404:
        raise SystemExit(f"[ERROR] Deck not found: {deck_id}")

    response.raise_for_status()
    data = response.json()


    boards_to_include = ["mainboard", "sideboard", "commanders", "companions", "signatureSpells", "attractions"]
    card_lines = []
    for board_name in boards_to_include:
        board = data.get(board_name, {})
        for card_entry in board.values():
            quantity = card_entry.get("quantity", 1)
            card_data = card_entry["card"]
            card_name = card_data["name"]
            scryfall_id = card_data.get("scryfall_id", "")
            for _ in range(quantity):
                card_lines.append({"name": card_name, "scryfall_id": scryfall_id})
        if not card_lines:
            raise ValueError(f"Deck '{deck_id}' appears to be empty or could not be parsed.")

    card_lines = [card for card in card_lines if card["name"] not in BASIC_LANDS] if land_filter else card_lines

    # Append tokens if requested
    if include_tokens:
        tokens = get_tokens_from_moxfield(data)
        print(f"\n  [Tokens] Added {len(tokens)} tokens to deck")
        card_lines.extend(tokens)

    return card_lines

def read_decklist_file(path: str) -> list[str]:  # [NON-FUNCTIONAL] Undefined variables: url_input, dl_path, decklength typo
    decklist = []
    if url_input[-4:] != ".txt":
        raise Exception("Sorry, only input a txt file for a decklist, alternatively input a moxfield URL.")
    else:
        with open(dl_path) as decklist_file:
            deck_length = sum(1 for line in decklength)
            for line in decklist_file:
                if len(line) > 2: #ignore empty lines
                    for i in range(int(line[0])): #for number in first char of line
                        decklist.append(str(line[1:])) #add rest to array
            decklist_file.close()
    return decklist

def get_card_name(card): 
    match = re.search(r"^\d+ (.+?) \(", card)
    return match.group(1) if match else card.split()[1]

def get_card_name_from_entry(card_entry: str) -> str:
    """Extracts just the card name from a deck list entry like 'Forest (STX) 375'"""
    match = re.match(r"^(.+?)(?:\s+\(|$)", card_entry)
    return match.group(1).strip() if match else card_entry.strip()

def get_local_image_path(card_name: str) -> str | None:
    """Returns the path to a local card image if it exists, otherwise None."""
    for ext in ["jpg", "jpeg", "png", "webp"]:
        path = os.path.join(LOCAL_IMAGE_DIR, f"{card_name}.{ext}")
        if os.path.exists(path):
            return path
    return None

def get_token_scryfall_imagesfall_images(card_id: str) ->list[Image.Image]:  # [NON-FUNCTIONAL] Stub implementation, function name has typo
    return []

def calculate_upscale_dimensions(dpi: int = UPSCALE_DPI) -> tuple[int, int]:
    """
    Calculate target pixel dimensions for upscaling based on DPI.
    MTG card size: 63mm × 88mm
    Returns: (width_px, height_px)
    """
    # Convert mm to inches, then multiply by DPI
    card_width_inches = CARD_WIDTH_MM / 25.4  # 63mm = 2.48 inches
    card_height_inches = CARD_HEIGHT_MM / 25.4  # 88mm = 3.46 inches

    target_width = int(card_width_inches * dpi)
    target_height = int(card_height_inches * dpi)

    return (target_width, target_height)

def upscale_image(image: Image.Image, algorithm: str = BICUBIC_ALGORITHM) -> Image.Image:
    """
    Upscale image to 1200 DPI print quality.

    Args:
        image: PIL Image to upscale
        algorithm: "LANCZOS" (high quality, slower) or "BICUBIC" (balanced)

    Returns:
        Upscaled PIL Image

    Raises:
        ValueError: If upscaling fails or algorithm is invalid
    """
    try:
        target_width, target_height = calculate_upscale_dimensions(UPSCALE_DPI)

        # Select resample filter
        if algorithm == LANCZOS_ALGORITHM:
            resample = Image.LANCZOS
        elif algorithm == BICUBIC_ALGORITHM:
            resample = Image.BICUBIC
        else:
            raise ValueError(f"Unknown upscaling algorithm: {algorithm}")

        # Upscale the image
        upscaled = image.resize((target_width, target_height), resample=resample)

        return upscaled

    except Exception as e:
        raise ValueError(f"Failed to upscale image: {e}")

def get_cached_upscaled_image(scryfall_id: str) -> Image.Image | None:
    """Check if upscaled image exists in cache and return it."""
    if not scryfall_id:
        return None

    cache_path = os.path.join(LOCAL_IMAGE_DIR, f"{scryfall_id}.upscaled.png")
    if os.path.exists(cache_path):
        try:
            return Image.open(cache_path)
        except Exception as e:
            print(f"  [Cache] Failed to load cached image {scryfall_id}: {e}")
            return None

    return None

def save_upscaled_image_to_cache(image: Image.Image, scryfall_id: str) -> None:
    """Save upscaled image to cache."""
    if not scryfall_id:
        return

    try:
        os.makedirs(LOCAL_IMAGE_DIR, exist_ok=True)
        cache_path = os.path.join(LOCAL_IMAGE_DIR, f"{scryfall_id}.upscaled.png")
        image.save(cache_path, "PNG")
    except Exception as e:
        print(f"  [Cache] Failed to save upscaled image {scryfall_id}: {e}")

def extract_images_from_scryfall_data(data: dict) -> list[Image.Image]:
    """Extract images from Scryfall card data (handles single and double-faced cards)."""
    images = []

    # Single-faced card
    image_uris = data.get("image_uris")
    if image_uris:
        image_url = (
            image_uris.get("png") or
            image_uris.get("large") or
            image_uris.get("normal")
        )
        if image_url:
            img_response = requests.get(image_url, headers=SCRYFALL_HEADERS, timeout=(2, 5))
            img_response.raise_for_status()
            images.append(Image.open(BytesIO(img_response.content)))
        return images

    # Double-faced card
    card_faces = data.get("card_faces", [])
    if card_faces:
        for face in card_faces:
            face_uris = face.get("image_uris", {})
            face_url = (
                face_uris.get("png") or
                face_uris.get("large") or
                face_uris.get("normal")
            )
            if face_url:
                img_response = requests.get(face_url, headers=SCRYFALL_HEADERS, timeout=(2, 5))
                img_response.raise_for_status()
                images.append(Image.open(BytesIO(img_response.content)))
        return images if images else []

    return []

def get_scryfall_images(card_name: str, scryfall_id: str = "") -> list[Image.Image]:
    """
    Fetches card image(s) from Scryfall.
    If scryfall_id is provided, uses direct ID lookup (faster, no fuzzy matching).
    Falls back to fuzzy search by card name if ID lookup fails or no ID provided.
    Returns a list with one image for normal cards, two for double-faced cards.
    """
    try:
        data = None

        # Try direct ID lookup first if we have it
        if scryfall_id:
            try:
                response = requests.get(
                    f"https://api.scryfall.com/cards/{scryfall_id}",
                    headers=SCRYFALL_HEADERS,
                    timeout=(2, 5)
                )
                if response.status_code == 200:
                    data = response.json()
                    print(f"  [Scryfall] Fetched '{card_name}' via ID")
            except Exception as e:
                print(f"  [Scryfall] ID lookup failed for {scryfall_id}: {e}, trying fuzzy search...")

        # Fallback to fuzzy search if ID lookup didn't work
        if data is None:
            response = requests.get(
                "https://api.scryfall.com/cards/named",
                params={"fuzzy": card_name},
                headers=SCRYFALL_HEADERS,
                timeout=(2, 5)
            )
            response.raise_for_status()
            data = response.json()
            print(f"  [Scryfall] Fetched '{card_name}' via fuzzy search")

        # Extract images from the data
        images = extract_images_from_scryfall_data(data)

        if not images:
            print(f"  [Scryfall] No image URLs found for '{card_name}'")
            return []

        return images

    except Exception as e:
        print(f"  [Scryfall] Failed to fetch '{card_name}': {e}")
        return []

def get_card_images(
    card_name: str,
    scryfall_id: str,
    remote: bool,
    use_upscaling: bool = False,
    upscale_algorithm: str = BICUBIC_ALGORITHM
) -> list[Image.Image]:
    """
    Returns a list of PIL Images for the given card name and scryfall_id.
    Single-faced cards return [front, card_back_image].
    Double-faced cards return [front_face, back_face].
    If remote is True:  Scryfall only.
    If remote is False: local first (single image), Scryfall as fallback.
    """
    # Load the generic card back once, crash gracefully if it's missing
    if not os.path.exists(CARD_BACK_PATH):
        raise SystemExit(f"[ERROR] Card back image not found at '{CARD_BACK_PATH}'. Please add one.")
    card_back = Image.open(CARD_BACK_PATH)

    if not remote:
        local_path = get_local_image_path(card_name)
        if local_path:
            print(f"  [Local] Found '{card_name}'")
            return [Image.open(local_path), card_back]
        print(f"  [Local] '{card_name}' not found locally, trying Scryfall...")

    print(f"  [Scryfall] Fetching '{card_name}'...")
    scryfall_images = get_scryfall_images(card_name, scryfall_id)
    time.sleep(SLEEP_AMOUNT)

    # Apply upscaling if requested
    if use_upscaling and scryfall_images:
        upscaled_images = []
        for i, img in enumerate(scryfall_images):
            # Check cache first
            if scryfall_id and i == 0:  # Cache first image only (front face)
                cached = get_cached_upscaled_image(scryfall_id)
                if cached:
                    print(f"  [Cache] Using cached upscaled image for '{card_name}'")
                    upscaled_images.append(cached)
                    continue

            # Upscale and cache
            try:
                upscaled = upscale_image(img, upscale_algorithm)
                if scryfall_id and i == 0:
                    save_upscaled_image_to_cache(upscaled, scryfall_id)
                upscaled_images.append(upscaled)
            except ValueError as e:
                print(f"\n[ERROR] {e}")
                raise SystemExit(1)

        scryfall_images = upscaled_images

    # DFC — already has both faces from Scryfall
    if len(scryfall_images) > 1:
        return scryfall_images

    # Single faced — pair with generic card back
    if len(scryfall_images) == 1:
        return [scryfall_images[0], card_back]
    return []

def draw_card_grid(c, cards_with_images, page_width, page_height, card_w, card_h, x_margin, y_margin, gap):
    """Draws a single page grid of up to 9 card images. None entries are skipped (blank cell)."""
    for i, img in enumerate(cards_with_images):
        if img is None:
            continue

        row = i // CARDS_PER_ROW
        col = i  % CARDS_PER_ROW

        x = x_margin + col * (card_w + gap)
        y = page_height - y_margin - (row + 1) * card_h - row * gap

        buffer = BytesIO()
        img.save(buffer, format="PNG")
        buffer.seek(0)
        c.drawImage(
            ImageReader(buffer), x, y,
            width=card_w, height=card_h,
            preserveAspectRatio=True
        )

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

def build_pdf(
    deck_list: list[dict],
    remote: bool,
    output_path: str = "proxies.pdf",
    progress_var: tk.DoubleVar = None,
    use_upscaling: bool = False,
    upscale_algorithm: str = BICUBIC_ALGORITHM,
    skip_single_backs: bool = False
) -> None:
    """
    Builds a proxy PDF from a deck list.
    Front pages: 3x3 grid of card fronts.
    Back pages:  matching 3x3 grid of card backs (mirrored horizontally for double-sided printing).
    Cards are separated by a 1mm gap.
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
                gap,
                skip_single_backs
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

def ProxyField():
    # First, Arg handling and variable initiation
    parser = argparse.ArgumentParser(
            prog="ProxyField",
            description="ProxyField - converts moxfield links to pdfs, CLI with flags, GUI without",
            epilog="if you find this useful, please buy me a white monster, venmo:@Jeremiah_Hawley, have a wonderful day!"
            )

                #Input Args:
    parser.add_argument("-u","--url", type=str, help="MoxField URL for deck list - make sure it's public :) ")
    parser.add_argument("-f","--file-path",type=str,help="Filepath for txt file containing deck list, URL takes priority if both are used")
    parser.add_argument("-n","--name", type=str, help="name for PDF (default is proxies.pdf)")

                #Settings Flags:
    parser.add_argument("-b", "--basic-lands", action="store_true", help="Filter out basic lands (don't include them in PDF)")
    parser.add_argument("-l","--enable-local",action="store_true",help="searches local card images in ./storage/ before asking scryfall")
    parser.add_argument("-t", "--tokens", action="store_true", help="adds all tokens to the pdf")
    parser.add_argument("-k", "--ink-saver", action="store_true", help="skip printing card backs for single-faced cards (save ink)")

    args = parser.parse_args()

    #next, check if any flags were used
    if not any(vars(args).values()):
        #if none were used go into GUI mode
        PFGUI()

    #if they were used, then assign values to variables
    land_filter = args.basic_lands
    remote = not args.enable_local
    token_filter = args.tokens
    if args.url is None:
        if args.file_path is None:
            raise Exception("you need either a MoxField URL or a deck list txt file")
        else:
            deck_filepath = args.file_path
            from_file = True
            deck_url = ""
            from_url = False
    else:
        deck_filepath = ""
        from_file = False
        deck_url = args.url
        from_url = True

    # tags read, now need to create the deck list
    if from_url:
        deck_list = read_url(deck_url, land_filter, include_tokens=token_filter)
    elif from_file:
        deck_list = read_decklist_file(deck_filepath)


    # now that we have the deck list we need to find the pictures and put them into a pdf
    pdf_file_name = "proxies.pdf"
    if args.name is not None:
        pdf_file_name = args.name

    build_pdf(
        deck_list,
        remote,
        pdf_file_name,
        use_upscaling=True,  # Always upscale in CLI
        upscale_algorithm=BICUBIC_ALGORITHM  # Use BICUBIC for CLI
    )

def PFGUI():
    disable_local = False
    deck_list = []
    token_filter = False

    # --- internal functions (buttons) ---
    def submit():
        url_string = str(url_gui_input.get())
        basic_land_filter = land_filter_gui_input.get()
        token_filter = tokens_gui_input.get()
        nonlocal disable_local
        disable_local = remote_gui_input.get()

        url_entry.delete(0, tk.END)

        # Show progress bar, disable buttons while working
        progress.grid(row=5, column=1, columnspan=3, padx=10, pady=5)
        progress_var.set(0)
        submit_button.config(state="disabled")
        save_button.grid_remove()

        nonlocal deck_list

        def fetch():
            nonlocal deck_list
            try:
                deck_list = read_url(url_string, basic_land_filter, include_tokens=token_filter)
                # Schedule UI update back on the main thread
                root.after(0, on_fetch_done)
            except Exception as e:
                root.after(0, lambda err=e: on_fetch_error(str(err)))

        def on_fetch_done():
            progress_var.set(10)  # URL fetch done, show a little progress
            submit_button.config(state="normal")
            save_button.grid(row=4, column=2)
            status_label.config(text=f"Deck loaded: {len(deck_list)} cards")

        def on_fetch_error(msg):
            submit_button.config(state="normal")
            status_label.config(text=f"Error: {msg}")

        # Run fetch in background thread so GUI doesn't freeze
        threading.Thread(target=fetch, daemon=True).start()

    def prompt_filesave():
        file_name = filedialog.asksaveasfilename(
            title="Select a filename and location",
            defaultextension=".pdf",
            filetypes=[("PDF Files", "*.pdf")])

        if not file_name:
            return  # user cancelled

        save_button.config(state="disabled")
        submit_button.config(state="disabled")
        progress_var.set(0)
        status_label.config(text="Building PDF...")

        def build():
            try:
                # Use LANCZOS if "Add to Collection" is on, BICUBIC otherwise
                algo = LANCZOS_ALGORITHM if collection_gui_input.get() else BICUBIC_ALGORITHM
                build_pdf(
                    deck_list,
                    disable_local,
                    file_name,
                    progress_var,
                    use_upscaling=collection_gui_input.get(),  # Only upscale if collecting
                    upscale_algorithm=algo
                )
                root.after(0, on_build_done)
            except Exception as e:
                root.after(0, lambda err=e: on_build_error(str(err)))

        def on_build_done():
            save_button.config(state="normal")
            submit_button.config(state="normal")
            status_label.config(text=f"PDF saved!")

        def on_build_error(msg):
            save_button.config(state="normal")
            submit_button.config(state="normal")
            status_label.config(text=f"Error: {msg}")

        threading.Thread(target=build, daemon=True).start()

    # --- Variables ---
    root = tk.Tk()
    root.title("ProxyField")
    root.geometry("400x200")

    progress_var = tk.DoubleVar(value=0)

    # --- Widgets ---
    # Land Filter Check Box
    land_filter_gui_input = tk.BooleanVar()
    tk.Checkbutton(root,
                   text="Basic Land Filter",
                   variable=land_filter_gui_input,
                   onvalue=True, offvalue=False,
                   bg="lightgrey", fg="blue",
                   font=("calibre", 8),
                   selectcolor="green",
                   relief="raised",
                   padx=10, pady=5).grid(row=1, column=3)

    # Add to Collection Check Box
    collection_gui_input = tk.BooleanVar()
    tk.Checkbutton(root,
                   text="Add to Collection",
                   variable=collection_gui_input,
                   onvalue=True, offvalue=False,
                   bg="lightgrey", fg="blue",
                   font=("calibre", 8),
                   selectcolor="green",
                   relief="raised",
                   padx=10, pady=5).grid(row=2, column=3)

    # Add Tokens Check Box
    tokens_gui_input = tk.BooleanVar()
    tk.Checkbutton(root,
                   text="Add Tokens",
                   variable=tokens_gui_input,
                   onvalue=True, offvalue=False,
                   bg="lightgrey", fg="blue",
                   font=("calibre", 8),
                   selectcolor="green",
                   relief="raised",
                   padx=10, pady=5).grid(row=3, column=3)

    # Disable Local Art Check Box
    remote_gui_input = tk.BooleanVar()
    tk.Checkbutton(root,
                   text="Disable Art Preference",
                   variable=remote_gui_input,
                   onvalue=True, offvalue=False,
                   bg="lightgrey", fg="blue",
                   font=("calibre", 8),
                   selectcolor="green",
                   relief="raised",
                   padx=10, pady=5).grid(row=4, column=3)

    # URL label and entry
    tk.Label(root, text='URL: ', font=('calibre', 10, 'bold')).grid(row=1, column=1)
    url_gui_input = tk.StringVar()
    url_entry = tk.Entry(root, textvariable=url_gui_input, font=("calibre", 10, "normal"), justify="center")
    url_entry.grid(row=1, column=2)

    # Submit button
    submit_button = tk.Button(root, text='Submit', command=submit)
    submit_button.grid(row=2, column=2)

    # Save button (hidden until deck is loaded)
    save_button = tk.Button(root, text='Save PDF', command=prompt_filesave)

    # Status label
    status_label = tk.Label(root, text="", font=("calibre", 8))
    status_label.grid(row=6, column=1, columnspan=3)

    # Progress bar (hidden until submit is pressed)
    progress = Progressbar(root, orient="horizontal", length=200, mode='determinate', variable=progress_var)

    # Run app
    root.mainloop()


if __name__ == "__main__":
    ProxyField()
