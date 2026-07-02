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
DECK_SIZE       = 0 #store decklist size here
BASIC_LANDS = ["Plains", "Island", "Swamp", "Mountain", "Forest"]
land_filter = False #has to be declared here and changed later

def get_tokens_for_pdf(deck_url: str) -> list[list[Image.Image]]:
    #create a list of IDs
    token_list = []
    if token_filter:
        token_board = data.get("tokens", [])  # default to [] not {}
        for card in token_board:              # iterate directly, no .values()
            card_is_token = card.get("isToken", False)
            print(str(card.get("name","")) + type(card_is_token))
            if card_is_token == "true" or card_is_token == True:
                print(card.get("name", "something is wrong"))    #for card in test_board:
    # [NON-FUNCTIONAL] Token image fetching incomplete — requires rewrite with proper Moxfield API parsing
    """
    #turn that into a list of images
    token_images = []
    for token in token_list:
        try:
            response = requests.get(
                "https://api.scryfall.com/cards/named",
                params={"fuzzy": card_name},
                timeout=10
            )
            
            response.raise_for_status()
            data = response.json()

            image_uris = data.get("image_uris")

            # Single faced card
            if image_uris:
                image_url = (
                    image_uris.get("png") or
                    image_uris.get("large") or
                    image_uris.get("normal")
                )
                img_response = requests.get(image_url, timeout=10)
                img_response.raise_for_status()
                token_images.append([Image.open(BytesIO(img_response.content))])

        # Double-faced card — fetch both faces
            card_faces = data.get("card_faces", [])
            if card_faces:
                images = []
                for face in card_faces:
                    face_uris = face.get("image_uris", {})
                    face_url = (
                        face_uris.get("png") or
                        face_uris.get("large") or
                        face_uris.get("normal")
                    )
                    if face_url:
                        img_response = requests.get(face_url, timeout=10)
                        img_response.raise_for_status()
                        images.append(Image.open(BytesIO(img_response.content)))
                if images:
                    token_images.append(images)

            print(f"  [Scryfall] No image URLs found for '{card_name}'")

        except Exception as e:
            print(f"  [Scryfall] Failed to fetch '{card_name}': {e}")
    
    return token_images
"""


def read_url(deck_url: str, land_filter: bool) -> list[str]:
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
            card_name = card_entry["card"]["name"]
            for _ in range(quantity):
                card_lines.append(card_name)
        if not card_lines:
            raise ValueError(f"Deck '{deck_id}' appears to be empty or could not be parsed.")

    card_lines = [card for card in card_lines if card not in BASIC_LANDS] if land_filter else card_lines

    DECK_SIZE = len(card_lines) #update DECK_SIZE

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

def get_scryfall_images(card_name: str) -> list[Image.Image]:
    """
    Fetches card image(s) from Scryfall.
    Returns a list with one image for normal cards, two for double-faced cards.
    """
    try:
        response = requests.get(
            "https://api.scryfall.com/cards/named",
            params={"fuzzy": card_name},
            timeout=(2,5)
        )
        response.raise_for_status()
        data = response.json()

        image_uris = data.get("image_uris")

        # Single faced card
        if image_uris:
            image_url = (
                image_uris.get("png") or
                image_uris.get("large") or
                image_uris.get("normal")
            )
            img_response = requests.get(image_url, timeout=(2,5))

            img_response.raise_for_status()
            return [Image.open(BytesIO(img_response.content))]

        # Double-faced card — fetch both faces
        card_faces = data.get("card_faces", [])
        if card_faces:
            images = []
            for face in card_faces:
                face_uris = face.get("image_uris", {})
                face_url = (
                    face_uris.get("png") or
                    face_uris.get("large") or
                    face_uris.get("normal")
                )
                if face_url:
                    img_response = requests.get(face_url, timeout=(2,5))
                    img_response.raise_for_status()
                    images.append(Image.open(BytesIO(img_response.content)))
            if images:
                return images

        print(f"  [Scryfall] No image URLs found for '{card_name}'")
        return []

    except Exception as e:
        print(f"  [Scryfall] Failed to fetch '{card_name}': {e}")
        return []

def get_card_images(card_name: str, remote: bool) -> list[Image.Image]:
    """
    Returns a list of PIL Images for the given card name.
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
    scryfall_images = get_scryfall_images(card_name)
    time.sleep(SLEEP_AMOUNT)

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

def build_pdf(deck_list: list[str], remote: bool, output_path: str = "proxies.pdf", progress_var: tk.DoubleVar = None):
    """
    Builds a proxy PDF from a deck list.
    Front pages: 3x3 grid of card fronts.
    Back pages:  matching 3x3 grid of card backs (mirrored horizontally for double-sided printing).
    Cards are separated by a 1mm gap.
    """

    page_width, page_height = letter

    card_w = CARD_WIDTH_MM  * mm
    card_h = CARD_HEIGHT_MM * mm
    gap    = 1 * mm

    grid_width  = CARDS_PER_ROW * card_w + (CARDS_PER_ROW - 1) * gap
    grid_height = CARDS_PER_COL * card_h + (CARDS_PER_COL - 1) * gap
    x_margin = (page_width  - grid_width)  / 2
    y_margin = (page_height - grid_height) / 2

    c = canvas.Canvas(output_path, pagesize=letter)
    total_cards = len(deck_list)
    total_pages = math.ceil(total_cards / CARDS_PER_PAGE)

    print(f"\nBuilding PDF: {total_cards} cards, {total_pages} front page(s) + {total_pages} back page(s)...")

    # Fetch all images upfront so we can build front and back pages together
    all_images = []
    for idx, card_entry in enumerate(deck_list):
        card_name = get_card_name_from_entry(card_entry)
        print(f"[{idx + 1}/{total_cards}] Fetching '{card_name}'...")
        imgs = get_card_images(card_name, remote)

        if not imgs:
            print(f"\n[ERROR] Could not find an image for '{card_name}'. Aborting.")
            raise SystemExit(1)

        all_images.append(imgs)

        # Update progress bar: fetching images = 0-90% of progress
        if progress_var is not None:
            progress_var.set((idx + 1) / total_cards * 90)

    # Build pages in front/back pairs
    for page_num in range(total_pages):
        page_slice = all_images[page_num * CARDS_PER_PAGE : (page_num + 1) * CARDS_PER_PAGE]

        # --- Front page ---
        front_images = [imgs[0] for imgs in page_slice]
        draw_card_grid(c, front_images, page_width, page_height, card_w, card_h, x_margin, y_margin, gap)
        c.showPage()

        # --- Back page ---
        back_images = []
        for row in range(CARDS_PER_COL):
            row_slice = page_slice[row * CARDS_PER_ROW : (row + 1) * CARDS_PER_ROW]
            row_backs = [imgs[1] if len(imgs) > 1 else imgs[0] for imgs in row_slice]
            while len(row_backs) < CARDS_PER_ROW:
                row_backs.append(None)
            back_images.extend(reversed(row_backs))

        draw_card_grid(c, back_images, page_width, page_height, card_w, card_h, x_margin, y_margin, gap)
        c.showPage()

        # Update progress bar: building pages = 90-100% of progress
        if progress_var is not None:
            progress_var.set(90 + (page_num + 1) / total_pages * 10)

    c.save()

    # Set progress to 100% when done
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
        deck_list = read_url(deck_url, land_filter)
    elif from_file:
        deck_list = read_decklist_file(deck_filepath)


    # now that we have the deck list we need to find the pictures and put them into a pdf
    pdf_file_name = "proxies.pdf"
    if args.name is not None:
        pdf_file_name = args.name

    build_pdf(deck_list, remote, pdf_file_name)

def PFGUI():
    disable_local = False
    deck_list = []

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
                deck_list = read_url(url_string, basic_land_filter)
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
                build_pdf(deck_list, disable_local, file_name, progress_var)
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


ProxyField()
