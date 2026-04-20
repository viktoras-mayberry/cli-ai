# MAYAI Architecture — Research-First Roadmap

This document sketches how MAYAI evolves from "multi-provider AI CLI" into "CLI-native research assistant" without a rewrite. It describes the target shape of the system, the new modules needed, and where each piece slots into what already exists.

Scope: architectural direction and module boundaries. Not an implementation schedule.

## Design principles

1. **Local-first.** Any research feature must be usable with Ollama and zero cloud calls. Cloud providers are an optional accelerator, never a requirement.
2. **Citations are first-class.** Every research answer is either grounded in a retrievable source (URL, file path + page, corpus chunk ID) or it says "no source" explicitly. A research tool that might be hallucinating is worse than no tool.
3. **Nothing new that the plugin system could do.** Extractors, embedders, and retrievers are plugins. This keeps the core small and gives users a way to add niche formats without a PR.
4. **Composable via pipes.** Every research command has a `--json` output mode. Output from one command feeds the next. This is the CLI's structural advantage over web UIs — don't waste it.
5. **Unique, not competitive.** The goal is distinctive usefulness, not feature parity with Elicit or NotebookLM. Skip features whose only justification is "they have it."

## Current state (what exists today)

- `providers/` — 6 providers behind a shared `stream_chat` interface. Perplexity exposes `last_citations`.
- `research.py` — thin Perplexity wrapper. Returns (answer, citations).
- `compare.py` — runs a prompt against multiple providers.
- `finder.py` — filesystem search (name/type/date + optional content index).
- `extractor.py` — PDF/DOCX/XLSX/text reading. Already used by `/open`.
- `plugins.py` — entry-point discovery for `mayai.providers` and `mayai.tools`.
- `history.py` — SQLite log of every exchange.
- `sessions.py` — JSON session persistence.

The research pillar is the thinnest. Everything else is either adequate or adjacent.

## Target shape — the corpus pipeline

The central missing capability: **query my own documents with any model, get cited answers.** This is what NotebookLM and Elicit do in a web UI. Doing it in a CLI with local models is the wedge.

```
                         ┌────────────────────────┐
                         │  mayai corpus build    │
                         │  ~/papers              │
                         └──────────┬─────────────┘
                                    │
              ┌─────────────────────┼─────────────────────┐
              ▼                     ▼                     ▼
       ┌────────────┐        ┌────────────┐       ┌────────────┐
       │ extractor  │───►    │  chunker   │──►    │  embedder  │
       │ (exists)   │        │   (new)    │       │   (new)    │
       └────────────┘        └────────────┘       └─────┬──────┘
                                                        │
                                                        ▼
                                                ┌───────────────┐
                                                │  corpus store │
                                                │  SQLite +     │
                                                │  vector col   │
                                                └───────┬───────┘
                                                        │
┌───────────────────┐    retrieve top-k chunks          │
│ mayai research    │◄──────────────────────────────────┘
│ --corpus ~/papers │
│ "question"        │──►  any provider (Ollama/GPT/Claude/...)
└───────────┬───────┘         │
            │                 ▼
            │         answer + chunk IDs
            ▼
    cite.verify: re-prompt a second model with the chunks;
    flag claims that don't match source text
```

### New modules

**`src/mayai/corpus/`** (new package)

- `store.py` — SQLite schema: `documents(id, path, mtime, hash)`, `chunks(id, doc_id, text, page, start, end)`, `embeddings(chunk_id, vector)`. Start with stored-as-BLOB numpy arrays and brute-force cosine similarity; migrate to `sqlite-vec` only if corpora grow past ~50k chunks. Keep the store under `~/.config/mayai/corpora/<name>.db` so it's portable and deletable.
- `chunker.py` — splits extracted text into ~500-token windows with 50-token overlap. Respects document structure (don't split across PDF pages if possible). Records source page/offset so citations can point back.
- `embedder.py` — abstract `Embedder` interface with two built-in implementations:
  - `OllamaEmbedder` (default, local, uses `nomic-embed-text` or similar)
  - `OpenAIEmbedder` (optional, for users who already pay)
  Embedders are a **plugin entry-point group** (`mayai.embedders`), so someone can add `VoyageEmbedder` or `CohereEmbedder` without touching core.
- `retriever.py` — takes a query, embeds it, returns top-k chunks with scores and document metadata.
- `builder.py` — orchestrates extract → chunk → embed → store. Idempotent: skip unchanged files by hash. Shows progress. Survives interruption.

**`src/mayai/cite.py`** (new module)

- `verify(answer, chunks, provider)` — given an LLM answer and the source chunks it was grounded in, re-prompt a second (usually cheaper/local) model to check each factual claim against the chunks. Returns a list of `Claim(text, supported: bool, source_chunk_id | None)`. This is the hallucination-catching feature the README promises.
- Works with both corpus chunks and Perplexity web citations (which are URLs, not chunks — so for those, the verifier needs to fetch the URL; gate behind `--fetch-sources` to keep it explicit).

### Extended modules (not new)

- **`research.py`** — gains a `--corpus <name>` flag. When present, runs the corpus pipeline; when absent, falls back to current Perplexity web search. Same return shape: `(answer, citations)`, but `citations` can now be a mix of URLs and corpus chunk IDs.
- **`compare.py`** — gains awareness of corpus context. When comparing, pass the same retrieved chunks to each provider so the comparison is apples-to-apples.
- **`extractor.py`** — already good. Make sure it exposes page/offset metadata (PDFs already do via pdfplumber; DOCX needs a small addition).
- **`cli.py`** — add `mayai corpus build|list|drop|rebuild` subcommand family. Reuses existing subparser pattern.

## New CLI surface

```bash
# One-time setup per corpus
mayai corpus build ~/papers --name phd
mayai corpus list
mayai corpus rebuild phd          # after adding new papers
mayai corpus drop phd

# Query
mayai research --corpus phd "what methods have been used to study X?"
mayai research --corpus phd --compare "..."       # same chunks, multiple models
mayai research --corpus phd --verify "..."        # runs cite.verify post-hoc
mayai research --corpus phd --json "..." | jq ... # pipeline-friendly

# Existing web research still works
mayai research "latest on GLP-1 cardiovascular outcomes"
```

REPL commands mirror the flags: `/corpus use phd`, then `/research ...` uses the active corpus.

## Storage & data layout

```
~/.config/mayai/
  config.toml
  sessions/
  history.db
  corpora/
    phd.db              # one SQLite per corpus — easy to share/back up/delete
    reading-list.db
```

One-file-per-corpus means users can email a corpus to a collaborator, check it into a shared drive, or version-control it. That's a property cloud tools cannot have.

## What we are explicitly NOT building

- **Real-time sync with cloud drives.** Out of scope. Users can re-run `corpus rebuild`; a watcher daemon is too much surface area.
- **A general-purpose agent framework.** No tool loops, no autonomous browsing. The existing `tools/` plugin slot is enough.
- **A web UI.** Every feature must work via CLI + JSON. If someone later wants a TUI, `rich` + the existing JSON output gets them 80%.
- **Our own embedding model.** Use Ollama's `nomic-embed-text` or an OpenAI key. This is not where the value is.
- **Yet another vector DB.** SQLite is enough at the scale of a human being's document collection (≤10k papers). Resist Chroma/Qdrant/Pinecone until a real user hits a real wall.

## Why this shape is defensible

- **Local-first corpus + any provider** is a combination NotebookLM (Google-only), Elicit (cloud-only), and Perplexity Spaces (cloud-only) do not offer.
- **Citation verification across models** is a feature, not a bolt-on. The multi-provider architecture you already have is the exact substrate it needs.
- **Plugin-extensible extractors/embedders** means niche formats (LaTeX, Jupyter, Markdown-with-frontmatter, Zotero exports) ship as third-party packages without touching core.
- **CLI + JSON output** is not a UX limitation — it's the feature. Grad students who live in tmux + vim + pandoc want their tools to compose. That's a small audience, but it's the right audience.

## Open questions (decide before building)

1. Default embedder: require Ollama (friction but principled) or ship a small sentence-transformers fallback (works out of the box but drags in torch)? Recommendation: Ollama required for `corpus build`, with a clear error if not installed. Stays lean.
2. Chunk size: fixed 500 tokens, or adaptive per document structure? Recommendation: start fixed, measure, revisit.
3. Where does cite-verification run by default — every research call, or only when `--verify` is passed? Recommendation: opt-in. It doubles latency and cost; make users choose.
4. Do we support cross-corpus queries (`--corpus phd,reading-list`)? Recommendation: yes, trivially — retrievers just union results. Cheap feature, real value.

## Minimum viable slice (if/when you build)

Not a schedule — just the order that de-risks the most with the least code:

1. `corpus/store.py` + `corpus/chunker.py` + `corpus/builder.py` wired to existing `extractor.py`. No embeddings yet — use BM25 (via `rank_bm25`, pure Python) for retrieval.
2. `research.py --corpus` using BM25 retrieval. Validate end-to-end before touching embeddings.
3. Add `OllamaEmbedder` and switch retrieval to vector similarity.
4. Add `cite.py` verification.
5. Plugin entry points for embedders.

Stopping after step 2 already ships a useful tool. That's the point of slicing it this way.
