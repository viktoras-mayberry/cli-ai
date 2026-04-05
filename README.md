# MAYAI — Multi-provider AI CLI

Chat with OpenAI, Anthropic (Claude), Google Gemini, Perplexity, Groq, or local Ollama models — all from one terminal command.

## Features

- **Multi-provider**: OpenAI, Anthropic, Gemini, Perplexity, Groq, Ollama (local)
- **Real-time streaming**: responses print as they are generated
- **Multi-turn chat**: full conversation history in interactive REPL mode
- **Session persistence**: save, load, and resume conversations across restarts
- **Pipe-friendly output**: `--raw` for plain text piping, `--json` for structured output
- **File / stdin input**: pipe any file directly into your query
- **Prompt patterns**: reusable named prompts with per-pattern provider/model routing
- **Cost estimation**: live token count and USD cost per response with `--estimate`
- **Config file**: store API keys and defaults in `~/.config/mayai/config.toml`
- **In-chat commands**: switch provider, apply patterns, save/load sessions, view costs

## Requirements

- Python 3.11+
- pip

## Installation

```bash
pip install mayai
```

Or install from source:

```bash
git clone https://github.com/viktoras-mayberry/cli-ai
cd cli-ai
pip install .
```

## Quick Start

### 1. Initialise your config file

```bash
mayai config init
```

This creates `~/.config/mayai/config.toml` with all providers pre-configured.

### 2. Add your API keys

```bash
mayai config set providers.openai.api_key sk-...
mayai config set providers.anthropic.api_key sk-ant-...
mayai config set providers.gemini.api_key AIza...
mayai config set providers.perplexity.api_key pplx-...
mayai config set providers.groq.api_key gsk_...
```

Or use environment variables:

```bash
export OPENAI_API_KEY="sk-..."
export ANTHROPIC_API_KEY="sk-ant-..."
export GEMINI_API_KEY="AIza..."
export PERPLEXITY_API_KEY="pplx-..."
export GROQ_API_KEY="gsk_..."
```

### 3. Set your default provider (optional)

```bash
mayai config set defaults.provider anthropic
```

### 4. Start chatting

```bash
# Interactive REPL (default provider)
mayai

# Interactive REPL with a specific provider and model
mayai -p openai -m gpt-4o
mayai -p anthropic -m claude-opus-4-6
mayai -p gemini -m gemini-2.0-flash
mayai -p groq -m llama-3.3-70b-versatile
mayai -p ollama -m llama3.2

# Single-shot query (no REPL)
mayai "Explain quantum entanglement in one paragraph"
mayai -p perplexity "What happened in tech news today?"
```

## Providers & Models

| Provider   | Flag            | Models                                                         |
|------------|-----------------|----------------------------------------------------------------|
| OpenAI     | `-p openai`     | gpt-4o, gpt-4o-mini, gpt-4-turbo, o1, o3-mini, ...           |
| Anthropic  | `-p anthropic`  | claude-opus-4-6, claude-sonnet-4-6, claude-haiku-4-5, ...     |
| Gemini     | `-p gemini`     | gemini-2.0-flash, gemini-1.5-pro, gemini-1.5-flash, ...       |
| Perplexity | `-p perplexity` | sonar-pro, sonar-reasoning-pro, sonar-reasoning, sonar         |
| Groq       | `-p groq`       | llama-3.3-70b-versatile, mixtral-8x7b-32768, gemma2-9b-it, ...|
| Ollama     | `-p ollama`     | Any locally pulled model (llama3.2, mistral, codellama, ...)  |

List models:

```bash
mayai models                # all providers
mayai models -p openai      # specific provider
mayai models -p ollama      # locally installed Ollama models
```

## In-chat Commands (REPL mode)

| Command                        | Description                                        |
|--------------------------------|----------------------------------------------------|
| `/save [name]`                 | Save current conversation (auto-names if omitted)  |
| `/load <name>`                 | Load and resume a saved conversation               |
| `/sessions`                    | List all saved sessions                            |
| `/sessions delete <name>`      | Delete a saved session                             |
| `/switch <provider> [model]`   | Switch provider (history is preserved)             |
| `/pattern <name>`              | Apply a prompt pattern to this session             |
| `/patterns`                    | List all defined patterns                          |
| `/clear`                       | Clear conversation history                         |
| `/models`                      | List models for the current provider               |
| `/history`                     | Show conversation history                          |
| `/cost`                        | Show session token usage and cost estimate         |
| `/help`                        | Show command list                                  |
| `/exit`                        | Exit MAYAI (auto-saves conversation)               |

## Pipe-Friendly Output

```bash
# --raw: bare response text, no decorators — perfect for piping
mayai --raw "List 5 Unix tips" | grep "tip"
mayai --raw "Write a haiku" > haiku.txt

# --json: structured JSON output
mayai --json "Summarize Redis" | jq '.response'
mayai --json -p openai "Explain REST" > result.json
```

The JSON schema:
```json
{
  "response": "...",
  "provider": "openai",
  "model": "gpt-4o",
  "tokens": { "estimated_input": 42, "estimated_output": 310 },
  "estimated_cost_usd": 0.003875
}
```

## File & Stdin Input

Pipe any file content directly into your query:

```bash
# Review a file
cat src/auth.py | mayai "Find security issues in this code"

# Summarize a document
mayai "Summarize this" < report.txt

# Combine a query with file input
mayai -P code-review < myfile.py

# Chain commands
git diff | mayai --raw "Write a commit message for these changes"
```

## Prompt Patterns

Patterns are reusable named prompts defined in your config file. They can pin a specific system prompt, provider, and model — so you don't have to repeat yourself.

```bash
# Use a pattern
mayai -P code-review < myfile.py
mayai -P summarize < long_article.txt
mayai -P search "latest Python 3.14 features"
mayai -P explain "what is a merkle tree"
mayai -P fix < error_log.txt

# List all patterns
mayai patterns

# Switch pattern mid-conversation (REPL)
/pattern code-review
```

Built-in patterns: `code-review`, `summarize`, `search`, `explain`, `fix`

Define your own in `~/.config/mayai/config.toml`:

```toml
[patterns.my-pattern]
system_prompt = "You are an expert in distributed systems. Be rigorous and technical."
provider = "anthropic"          # optional — overrides default provider
model = "claude-opus-4-6"       # optional — overrides default model
```

## Cost Estimation

MAYAI tracks token usage and estimates cost after every response:

```
~320 tokens in | ~180 tokens out | est. $0.0062 | session total: $0.0187
```

Before sending a long or expensive query, preview the cost:

```bash
mayai --estimate "Rewrite this entire codebase" < main.py
# Shows: Estimated input: ~2,400 tokens | cost: ~$0.0720
# Continue? [y/N]
```

View session totals in the REPL:
```
/cost
```

## Session Persistence

MAYAI automatically saves your conversation when you exit so you never lose context.

```bash
# Resume a session from the terminal
mayai -s my-research

# Resume a session and immediately ask a follow-up
mayai -s my-research "Can you elaborate on the last point?"

# Manage sessions
mayai sessions                    # list all saved sessions
mayai sessions delete my-research # delete a session
```

Sessions are stored as JSON at `~/.config/mayai/sessions/`.

## Config File

Located at `~/.config/mayai/config.toml`:

```toml
[defaults]
provider = "openai"
system_prompt = "Be precise and concise."

[providers.openai]
api_key = "sk-..."
default_model = "gpt-4o"

[providers.anthropic]
api_key = "sk-ant-..."
default_model = "claude-opus-4-6"

[providers.gemini]
api_key = "AIza..."
default_model = "gemini-2.0-flash"

[providers.perplexity]
api_key = "pplx-..."
default_model = "sonar-pro"

[providers.groq]
api_key = "gsk_..."
default_model = "llama-3.3-70b-versatile"

[providers.ollama]
base_url = "http://localhost:11434"
default_model = "llama3.2"
```

```bash
mayai config show       # print current config
mayai config path       # print config file path
mayai config init       # (re)create default config
```

## Local Models (Ollama)

1. Install Ollama: https://ollama.com
2. Pull a model: `ollama pull llama3.2`
3. Start the server: `ollama serve`
4. Chat: `mayai -p ollama -m llama3.2`

No API key needed for local models.

## CLI Reference

```
mayai [query] [-p PROVIDER] [-m MODEL] [-s SESSION] [-P PATTERN]
              [--raw | --json] [--estimate] [-v]
mayai models [-p PROVIDER]
mayai patterns
mayai sessions [delete <name>]
mayai config [show|set|path|init]
mayai --version
```

## License

MIT — Copyright (c) 2026 MAYAI
