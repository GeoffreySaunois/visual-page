"""Hosted regressions: forged identity, cross-report reads and unauthorized writes."""

import time
from types import SimpleNamespace

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi import HTTPException
from fastapi.testclient import TestClient

from visualreport.comments import ReportThreads
from visualreport.hosted.app import create_app
from visualreport.hosted.comments import CommentAction
from visualreport.hosted.identity import AccessIdentity
from visualreport.hosted.reports import Report, Role
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

    def visible(self, email, administrator):
        if administrator or email == self.current.owner or email in self.current.grants:
            return [self.current.model_copy(deep=True)]
        return []

    def mutate(self, document_id, change):
        self.before_mutation()
        updated = change(self.read(document_id))
        self.current = updated.model_copy(deep=True)
        return updated


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
        owner=OWNER,
        grants={ALICE: Role.COMMENTER},
        page_name="report-demo-2026-09-21.html",
        html_key="page",
        source_key="source",
        threads=ReportThreads.empty("report-demo"),
        revision=1,
    )
    repository = MemoryReports(report)
    service = ReportService(repository, MemoryObjects(), {OWNER})
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
            "report-demo", ALICE, CommentAction("create", None, None, "hello", None)
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
        "report-demo", ALICE, CommentAction("create", None, None, "keep me", None)
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
            "report-demo", ALICE, CommentAction("create", None, None, "hello", anchor)
        )
    assert error.value.status_code == 409
    assert repository.current.threads.threads == []
