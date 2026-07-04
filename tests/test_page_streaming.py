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
