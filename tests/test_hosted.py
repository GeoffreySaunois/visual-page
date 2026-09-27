"""Hosted regressions: forged identity, cross-report reads and unauthorized writes."""

import time
from types import SimpleNamespace

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi import HTTPException
from fastapi.testclient import TestClient

from visualreport.comments import AuthorKind, ReportThreads
from visualreport.hosted.app import create_app
from visualreport.hosted.comments import CommentAction
from visualreport.hosted.grants import NO_GRANTS, Role
from visualreport.hosted.identity import AccessIdentity
from visualreport.hosted.reports import Report
from visualreport.hosted.service import ReportService

ISSUER = "https://example.cloudflareaccess.com"
AUDIENCE = "report-audience"
SOURCE = "---\ntitle: Demo\neyebrow: Test\nsubtitle: Demo\nfolder: personal/tooling\nslug: demo\n---\n\n## Heading\n\nSource body."

OWNER = "owner@example.com"
ALICE = "alice@example.com"
BOB = "bob@example.com"


class MemoryReports:
    def __init__(self, report):
        self.current = report
        self.before_mutation = lambda: None

    def read(self, document_id):
        if document_id != self.current.document_id:
            raise HTTPException(404)
        return self.current.model_copy(deep=True)

    def visible(self, email, administrator, folders):
        if (
            administrator
            or email == self.current.owner
            or email in self.current.grants
            or self.current.everyone is not None
            or self.current.folder in folders
        ):
            return [self.current.model_copy(deep=True)]
        return []

    def archive(self, path):
        raise HTTPException(404)

    def gallery(self, email, administrator, folders):
        return self.visible(email, administrator, folders)

    def history(self, document_id):
        return [self.read(document_id)]

    def page(self, page_name):
        if page_name != self.current.page_name:
            raise HTTPException(404)
        return self.current.model_copy(deep=True)

    def version(self, document_id, page_name):
        return self.page(page_name)

    def mutate(self, document_id, change, version):
        self.before_mutation()
        updated = change(self.read(document_id))
        self.current = updated.model_copy(deep=True)
        return updated


class MemoryFolderShares:
    def __init__(self):
        self.grants = {}

    def all(self):
        return dict(self.grants)

    def share(self, folder, grantee, role):
        current = self.grants.get(folder, NO_GRANTS)
        self.grants[folder] = current.granting(grantee, role)
        return self.grants[folder]


class MemoryObjects:
    def read(self, key):
        return (
            '<html>private report<script id="vr-bootstrap" type="application/json">{"threads":["stale secret"]}</script></html>'
            if key == "page"
            else SOURCE
        )


@pytest.fixture
def environment():
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    keys = SimpleNamespace(
        get_signing_key_from_jwt=lambda _: SimpleNamespace(key=private_key.public_key())
    )
    identity = AccessIdentity(ISSUER, AUDIENCE, keys)
    report = Report(
        document_id="report-demo",
        title="Private title",
        eyebrow="Test",
        subtitle="Demo",
        folder="personal/tooling",
        date="2026-09-21",
        owner=OWNER,
        grants={ALICE: Role.COMMENTER},
        everyone=None,
        page_name="report-demo-2026-09-21.html",
        html_key="page",
        source_key="source",
        threads=ReportThreads.empty("report-demo"),
        revision=1,
    )
    repository = MemoryReports(report)
    service = ReportService(repository, MemoryObjects(), MemoryFolderShares(), {OWNER})
    client = TestClient(create_app(service, identity, "https://artefacts.saunois.xyz"))

    def token(email, changes):
        claims = {
            "iss": ISSUER,
            "aud": AUDIENCE,
            "sub": email,
            "email": email,
            "exp": int(time.time()) + 300,
            "iat": int(time.time()),
            "type": "app",
        }
        claims.update(changes)
        return jwt.encode(claims, private_key, algorithm="RS256")

    return client, repository, service, token


def headers(token, email):
    return {"Cf-Access-Jwt-Assertion": token(email, {})}


@pytest.mark.parametrize(
    "claims",
    [
        {"aud": "another-app"},
        {"iss": "https://evil.example"},
        {"exp": 1},
        {"type": "service"},
        {"email": None},
    ],
)
def test_rejects_wrong_or_expired_access_identity(environment, claims):
    client, _, _, token = environment
    response = client.get(
        "/reports/report-demo",
        headers={"Cf-Access-Jwt-Assertion": token(ALICE, claims)},
    )
    assert response.status_code == 401
    assert "private report" not in response.text


def test_unverified_headers_and_forged_signatures_do_not_grant_access(environment):
    client, _, _, token = environment
    assert (
        client.get(
            "/", headers={"Cf-Access-Authenticated-User-Email": OWNER}
        ).status_code
        == 401
    )
    forged = jwt.encode(
        {"email": OWNER}, "attacker-secret-is-not-a-signing-key", algorithm="HS256"
    )
    assert (
        client.get("/", headers={"Cf-Access-Jwt-Assertion": forged}).status_code == 401
    )
    assert (
        client.get("/reports/report-demo", headers=headers(token, OWNER)).status_code
        == 200
    )


def test_unshared_report_is_absent_from_gallery_and_every_read_route(environment):
    client, _, _, token = environment
    bob = headers(token, BOB)
    for path in [
        "/reports/report-demo",
        "/report-demo-2026-09-21.html",
        "/api/documents/report-demo/threads",
    ]:
        assert client.get(path, headers=bob).status_code == 404
    assert "Private title" not in client.get("/", headers=bob).text
    assert client.get("/api/documents", headers=bob).json()["documents"] == []
    assert client.get("/source.md", headers=headers(token, OWNER)).status_code == 404


def test_reader_cannot_write_and_revocation_affects_existing_session(environment):
    client, repository, _, token = environment
    repository.current.grants[ALICE] = Role.READER
    alice = headers(token, ALICE)
    assert (
        client.post(
            "/api/documents/report-demo/threads",
            headers=alice,
            json={"body": "hello", "anchor": None},
        ).status_code
        == 403
    )
    assert client.get("/reports/report-demo", headers=alice).status_code == 200
    repository.current.grants.pop(ALICE)
    assert client.get("/reports/report-demo", headers=alice).status_code == 404
    assert repository.current.threads.threads == []


def test_comment_author_cannot_be_spoofed_and_other_commenter_cannot_edit(environment):
    client, repository, _, token = environment
    alice, bob = headers(token, ALICE), headers(token, BOB)
    path = "/api/documents/report-demo/threads"
    created = client.post(
        path, headers=alice, json={"body": "Alice's text", "anchor": None}
    )
    assert created.status_code == 200
    assert created.json()["threads"][0]["comments"][0]["author"]["name"] == ALICE
    repository.current.grants[BOB] = Role.COMMENTER
    edit = f"{path}/t1/comments/t1.1"
    assert (
        client.patch(edit, headers=bob, json={"body": "overwritten"}).status_code == 403
    )
    assert repository.current.threads.require("t1").comments[0].body == "Alice's text"
    assert (
        client.patch(edit, headers=alice, json={"body": "corrected"}).status_code == 200
    )
    assert repository.current.threads.require("t1").comments[0].body == "corrected"


def test_access_is_rechecked_inside_transaction(environment):
    _, repository, service, _ = environment
    repository.before_mutation = lambda: repository.current.grants.pop(ALICE)
    with pytest.raises(HTTPException) as error:
        service.comment(
            "report-demo",
            ALICE,
            CommentAction("create", None, None, "hello", None, AuthorKind.HUMAN),
        )
    assert error.value.status_code == 404
    assert repository.current.threads.threads == []


def test_only_owner_can_share_and_cross_origin_mutations_are_blocked(environment):
    client, repository, _, token = environment
    path = "/api/documents/report-demo/shares"
    assert (
        client.put(
            path, headers=headers(token, ALICE), json={"email": BOB, "role": "reader"}
        ).status_code
        == 403
    )
    owner = headers(token, OWNER)
    assert (
        client.put(
            path,
            headers={**owner, "Origin": "https://evil.example"},
            json={"email": BOB, "role": "reader"},
        ).status_code
        == 403
    )
    assert BOB not in repository.current.grants
    assert (
        client.put(
            path, headers=owner, json={"email": BOB, "role": "reader"}
        ).status_code
        == 200
    )
    assert (
        client.get("/reports/report-demo", headers=headers(token, BOB)).status_code
        == 200
    )


def test_page_uses_current_comments_and_does_not_allow_private_cache(environment):
    client, _, _, token = environment
    response = client.get("/reports/report-demo", headers=headers(token, ALICE))
    assert "stale secret" not in response.text
    assert "no-store" in response.headers["cache-control"]


def test_publication_is_owner_only_and_republication_preserves_grants_and_discussion(
    environment,
):
    from visualreport.hosted.publication import Publication, publish

    _, repository, service, _ = environment
    service.comment(
        "report-demo",
        ALICE,
        CommentAction("create", None, None, "keep me", None, AuthorKind.HUMAN),
    )
    publication = Publication(
        page_name="report-demo-2026-09-22.html",
        title="New version",
        html="<html>report-demo</html>",
        source=SOURCE,
    )
    objects = SimpleNamespace(upload=lambda *args: ("new-page", "new-source"))
    with pytest.raises(HTTPException) as error:
        publish(repository, objects, publication, ALICE, {OWNER})
    assert error.value.status_code == 403
    updated = publish(repository, objects, publication, OWNER, {OWNER})
    assert updated.threads.require("t1").comments[0].body == "keep me"
    assert updated.grants[ALICE] == Role.COMMENTER
    assert updated.source_key == "new-source"


def test_anchored_comment_rejected_if_report_changes_before_transaction(environment):
    _, repository, service, _ = environment
    repository.before_mutation = lambda: setattr(
        repository.current, "source_key", "new-source"
    )
    anchor = {"block_index": 1, "quote": "Source body", "prefix": "", "suffix": ""}
    with pytest.raises(HTTPException) as error:
        service.comment(
            "report-demo",
            ALICE,
            CommentAction("create", None, None, "hello", anchor, AuthorKind.HUMAN),
        )
    assert error.value.status_code == 409
    assert repository.current.threads.threads == []


def share_folder(client, token, email, folder, recipient, role):
    return client.put(
        f"/api/folders/{folder}/shares",
        headers=headers(token, email),
        json={"email": recipient, "role": role},
    )


@pytest.mark.parametrize(
    ("granted", "opens"),
    [
        ("personal/tooling", True),
        ("personal", True),
        ("personal/azul", False),
        ("swaap", False),
    ],
)
def test_folder_grant_opens_reports_in_that_folder_and_below_only(
    environment, granted, opens
):
    client, _, _, token = environment
    assert share_folder(client, token, OWNER, granted, BOB, "reader").status_code == 200
    bob = headers(token, BOB)
    assert (client.get("/reports/report-demo", headers=bob).status_code == 200) is opens
    assert ("Private title" in client.get("/", headers=bob).text) is opens
    listed = client.get("/api/documents", headers=bob).json()["documents"]
    assert bool(listed) is opens


def test_folder_revocation_closes_reports_opened_by_the_folder(environment):
    client, _, _, token = environment
    share_folder(client, token, OWNER, "personal/tooling", BOB, "reader")
    share_folder(client, token, OWNER, "personal/tooling", BOB, None)
    assert (
        client.get("/reports/report-demo", headers=headers(token, BOB)).status_code
        == 404
    )


def test_effective_role_is_the_strongest_of_report_and_folder_grants(environment):
    client, repository, _, token = environment
    path = "/api/documents/report-demo/threads"
    comment = {"body": "hello", "anchor": None}
    bob = headers(token, BOB)
    share_folder(client, token, OWNER, "personal", BOB, "reader")
    assert client.post(path, headers=bob, json=comment).status_code == 403
    repository.current.grants[ALICE] = Role.READER
    share_folder(client, token, OWNER, "personal/tooling", ALICE, "commenter")
    assert (
        client.post(path, headers=headers(token, ALICE), json=comment).status_code
        == 200
    )


def test_only_the_archive_owner_shares_folders_and_only_real_ones(environment):
    client, _, service, token = environment
    assert (
        share_folder(
            client, token, ALICE, "personal/tooling", BOB, "reader"
        ).status_code
        == 403
    )
    assert (
        share_folder(
            client, token, OWNER, "personal/nowhere", BOB, "reader"
        ).status_code
        == 404
    )
    assert service.folder_shares.all() == {}


def share_everyone(client, token, email, target, role):
    return client.put(
        f"/api/{target}/shares",
        headers=headers(token, email),
        json={"everyone": True, "role": role},
    )


DOCUMENT = "documents/report-demo"
COMMENT = {"body": "hello", "anchor": None}
THREADS = "/api/documents/report-demo/threads"


@pytest.mark.parametrize("target", [DOCUMENT, "folders/personal"])
def test_everyone_grant_opens_the_report_to_any_verified_email(environment, target):
    client, _, _, token = environment
    assert share_everyone(client, token, OWNER, target, "reader").status_code == 200
    stranger = headers(token, "stranger@elsewhere.org")
    assert client.get("/reports/report-demo", headers=stranger).status_code == 200
    assert client.get(THREADS, headers=stranger).status_code == 200
    assert "Private title" in client.get("/", headers=stranger).text
    assert client.get("/api/documents", headers=stranger).json()["documents"]
    assert client.post(THREADS, headers=stranger, json=COMMENT).status_code == 403


@pytest.mark.parametrize("target", [DOCUMENT, "folders/personal"])
def test_everyone_grant_never_admits_an_unauthenticated_request(environment, target):
    client, _, _, token = environment
    share_everyone(client, token, OWNER, target, "commenter")
    expired = {"Cf-Access-Jwt-Assertion": token(BOB, {"exp": 1})}
    for request_headers in [{}, expired]:
        for path in [
            "/",
            "/reports/report-demo",
            "/report-demo-2026-09-21.html",
            THREADS,
        ]:
            response = client.get(path, headers=request_headers)
            assert response.status_code == 401
            assert "Private title" not in response.text
        assert (
            client.post(THREADS, headers=request_headers, json=COMMENT).status_code
            == 401
        )


def test_effective_role_is_the_strongest_across_everyone_email_and_folder_grants(
    environment,
):
    client, repository, _, token = environment
    repository.current.grants[ALICE] = Role.READER
    share_everyone(client, token, OWNER, DOCUMENT, "reader")
    alice, bob = headers(token, ALICE), headers(token, BOB)
    assert client.post(THREADS, headers=alice, json=COMMENT).status_code == 403
    share_everyone(client, token, OWNER, "folders/personal/tooling", "commenter")
    assert client.post(THREADS, headers=alice, json=COMMENT).status_code == 200
    assert client.post(THREADS, headers=bob, json=COMMENT).status_code == 200
    share_everyone(client, token, OWNER, "folders/personal/tooling", None)
    repository.current.grants[BOB] = Role.COMMENTER
    assert client.post(THREADS, headers=bob, json=COMMENT).status_code == 200
    assert client.post(THREADS, headers=alice, json=COMMENT).status_code == 403


def test_revoking_everyone_closes_strangers_but_keeps_email_grants(environment):
    client, repository, _, token = environment
    share_everyone(client, token, OWNER, DOCUMENT, "reader")
    share_everyone(client, token, OWNER, DOCUMENT, None)
    bob = headers(token, BOB)
    assert client.get("/reports/report-demo", headers=bob).status_code == 404
    assert "Private title" not in client.get("/", headers=bob).text
    assert repository.current.grants == {ALICE: Role.COMMENTER}
    assert (
        client.get("/reports/report-demo", headers=headers(token, ALICE)).status_code
        == 200
    )


@pytest.mark.parametrize("target", [DOCUMENT, "folders/personal"])
def test_only_the_owner_opens_to_everyone_and_an_everyone_grantee_cannot_reshare(
    environment, target
):
    client, repository, service, token = environment
    assert share_everyone(client, token, ALICE, target, "reader").status_code == 403
    assert repository.current.everyone is None
    assert service.folder_shares.all() == {}
    share_everyone(client, token, OWNER, target, "commenter")
    bob = headers(token, BOB)
    assert share_everyone(client, token, BOB, target, None).status_code == 403
    assert (
        client.post(
            THREADS, headers=bob, json={**COMMENT, "actor": "agent"}
        ).status_code
        == 403
    )
    assert client.get("/api/shares", headers=bob).status_code == 403


@pytest.mark.parametrize(
    "body",
    [
        {"email": BOB, "everyone": True, "role": "reader"},
        {"role": "reader"},
        {"email": "*", "role": "reader"},
        {"email": "everyone", "role": "reader"},
    ],
)
def test_a_share_names_exactly_one_real_grantee(environment, body):
    client, repository, _, token = environment
    response = client.put(
        f"/api/{DOCUMENT}/shares", headers=headers(token, OWNER), json=body
    )
    assert response.status_code == 422
    assert repository.current.everyone is None
    assert repository.current.grants == {ALICE: Role.COMMENTER}


def test_shares_lists_everyone_grants_apart_from_email_grants(environment):
    client, _, _, token = environment
    share_everyone(client, token, OWNER, DOCUMENT, "reader")
    share_everyone(client, token, OWNER, "folders/personal", "commenter")
    listed = client.get("/api/shares", headers=headers(token, OWNER)).json()
    assert listed["documents"]["report-demo"] == {
        "emails": {ALICE: "commenter"},
        "everyone": "reader",
    }
    assert listed["folders"]["personal"] == {"emails": {}, "everyone": "commenter"}


def test_republication_keeps_the_everyone_grant(environment):
    # A republished report is rebuilt from scratch: dropping `everyone` there
    # would silently close a report the owner opened to every verified email.
    from visualreport.hosted.publication import Publication, publish

    client, repository, _, token = environment
    share_everyone(client, token, OWNER, DOCUMENT, "reader")
    publication = Publication(
        page_name="report-demo-2026-09-22.html",
        title="New version",
        html="<html>report-demo</html>",
        source=SOURCE,
    )
    objects = SimpleNamespace(upload=lambda *args: ("new-page", "new-source"))
    assert (
        publish(repository, objects, publication, OWNER, {OWNER}).everyone
        == Role.READER
    )
