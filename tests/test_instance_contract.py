"""Contract checks for the shared runner template and shipped agent profiles."""

import json
import os
import re
import subprocess
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[1]
FRAMEWORK_ROOT = REPO_ROOT / "dev-bot"


def _framework_config():
    import sys

    framework = str(FRAMEWORK_ROOT)
    if framework not in sys.path:
        sys.path.insert(0, framework)
    from bot.config import (
        InstanceConfig,
        load_config,
        load_mcp_servers,
        resolve_active_envs,
        resolve_cycle_model,
        resolve_workflow_dir,
        validate_instance_config,
        validate_manifest,
    )

    return (
        InstanceConfig,
        load_config,
        load_mcp_servers,
        resolve_active_envs,
        resolve_cycle_model,
        resolve_workflow_dir,
        validate_instance_config,
        validate_manifest,
    )


def test_each_profile_loads_and_validates_against_pinned_framework(monkeypatch):
    (
        InstanceConfig,
        load_config,
        load_mcp_servers,
        resolve_active_envs,
        resolve_cycle_model,
        resolve_workflow_dir,
        validate_instance_config,
        validate_manifest,
    ) = _framework_config()

    profiles = sorted((REPO_ROOT / "instance").glob("*/agent/instance.yaml"))
    assert profiles, "at least one deployable instance profile must exist"

    monkeypatch.setenv("BOT_LABEL", "test-cve-label")
    monkeypatch.setenv("BOT_INSTANCE_ID", "test-cve-instance")
    monkeypatch.setenv("BOT_JIRA_EMAIL", "bot@example.invalid")
    monkeypatch.setenv("JIRA_MCP_URL", "http://jira-mcp.invalid/mcp")

    for config_path in profiles:
        agent_dir = config_path.parent
        config = InstanceConfig.from_yaml(config_path)

        validate_instance_config(FRAMEWORK_ROOT, config, agent_dir)
        workflow_dir = resolve_workflow_dir(FRAMEWORK_ROOT, config.workflow, agent_dir)
        assert workflow_dir.is_dir(), f"{config_path}: workflow directory does not exist"

        available_envs = {path.name for path in (FRAMEWORK_ROOT / "presets/envs").iterdir() if path.is_dir()}
        assert set(resolve_active_envs(FRAMEWORK_ROOT, config)) <= available_envs

        project_repos = json.loads((agent_dir / "project-repos.json").read_text())
        assert project_repos, f"{config_path}: no target repositories configured"
        for name, repository in project_repos.items():
            assert repository.get("url", "").startswith(("https://", "ssh://", "git@")), name
            assert repository.get("upstream", "").startswith(("https://", "ssh://", "git@")), name

        mcp_config = json.loads((agent_dir / "mcp.json").read_text())
        assert "mcp-atlassian" in mcp_config.get("mcpServers", {})

        if config.runtime == "opencode":
            assert (agent_dir / "AGENTS.md").is_file(), f"{config_path}: OpenCode needs AGENTS.md"

        mcp_servers = load_mcp_servers(FRAMEWORK_ROOT)
        validate_manifest(FRAMEWORK_ROOT, config.workflow, mcp_servers, agent_dir)
        runtime_config = load_config(FRAMEWORK_ROOT)
        assert resolve_cycle_model(FRAMEWORK_ROOT, config, runtime_config, agent_dir)


def test_cve_profile_is_jira_driven_opencode_and_has_scanners():
    config_path = REPO_ROOT / "instance/cve-config/agent/instance.yaml"
    assert config_path.is_file()
    config = yaml.safe_load(config_path.read_text())

    assert config["workflow"] == "jira-sprint"
    assert config["source"] == "jira"
    assert config["runtime"] == "opencode"
    assert config["provider"] == "rehor-openai"
    assert (config_path.parent / "AGENTS.md").is_file()

    scanner_setup = REPO_ROOT / "instance/cve-config/setup.sh"
    scanner_script = scanner_setup.read_text()
    assert "cmd/govulncheck@v1.1.4" in scanner_script
    assert "pip-audit==2.10.1" in scanner_script


def test_shared_template_is_profile_agnostic_and_forwards_execution_engine():
    template_path = REPO_ROOT / "deploy/template.yaml"
    template_text = template_path.read_text()
    template = yaml.safe_load(template_text)
    params = {item["name"]: item for item in template["parameters"]}
    assert "cve" not in template["metadata"]["name"].lower()
    assert "cve" not in params["BOT_NAME"]["value"].lower()
    assert params["BOT_EXECUTION_ENGINE"]["value"] == "coordinator"

    references = set(re.findall(r"\$\{\{?([A-Z][A-Z0-9_]*)\}\}?", template_text))
    assert references <= params.keys()

    sandbox_template = next(item for item in template["objects"] if item["kind"] == "SandboxTemplate")
    container = sandbox_template["spec"]["podTemplate"]["spec"]["containers"][0]
    env = {item["name"]: item for item in container["env"]}
    assert env["BOT_EXECUTION_ENGINE"]["value"] == "${BOT_EXECUTION_ENGINE}"
    assert [port["port"] for rule in sandbox_template["spec"]["networkPolicy"]["egress"]
            if any(target.get("namespaceSelector", {}).get("matchLabels", {}).get("kubernetes.io/metadata.name") == "openshift-dns"
                   for target in rule["to"])
            for port in rule["ports"]] == [5353, 5353]

    assert "cve-bot-instance" not in (REPO_ROOT / "setup.sh").read_text()


def test_root_setup_runs_profile_hooks_from_selected_build_context(tmp_path):
    profile_hook = tmp_path / "instance/demo/setup.sh"
    profile_hook.parent.mkdir(parents=True)
    profile_hook.write_text('printf "profile-hook-ran\\n" > "$APP_DIR/hook-result"\n')

    env = os.environ.copy()
    env["APP_DIR"] = str(tmp_path)
    result = subprocess.run(
        ["bash", str(REPO_ROOT / "setup.sh")],
        check=True,
        capture_output=True,
        text=True,
        env=env,
    )
    assert (tmp_path / "hook-result").read_text() == "profile-hook-ran\n"
    assert "Runner image setup complete" in result.stdout


def test_yaml_json_and_shell_files_are_well_formed():
    for path in (REPO_ROOT / "deploy").glob("*.yaml"):
        yaml.safe_load(path.read_text())
    for path in (REPO_ROOT / "instance").rglob("*.yaml"):
        yaml.safe_load(path.read_text())
    for path in (REPO_ROOT / "instance").rglob("*.json"):
        json.loads(path.read_text())

    for path in [REPO_ROOT / "setup.sh", *REPO_ROOT.glob("instance/*/setup.sh")]:
        subprocess.run(["bash", "-n", str(path)], check=True)
