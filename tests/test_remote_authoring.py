"""Agent authoring must update the hosted discussion, not a stale local file."""

import pytest
from test_hosted import OWNER
from test_hosted import environment as hosted_environment

from visualreport.cli import discussion, remote
from visualreport.cli.main import build_parser
from visualreport.comments import AuthorKind


@pytest.fixture
def environment():
    return hosted_environment.__wrapped__()


def test_cli_reply_keeps_agent_attribution_and_lifecycle(
    environment, monkeypatch, capsys
):
    client, repository, _, issue_token = environment
    token = issue_token(OWNER, {})

    def exchange(origin, credential, path, payload, method):
        response = client.request(
            method,
            path,
            json=payload,
            headers={"Cf-Access-Jwt-Assertion": credential},
        )
        response.raise_for_status()
        return response.json()

    monkeypatch.setattr(remote, "exchange", exchange)
    monkeypatch.setenv("ARTEFACTS_ACCESS_JWT", token)
    parser = build_parser()
    for command in [
        ["comment", "report-demo", "--body", "Question", "--as", "geoffrey"],
        ["reply", "report-demo", "t1", "--body", "Answer"],
        ["edit", "report-demo", "t1.2", "--body", "Corrected answer"],
    ]:
        args = parser.parse_args(command)
        args.handler(args)
    thread = repository.current.threads.require("t1")
    assert thread.comments[1].body == "Corrected answer"
    assert thread.comments[1].author.kind == AuthorKind.AGENT
    assert thread.awaiting == AuthorKind.HUMAN
    discussion.run_list(parser.parse_args(["comments", "report-demo"]))
    assert "Corrected answer" in capsys.readouterr().out
    args = parser.parse_args(["resolve", "report-demo", "t1"])
    args.handler(args)
    assert not repository.current.threads.require("t1").is_open
    args = parser.parse_args(["reopen", "report-demo", "t1"])
    args.handler(args)
    assert repository.current.threads.require("t1").is_open
