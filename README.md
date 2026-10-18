# MinerU_pyclient

Python client and CLI for the [MinerU](https://mineru.net) document parsing
API. It wraps both API families exposed by MinerU:

| | 精准解析 API | Agent 轻量解析 API |
| --- | --- | --- |
| Client | `MinerUClient` | `AgentClient` |
| Base URL | `https://mineru.net/api/v4` | `https://mineru.net/api/v1/agent` |
| Token | required (`Bearer`) | not required |
| Input | single file, batch of files, batch of URLs | single file or URL |
| Output | Zip with Markdown, JSON, plus optional docx/html/latex | Markdown only |
| Limits | <= 200 MB, <= 200 pages | <= 10 MB, <= 20 pages |

## Install

```bash
uv sync
cp .env.example .env   # then set MINERU_TOKEN inside it
```

## Configuration

The precise API needs a token, resolved in this order:

1. the `token` argument of `MinerUClient`,
2. the `MINERU_TOKEN` environment variable,
3. `MINERU_TOKEN` in the nearest `.env` file, searched from the current
   directory upwards.

The agent API needs no token. Real `.env` files are git-ignored; commit only
`.env.example`.

## Library usage

Both clients are asynchronous under the hood (submit, then poll). The
convenience helpers do the whole round trip, including downloading results.

### Precise API

```python
from mineru_pyclient import MinerUClient

# token falls back to $MINERU_TOKEN or .env when omitted
client = MinerUClient("YOUR_TOKEN")

# one URL: submit, wait, download and extract the archive into ./out
path = client.extract_url(
    "https://cdn-mineru.openxlab.org.cn/demo/example.pdf",
    "out",
    model_version="vlm",
    is_ocr=True,
)
print(path)  # out/

# local files are uploaded and parsed as a batch
dirs = client.extract_files(["a.pdf", "b.docx"], "out")

# or drive it manually
task_id = client.create_url_task("https://example.com/file.pdf", page_ranges="1-10")
result = client.wait(task_id, on_progress=lambda r: print(r.state))
```

### Agent API

```python
from mineru_pyclient import AgentClient

client = AgentClient()  # no token needed

result = client.parse_url("https://example.com/file.pdf")  # -> AgentResult
saved = client.parse_file("report.docx", "out")            # -> out/report.md
```

## CLI usage

The console script is installed as `mineru`, and `python -m mineru_pyclient`
works too. Options may be written before or after the command.

```bash
# precise API (needs a token: taken from .env, or exported as shown here)
export MINERU_TOKEN=...
mineru --out-dir out url https://example.com/file.pdf --model-version vlm
mineru file a.pdf b.docx --page-ranges 1-10 --extra-formats docx --extra-formats html

# agent API (no token, Markdown only)
mineru --api agent url https://example.com/file.pdf
mineru url https://example.com/file.pdf --api agent --out-dir out

# submit without waiting, then poll later
mineru url https://example.com/file.pdf --no-wait
mineru status <task_id>
mineru status <batch_id> --batch

# machine-readable output
mineru --json status <task_id>
```

Run `mineru --help` for the full option list.

## Development

```bash
uv sync
uv run pytest
```

The test suite is fully mocked: it injects fake HTTP sessions, so it never
touches the network and needs no token.

## Notes

- Standard API files must be <= 200 MB / <= 200 pages; the agent API is limited
  to 10 MB / 20 pages and one file per request.
- Result archives are extracted with a zip-slip guard.
