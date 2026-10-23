# stolos-bot-instance

Shared runner image and instance definitions for Stolostron agents. This repository is the runner build context; `dev-bot/` is the framework submodule, and `instance/` contains independently deployable agent profiles.

## Build

Run from the repository root:

```bash
git submodule update --init --recursive
podman build -f dev-bot/Dockerfile.runner -t stolos-bot-instance:local .
```

The image includes every `instance/<profile>/` directory. The framework unions the profiles' `envs` selections when installing presets. Optional `instance/<profile>/setup.sh` hooks run as root during the image build; keep the root `setup.sh` generic and put profile-only build dependencies in the corresponding profile hook.

## Add or deploy a profile

Create `instance/<profile>/agent/` with at least `instance.yaml`, `project-repos.json`, and any profile-specific MCP or agent instructions. Set the deployment's `BOT_CONFIG_REPO` to this repository and `BOT_CONFIG_PATH` to `instance/<profile>`; the runner loads configuration from its `agent/` subdirectory. Each profile is deployed independently and gets its own `BOT_INSTANCE_ID`, Jira label, resource name, and schedule.

The included CVE profile is `instance/cve-config/agent/`. It processes Jira CVE tickets using the built-in `jira-sprint` workflow, OpenCode, and the `rehor-openai` provider. Its deployment must set:

| Parameter | CVE profile value |
|---|---|
| `BOT_CONFIG_REPO` | `https://github.com/stolostron/stolos-bot-instance.git` |
| `BOT_CONFIG_PATH` | `instance/cve-config` |
| `BOT_INSTANCE_ID` | `cve-bot-instance` |
| `BOT_EXECUTION_ENGINE` | `coordinator` |
| `BOT_LABEL` | The Jira label assigned to CVE work |
| `BOT_INCLUDE_BACKLOG` | `true` if CVE tickets are not guaranteed to be in the active sprint |

Also supply the image path and digest, and ensure the shared proxy has the Jira MCP and OpenAI-compatible gateway configured for the selected provider/model. See [the onboarding guide](dev-bot/docs/onboarding-new-instance.md) for the surrounding Konflux and app-interface setup.

## Verify the profile and template

```bash
uv run --project dev-bot --extra dev pytest tests/
```

## Update dev-bot

```bash
cd dev-bot && git pull origin master && cd ..
git add dev-bot
git commit -m "chore: update dev-bot submodule"
```
