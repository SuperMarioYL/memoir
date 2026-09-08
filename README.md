[简体中文](./README.zh-CN.md) · [Website](https://memoir.lei6393.com) · [GitHub](https://github.com/SuperMarioYL/memoir)

<picture>
  <source media="(max-width: 600px) and (prefers-color-scheme: dark)" srcset="./assets/presentation/hero-mobile-dark.svg">
  <source media="(max-width: 600px)" srcset="./assets/presentation/hero-mobile-light.svg">
  <source media="(prefers-color-scheme: dark)" srcset="./assets/presentation/hero-dark.svg">
  <img src="./assets/presentation/hero-light.svg" width="960" alt="Hero diagram">
</picture>

# memoir

**Give your notes a stable place in every conversation.**

Memoir reads local text notes, assembles a deterministic prefix, and can send that prefix with conversation turns to a configured DeepSeek-compatible endpoint.

## Why use it

A personal note collection is difficult to reuse if every session assembles it differently. Keep one ordered prefix and a source manifest so you can inspect what will be supplied to the model.

- **Inspect all source notes** — The manifest records the assembled sources.
- **Deterministic prefix** — Input traversal order does not change assembled bytes.
- **Local preparation** — Ingestion and prefix assembly need no chat request.

## Architecture

<picture>
  <source media="(max-width: 600px) and (prefers-color-scheme: dark)" srcset="./assets/presentation/architecture-mobile-dark.svg">
  <source media="(max-width: 600px)" srcset="./assets/presentation/architecture-mobile-light.svg">
  <source media="(prefers-color-scheme: dark)" srcset="./assets/presentation/architecture-dark.svg">
  <img src="./assets/presentation/architecture-light.svg" width="960" alt="Architecture diagram">
</picture>

ingest walks supported note files and hashes their content. prefix sorts sources by relative path and content hash, assembles stable framing, and records a manifest. session stores conversation turns; deepseek_client sends the full prefix and turns when chat is used.

| Component | Responsibility |
| --- | --- |
| `Note ingestion` | memoir/ingest.py |
| `Stable prefix` | memoir/prefix.py |
| `Session state` | memoir/session.py |
| `Chat client` | memoir/deepseek_client.py |

## Install and quickstart

Build with the version declared in the repository manifest. Run the example from the repository root.

```bash
git clone https://github.com/SuperMarioYL/memoir.git
cd memoir
uv venv .venv
uv pip install --python .venv/bin/python -e .
source .venv/bin/activate
```

Assemble only the four shipped example notes, reverse their input order and compare the resulting prefix bytes.

```bash
.venv/bin/python examples/presentation-demo.py
```

## Recorded demo

<picture>
  <source media="(max-width: 600px) and (prefers-color-scheme: dark)" srcset="./assets/presentation/process-mobile-dark.svg">
  <source media="(max-width: 600px)" srcset="./assets/presentation/process-mobile-light.svg">
  <source media="(prefers-color-scheme: dark)" srcset="./assets/presentation/process-dark.svg">
  <img src="./assets/presentation/process-light.svg" width="960" alt="Process diagram">
</picture>

The two assemblies produce identical prefix bytes and the same content hash.

```text
{
  "sources": 4,
  "ordered_paths": [
    "2024-goals.md",
    "decision-deepseek.md",
    "reading-list.md",
    "training.txt"
  ],
  "prefix_hash": "7dfc31cffa444112",
  "same_bytes_after_input_reversal": true,
  "cache_stable": true
}
```

The complete command and output are recorded in [docs/demo-results.json](./docs/demo-results.json). Inputs and reproduction code are included in the repository.

## Usage

The CLI exposes the following operations. Commands after the example use your own paths or identifiers.

```bash
memoir ingest examples/notes
memoir status
# Online chat requires your configured endpoint and API key:
memoir chat
```

## Configuration

MEMOIR_HOME selects prefix.txt, manifest.yaml and session.json storage. DEEPSEEK_API_KEY enables chat; DEEPSEEK_MODEL and DEEPSEEK_BASE_URL select the online model and endpoint. The cost command uses the repository pricing snapshot, which may differ from current provider billing.

## Integrations and responsibilities

<picture>
  <source media="(max-width: 600px) and (prefers-color-scheme: dark)" srcset="./assets/presentation/integrations-mobile-dark.svg">
  <source media="(max-width: 600px)" srcset="./assets/presentation/integrations-mobile-light.svg">
  <source media="(prefers-color-scheme: dark)" srcset="./assets/presentation/integrations-dark.svg">
  <img src="./assets/presentation/integrations-light.svg" width="960" alt="Integrations diagram">
</picture>

The following routes are implemented in the source. Choose the input that matches your task and keep the resulting artifact with your project.

| Route | Implemented role |
| --- | --- |
| Markdown / text | Local source notes |
| Prefix + manifest | Deterministic assembled input |
| DeepSeek HTTP | Configured online chat route |
| Session JSON | Saved conversation turns |

## Limits and next steps

- Stable bytes do not guarantee a provider cache hit or a particular cost. The demo makes no API call.
- Online chat sends the full ingested note content to the configured endpoint. Review the source folder before using chat.
- Token counts are estimates and full-prefix chat remains bounded by the selected model context window.

Provider cache behavior, large-note context limits and recall quality need separate live evaluation. No measured savings or unlimited recall is claimed here.

## License and contributions

See [LICENSE](./LICENSE). When reporting an issue, include a minimal input, the command, and the observed output.
