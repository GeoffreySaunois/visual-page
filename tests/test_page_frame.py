"""The page frame: the top bar's trail and the toolbar it carries."""

from __future__ import annotations

import re

from visualreport.document.controls import toolbar
from visualreport.document.page import back_to_folder, breadcrumb


def test_every_segment_of_the_trail_opens_its_folder_in_the_gallery():
    trail = breadcrumb("swaap/gym/lab")
    links = re.findall(r'<a href="([^"]*)">([^<]*)</a>', trail)
    assert links == [
        ("index.html", "Galerie"),
        ("index.html#/swaap", "Swaap"),
        ("index.html#/swaap/gym", "Gym"),
        ("index.html#/swaap/gym/lab", "Gym Lab"),
    ]


def test_the_back_arrow_returns_to_the_page_folder_not_the_gallery_root():
    assert 'href="index.html#/swaap/gym/lab"' in back_to_folder("swaap/gym/lab")
    # A page filed nowhere has no folder to return to: the gallery root it is.
    assert 'href="index.html"' in back_to_folder("")


def test_the_diff_toggle_exists_only_when_there_is_a_diff_to_review():
    """A toggle with nothing to toggle would hide nothing and confuse the reader;
    a missing one on an iterated page would leave the diff stuck on screen."""
    assert 'id="diff-toggle"' in toolbar(has_iteration=True)
    assert 'id="diff-toggle"' not in toolbar(has_iteration=False)
    assert 'id="comments-toggle"' in toolbar(has_iteration=False)
