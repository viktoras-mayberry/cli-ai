# MAYAI — Your AI Assistant in the Terminal

Chat with AI, research topics with cited sources, find and manage files on your computer, and compare answers from multiple AI models — all from one simple command.

## What Can MAYAI Do?

### Chat with AI
Talk to powerful AI models (GPT-4, Claude, Gemini, and more) directly from your terminal. No browser tabs needed.

```bash
mayai "What's the best way to organize my photos?"
```

### Research with Sources
Ask a question and get an answer backed by real web sources — perfect for students and researchers.

```bash
mayai --research "What are the latest treatments for type 2 diabetes?"
```

### Find Files on Your Computer
Describe what you're looking for in plain English. MAYAI searches your files by name, type, and date.

```bash
mayai --find "tax documents from 2025"
```

### Compare AI Models
Ask the same question to multiple AI models at once and see how their answers differ.

```bash
mayai --compare "Explain quantum computing in simple terms"
```

### Read Any File
Open and read PDFs, Word documents, Excel spreadsheets, and more — right in your terminal.

```bash
# In the interactive chat:
/open ~/Documents/report.pdf
```

### Move, Rename, and Convert Files
Organize your files and convert between formats with simple commands.

```bash
# In the interactive chat:
/move ~/Downloads/invoice.pdf ~/Documents/Tax/
/convert data.csv to xlsx
```

## Getting Started

### 1. Install MAYAI

```bash
pip install mayai
```

For PDF, Word, and Excel support:
```bash
pip install mayai[all]
```

### 2. Run the Setup Wizard

```bash
mayai setup
```

The wizard walks you through:
- Detecting free local AI (Ollama) on your machine
- Setting up API keys for cloud AI providers
- Choosing your default AI model

### 3. Start Chatting

```bash
mayai
```

That's it! You'll see a welcome screen with all available commands.

## Available AI Providers

| Provider   | What It's Good For                    | Free? |
|------------|---------------------------------------|-------|
| Ollama     | Private, local AI on your machine     | Yes   |
| OpenAI     | GPT-4o, powerful general-purpose AI   | No    |
| Anthropic  | Claude, great for analysis            | No    |
| Google     | Gemini, fast and versatile            | No    |
| Perplexity | Web search with cited sources         | No    |
| Groq       | Ultra-fast AI responses               | Free tier |

Switch between providers anytime:
```
/use claude
/use gpt
/use ollama
```

## Commands Reference

### In the Chat (Interactive Mode)

| Command | What It Does |
|---------|-------------|
| `/research <question>` | Search the web and get sourced answers |
| `/compare <question>` | Ask multiple AIs and compare answers |
| `/find <description>` | Search for files on your computer |
| `/open <filepath>` | Read any file (PDF, Word, Excel, text...) |
| `/move <source> <dest>` | Move or rename files |
| `/convert <file> to <format>` | Convert file formats (csv to xlsx, png to jpg...) |
| `/use <provider>` | Switch AI provider |
| `/save [name]` | Save your conversation |
| `/load <name>` | Resume a saved conversation |
| `/help` | See all commands |
| `/bye` | Exit MAYAI |

### From the Command Line

```bash
mayai "your question"                  Ask a question directly
mayai --research "your question"       Research with sources
mayai --compare "your question"        Compare multiple AIs
mayai --find "file description"        Search for files
mayai --shell "what you want to do"    Generate a terminal command
mayai setup                            Run the setup wizard
mayai index ~/Documents               Build file search index
```

## File Search Index

For faster and deeper file searches (searching inside file contents, not just names), build an index:

```bash
mayai index ~/Documents
```

This creates a search index so `/find` can look inside your text files, not just at file names.

## Supported File Formats

### Reading (`/open`)
- **Documents**: PDF, Word (.docx), plain text, Markdown
- **Spreadsheets**: Excel (.xlsx), CSV
- **Data**: JSON, YAML, TOML, XML
- **Code**: Python, JavaScript, HTML, CSS, and more

### Converting (`/convert`)
- CSV to Excel, Excel to CSV
- JSON to CSV, CSV to JSON
- Text to Word, Word to text
- PNG to JPG, JPG to PNG, WebP conversions
- And more...

## Configuration

Your settings are stored at `~/.config/mayai/config.toml`.

```bash
mayai config show          # See your current settings
mayai config set <key> <value>   # Change a setting
mayai config init          # Reset to defaults
```

### Adding API Keys

```bash
mayai config set providers.openai.api_key sk-...
mayai config set providers.anthropic.api_key sk-ant-...
mayai config set providers.perplexity.api_key pplx-...
```

Or use environment variables:
```bash
export OPENAI_API_KEY="sk-..."
export ANTHROPIC_API_KEY="sk-ant-..."
export PERPLEXITY_API_KEY="pplx-..."
```

## Using Local AI (Ollama)

Want to use AI without sending data to the cloud? Install Ollama for free:

1. Download from https://ollama.com
2. Pull a model: `ollama pull llama3.2`
3. Start it: `ollama serve`
4. Chat: `mayai -p ollama`

No API key needed. Your data stays on your machine.

## Session Persistence

Your conversations are automatically saved when you exit. Resume anytime:

```bash
mayai -s my-research    # Resume a saved session
mayai sessions          # List all sessions
```

## Cost Tracking

MAYAI shows token usage and estimated cost after each response, so you always know what you're spending.

```
/cost    # See session totals
```

## Requirements

- Python 3.11 or newer
- pip (Python package manager)

## License

MIT — Copyright (c) 2026 MAYAI
