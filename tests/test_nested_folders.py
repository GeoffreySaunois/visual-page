from dataclasses import replace

from visualreport import folders
from visualreport.gallery.catalog import Entry
from visualreport.gallery.index import ROOT, breadcrumb, children, location, under


def test_nested_folder_is_reachable_without_flattening_its_reports():
    lab = folders.folder("swaap/gym/lab")
    gym = folders.folder("swaap/gym")
    swaap = folders.folder("swaap")
    entry = Entry(
        "report.html", "report-lab", "report", "Lab", "", "", lab, "2026-09-16", 0, 3, 2
    )
    own = replace(entry, folder=gym, document_id="report-optimization")
    entries = [entry, own]
    assert children(ROOT, entries) == [swaap]
    assert children(swaap, entries) == [gym]
    assert children(gym, entries) == [lab]
    assert under(gym, entries) == entries
    assert under(lab, entries) == [entry]
    assert children(lab, entries) == []
    assert 'href="#/swaap/gym"' in breadcrumb(lab)
    assert location(lab) == "Swaap › Gym › Gym Lab"


def test_alias_keeps_its_url_without_duplicating_the_gallery(tmp_path):
    from visualreport.gallery.catalog import collect
    from visualreport.paths import Archive

    page = tmp_path / "report-lab-2026-09-16.html"
    page.write_text('<meta name="report-title" content="Gym Lab" />')
    alias = tmp_path / "agent-workspace.html"
    alias.symlink_to(page.name)
    entries = collect(Archive(tmp_path))
    assert [entry.href for entry in entries] == [page.name]
    assert alias.read_text() == page.read_text()
