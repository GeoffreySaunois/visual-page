"""Deployment helper refuses account/project drift and applies only saved plans."""

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def invocation(tmp_path):
    tools = tmp_path / "bin"
    tools.mkdir()
    events = tmp_path / "events"
    tool_script = (
        f"#!{sys.executable}\n"
        + """
import json, os, sys
from pathlib import Path
name = Path(sys.argv[0]).name
with open(os.environ['EVENTS'], 'a') as output:
    output.write(json.dumps([name, *sys.argv[1:]]) + '\\n')
if name == 'uv' and 'export' in sys.argv:
    print(Path(os.environ['REQUIREMENTS']).read_text(), end='')
if name == 'gcloud':
    if '--account=owner@example.com' not in sys.argv:
        raise SystemExit(9)
    print('dummy-google-token')
if name == 'terraform' and 'show' in sys.argv:
    print(json.dumps({'variables': {
        'gcp_project_id': {'value': os.environ['PLAN_PROJECT']},
        'terraform_state_bucket_name': {'value': 'test-state'}
    }}))
"""
    )
    for name in ["uv", "gcloud", "terraform"]:
        executable = tools / name
        executable.write_text(tool_script)
        executable.chmod(0o700)
    variables = tmp_path / "test.tfvars.json"
    variables.write_text(
        json.dumps(
            {
                "gcp_project_id": "test-project",
                "terraform_state_bucket_name": "test-state",
            }
        )
    )
    secrets = tmp_path / "test.env"
    secrets.write_text('CLOUDFLARE_API_TOKEN="dummy-cloudflare-token"\n')
    plan = tmp_path / "reviewed.tfplan"
    plan.touch()
    environment = {
        **os.environ,
        "PATH": str(tools) + os.pathsep + os.environ["PATH"],
        "EVENTS": str(events),
        "REQUIREMENTS": str(ROOT / "deploy/gcp/requirements.txt"),
        "PLAN_PROJECT": "test-project",
    }

    def invoke(action, project):
        result = subprocess.run(
            [
                str(ROOT / "deploy/gcp/deploy.sh"),
                action,
                "--account",
                "owner@example.com",
                "--project",
                project,
                "--vars",
                str(variables),
                "--secrets",
                str(secrets),
                "--state-bucket",
                "test-state",
                "--state-prefix",
                "artefacts",
                "--plan",
                str(plan),
            ],
            env=environment,
            check=False,
            capture_output=True,
            text=True,
        )
        calls = (
            [json.loads(line) for line in events.read_text().splitlines()]
            if events.exists()
            else []
        )
        return result, calls

    return invoke, environment


def test_plan_uses_explicit_account_frozen_lock_and_does_not_apply(invocation):
    invoke, _ = invocation
    result, calls = invoke("plan", "test-project")
    assert result.returncode == 0, result.stderr
    assert any(
        call[0] == "gcloud" and "--account=owner@example.com" in call for call in calls
    )
    assert all("--frozen" in call for call in calls if call[0] == "uv")
    assert not any("apply" in call for call in calls)
    assert "dummy-google-token" not in result.stdout + result.stderr
    assert "dummy-cloudflare-token" not in result.stdout + result.stderr


def test_apply_never_replans_and_refuses_plan_for_different_project(invocation):
    invoke, environment = invocation
    environment["PLAN_PROJECT"] = "other-project"
    result, calls = invoke("apply", "test-project")
    assert result.returncode != 0
    assert not any(
        "apply" in call or "plan" in call for call in calls if call[0] == "terraform"
    )


def test_vars_mismatch_is_rejected_before_credentials_or_terraform(invocation):
    invoke, _ = invocation
    result, calls = invoke("plan", "other-project")
    assert result.returncode != 0
    assert not any(call[0] in {"gcloud", "terraform"} for call in calls)
