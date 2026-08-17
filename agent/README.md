# Work IQ Orchestrator Agent

A small Microsoft Agent Framework app that:

1. Talks to your **Azure AI Foundry** deployment via the OpenAI-compatible
   `/openai/v1` endpoint, authenticated with `DefaultAzureCredential` (no
   API keys — uses your `az login` / Managed Identity / VS Code session).
2. Wires the local **Work IQ simulator** in as a tool surface over **both**
   transports:
   - **MCP (stdio)** — spawns `simulator/server.py` as a child process.
     Exposes the low-level tools `ask_work_iq`, `fetch`, `create_entity`,
     `update_entity`.
   - **A2A (HTTP)** — talks to `simulator/a2a_server.py` as a remote sub-agent
     for chat-style grounded answers.
3. Lets the model decide per turn which transport to use.

The same wiring will work against the **real** Work IQ later — only the
endpoint changes.

---

## Setup

```powershell
# 1) Python packages (Windows ARM64: --only-binary uses prebuilt wheels)
.\.venv\Scripts\python.exe -m pip install --only-binary=:all: -r agent\requirements.txt

# 2) Sign in for Entra ID auth
az login
```

## Configure

```powershell
$env:AZURE_AI_FOUNDRY_ENDPOINT   = "https://<your-resource>.services.ai.azure.com/openai/v1"
$env:AZURE_AI_FOUNDRY_DEPLOYMENT = "gpt-4o-mini"     # your deployment name
$env:WORKIQ_SIM_PERSONA          = "quality_pm"      # ops_director | quality_pm | credentialing_lead | vendor_liaison
```

## Run

In **terminal A** — start the A2A side of the simulator (the MCP side is
launched automatically by the agent):
```powershell
.\.venv\Scripts\python.exe simulator\a2a_server.py
```

In **terminal B** — run the agent:
```powershell
# one-shot
.\.venv\Scripts\python.exe agent\workiq_agent.py --ask "Prep me for the Joint Commission readiness review."

# interactive REPL
.\.venv\Scripts\python.exe agent\workiq_agent.py
```

## Deterministic hero demo (no LLM / no Foundry needed)

For a presentation-safe walkthrough that never stalls on the live model, run the
scripted demo. It drives the **same Work IQ engine** directly and proves all four
capability domains in order — Context+Chat (the Joint Commission brief), Governance
(RBAC across personas), and Tools (escalating every past-due quality CAPA):

```powershell
.\.venv\Scripts\python.exe agent\hero_demo.py            # full walkthrough
.\.venv\Scripts\python.exe agent\hero_demo.py --no-color # plain output (logs/CI)
```

It exits non-zero if any act misbehaves, so it doubles as a smoke test of the demo path.

## Things to try

| Prompt | Watch for |
|---|---|
| `what did the quality steering committee decide about the medication-reconciliation policy?` | A2A surface used; citations like `MTG-001` |
| `fetch every capa_tracker row whose committee is quality_steering and status is Open` | MCP `fetch` called |
| `for every open corrective action from the quality committee, update its status in the tracker and flag the ones past due` | A2A then MCP `update_entity` — CAPA-001 & CAPA-004 escalated |
| Re-run a question after `$env:WORKIQ_SIM_PERSONA="vendor_liaison"` | RBAC kicks in — answer fails closed, governance note surfaced |

## Notes / troubleshooting

- **Auth fails** — make sure `az login` was successful and your account has
  Cognitive Services User on the Foundry resource.
- **A2AAgent / OpenAIChatClient import errors** — the exact import path
  depends on your installed `agent-framework` version. On older builds try
  `from agent_framework_a2a import A2AAgent` and check the changelog.
- **MCP subprocess won't start** — the script uses `.\.venv\Scripts\python.exe`
  by default; edit `VENV_PY` in `workiq_agent.py` if your venv lives elsewhere.
