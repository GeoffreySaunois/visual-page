"""The page frame: the top bar's trail and the toolbar it carries."""

from __future__ import annotations

from visualreport.document.controls import toolbar
from visualreport.document.page import breadcrumb


def test_the_trail_names_every_folder_down_to_the_page_by_its_label():
    trail = breadcrumb("swaap/gym/lab")
    labels = [part.split("</span>")[0] for part in trail.split("<span>")[1:]]
    assert labels == ["Swaap", "Gym", "Gym Lab"]
    assert '<a href="index.html">Galerie</a>' in trail


def test_the_diff_toggle_exists_only_when_there_is_a_diff_to_review():
    """A toggle with nothing to toggle would hide nothing and confuse the reader;
    a missing one on an iterated page would leave the diff stuck on screen."""
    assert 'id="diff-toggle"' in toolbar(has_iteration=True)
    assert 'id="diff-toggle"' not in toolbar(has_iteration=False)
    assert 'id="comments-toggle"' in toolbar(has_iteration=False)
