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
