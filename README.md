# MUSE

MUSE provides skill packages for original fiction, serial fiction, literary analysis,
and the extraction of reusable writing references. Start with the
[skills collection](skills/README.md) for package descriptions and usage.

```text
MUSE/
├── skills/                 # Writing and literary analysis packages
├── src/open_muse/          # Python agent loop and eight-phase writing runner
├── tests/                  # Runtime and writing-script tests
├── config.example.yaml    # Provider configuration using an environment variable
├── requirements.txt       # Python runtime dependencies
└── requirements-dev.txt   # Test dependencies
```

The skill packages contain their own instructions, scripts, and dependency files.
Their package-level READMEs describe the supported writing workflows.

## Python runner

Use Python 3.10 or newer. Run the following commands from the repository root:

```bash
python3 -m venv .venv
source .venv/bin/activate
python3 -m pip install -r requirements.txt
cp config.example.yaml config.yaml
```

Edit `config.yaml` to select your OpenAI-compatible endpoint and model. Set
`MUSE_API_KEY` in your shell or local `.env` file. The configuration reads the key
from this environment variable.

```bash
PYTHONPATH=src python3 -m open_muse.main \
  --config config.yaml \
  "Write a short mystery set in an old observatory."
```

The Python runner loads the eight `phase0` through `phase7` skills in
`skills/MUSE-writing/skills/`. Requests use the configured model provider.
Generated text and event logs are written under `results/`.

## Tests

```bash
python3 -m pip install -r requirements-dev.txt
python3 -m pytest
```

The tests use local fixtures and mocks and do not require API credentials.
