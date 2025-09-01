# vibecite

A minimal CLI that turns natural-language paper descriptions into curated citations by delegating to Claude Code for search and formatting.

## Installation

```bash
# Install from local directory
pip install -e .

# Or install with uv
uv pip install git+https://github.com/jusjinuk/vibecite

# Or run directly with uvx
uvx --from git+https://github.com/jusjinuk/vibecite vc
```

## Requirements

- Python 3.9+
- [Claude Code](https://claude.ai/code) CLI installed and available in your PATH

## Usage

### Basic workflow

```bash
# Initialize a project
vc init --bib refs.bib

# Add paper descriptions ("vibes") using the -- syntax
vc add -- RLHF compression that preserves policy alignment

# Search for papers (delegates to Claude Code with progress feedback)
vc search

# Export to BibTeX
vc export --bib refs.bib
```

### Commands

- `vc init [--bib FILE]` - Initialize or continue a bibliography project
- `vc add -- DESCRIPTION` - Add a paper vibe using natural language
- `vc search` - Search for papers using Claude Code (shows progress)
- `vc export [--bib FILE]` - Export collected citations to BibTeX
- `vc status` - Show current session status
- `vc clear` - Clear current session

### Example

```bash
vc init
vc add -- neural network pruning methods that maintain accuracy
vc search
vc export
```

## How it works

1. **Local storage**: Uses a JSON file (`.vc_state.json`) in your working directory to track paper vibes
2. **Claude Code integration**: Sends enhanced prompts to Claude Code with search tool instructions for finding academic papers
3. **Progress feedback**: Shows real-time progress when Claude Code is working, so you know what's happening
4. **Minimal dependencies**: Just `typer` and `rich` - no databases, SQLite, or complex APIs
5. **Natural language interface**: Use `vc add -- "description"` syntax for intuitive paper descriptions
6. **Delegate complexity**: Let Claude Code handle web searching, ranking, and BibTeX formatting

## License

MIT
