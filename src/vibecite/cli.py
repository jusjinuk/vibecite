#!/usr/bin/env python3
"""Minimal CLI that delegates to Claude Code for paper search and formatting."""

import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Optional, List

import typer
from rich.console import Console
from rich.prompt import Prompt, Confirm
from rich.progress import Progress, SpinnerColumn, TextColumn

app = typer.Typer(help="Turn natural-language paper descriptions into curated citations")
console = Console()

# Simple state file to track current session (in working directory)
STATE_FILE = Path.cwd() / ".vc_state.json"


def load_state() -> dict:
    """Load current session state."""
    if STATE_FILE.exists():
        return json.loads(STATE_FILE.read_text())
    return {"vibes": [], "current_bib": None}


def save_state(state: dict) -> None:
    """Save current session state."""
    STATE_FILE.write_text(json.dumps(state, indent=2))


def extract_bibtex_from_response(response: str) -> List[str]:
    """Extract BibTeX entries from code blocks in Claude's response."""
    # Look for ```bibtex ... ``` code blocks
    bibtex_pattern = r'```(?:bibtex)?\s*\n(.*?)\n```'
    matches = re.findall(bibtex_pattern, response, re.DOTALL | re.IGNORECASE)
    
    # Clean up the matches and filter out empty ones
    bibtex_entries = []
    for match in matches:
        cleaned = match.strip()
        if cleaned and '@' in cleaned:  # Basic check for BibTeX entry
            bibtex_entries.append(cleaned)
    
    return bibtex_entries


def check_web_search_settings() -> bool:
    """Check if WebSearch and WebFetch tools are enabled in .claude/settings.local.json."""
    settings_file = Path.cwd() / ".claude" / "settings.local.json"
    
    try:
        if not settings_file.exists():
            # Create .claude directory if it doesn't exist
            settings_file.parent.mkdir(exist_ok=True)
            # Create settings file with WebSearch and WebFetch enabled
            settings = {
                "permissions": {
                    "allow": ["WebSearch", "WebFetch"],
                    "deny": [],
                    "ask": []
                }
            }
            settings_file.write_text(json.dumps(settings, indent=2))
            return True
        
        # Read existing settings
        settings = json.loads(settings_file.read_text())
        allowed_tools = settings.get("permissions", {}).get("allow", [])
        
        # Check if both WebSearch and WebFetch are in the allow list
        has_websearch = "WebSearch" in allowed_tools
        has_webfetch = "WebFetch" in allowed_tools
        
        if not has_websearch or not has_webfetch:
            # Add missing tools
            if not has_websearch:
                allowed_tools.append("WebSearch")
            if not has_webfetch:
                allowed_tools.append("WebFetch")
            
            # Update and save the file
            settings["permissions"]["allow"] = allowed_tools
            settings_file.write_text(json.dumps(settings, indent=2))
            return True
        
        return True
        
    except (json.JSONDecodeError, KeyError, FileNotFoundError) as e:
        console.print(f"[red]Error reading Claude settings: {e}[/red]")
        return False


def enable_web_search_with_consent() -> bool:
    """Ensure WebSearch and WebFetch tools are available in Claude settings."""
    # The check_web_search_settings function now automatically creates or updates
    # the settings file to include WebSearch and WebFetch tools
    if check_web_search_settings():
        console.print("[green]WebSearch and WebFetch tools are enabled![/green]")
        return True
    else:
        console.print("[red]Failed to configure search tools in Claude settings.[/red]")
        console.print("[yellow]Paper discovery may be limited without search tools.[/yellow]")
        return False


def call_claude_code(prompt: str) -> str:
    """Call Claude Code with a search prompt and return results."""
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        task = progress.add_task("Calling Claude Code...", total=None)
        
        try:
            # Enhanced prompt with search tools instructions
            enhanced_prompt = f"""You have access to search tools including WebSearch and WebFetch. Use these tools to search for academic papers.

{prompt}

Please use your available search tools to find relevant academic papers and format them as BibTeX entries. Be thorough in your search and provide high-quality citations."""

            result = subprocess.run(
                ["claude", "--"],  # Assumes claude CLI is available
                input=enhanced_prompt,
                text=True,
                capture_output=True,
                check=True,
            )
            progress.update(task, description="Claude Code completed successfully")
            return result.stdout
        except subprocess.CalledProcessError as e:
            progress.update(task, description=f"Error: {e}")
            console.print(f"[red]Error calling Claude Code: {e}[/red]")
            console.print(f"[red]Error output: {e.stderr}[/red]")
            return ""
        except FileNotFoundError:
            progress.update(task, description="Claude Code CLI not found")
            console.print("[red]Claude Code CLI not found. Please install it first.[/red]")
            return ""


@app.command()
def init(
    bib: Optional[str] = typer.Option(None, "--bib", help="BibTeX file path")
) -> None:
    """Initialize or continue a bibliography project."""
    state = load_state()
    
    if bib:
        bib_path = Path(bib)
        if not bib_path.exists():
            bib_path.touch()
            console.print(f"[green]Created new bibliography file: {bib}[/green]")
        state["current_bib"] = str(bib_path.absolute())
    else:
        state["current_bib"] = str(Path("refs.bib").absolute())
        Path("refs.bib").touch()
        console.print("[green]Created refs.bib[/green]")
    
    save_state(state)
    console.print(f"[blue]Project initialized with bibliography: {state['current_bib']}[/blue]")


@app.command(context_settings={"allow_extra_args": True, "ignore_unknown_options": True})
def add(
    ctx: typer.Context
) -> None:
    """Add a paper vibe (natural language description).
    
    Usage: vc add -- "description of papers you want"
    """
    # Get the description from command line args after --
    args = ctx.args
    if not args:
        console.print("[red]Please provide a description after --[/red]")
        console.print("[yellow]Usage: vc add -- \"your paper description here\"[/yellow]")
        return
    
    description = " ".join(args)
    state = load_state()
    
    vibe = {
        "description": description,
        "results": None
    }
    
    state["vibes"].append(vibe)
    save_state(state)
    
    console.print(f"[green]Added vibe: {description}[/green]")


@app.command()
def search() -> None:
    """Search for papers using Claude Code."""
    state = load_state()
    
    if not state["vibes"]:
        console.print("[yellow]No vibes added yet. Use 'vc add -- \"description\"' first.[/yellow]")
        return
    
    # Check and potentially enable web search
    enable_web_search_with_consent()
    
    for i, vibe in enumerate(state["vibes"]):
        if vibe["results"]:
            continue  # Skip already processed vibes
            
        console.print(f"[blue]Searching for: {vibe['description']}[/blue]")
        
        # Create a focused prompt for Claude Code
        search_prompt = f"""Please search for academic papers matching this description: "{vibe['description']}"

Please find ONLY ONE most relevant paper and return it in BibTeX format. IMPORTANT: When choosing between multiple versions of the same paper, prioritize the conference/journal publication over the arXiv version. Include DOI when available. Format your response with the BibTeX entry inside ```bibtex ``` code blocks."""

        results = call_claude_code(search_prompt)
        
        if results:
            # Store the raw response
            vibe["raw_results"] = results
            
            # Extract and parse BibTeX entries
            bibtex_entries = extract_bibtex_from_response(results)
            if bibtex_entries:
                vibe["results"] = "\n\n".join(bibtex_entries)
                console.print(f"[green]Search completed! Found {len(bibtex_entries)} BibTeX entries.[/green]")
            else:
                # Fallback to raw results if no BibTeX blocks found
                vibe["results"] = results
                console.print("[yellow]Search completed but no BibTeX code blocks found. Using raw response.[/yellow]")
        else:
            console.print("[red]Search failed[/red]")
    
    save_state(state)


@app.command()
def export(
    bib: Optional[str] = typer.Option(None, "--bib", help="Output BibTeX file"),
    format: str = typer.Option("bibtex", "--format", help="Output format (bibtex only for now)")
) -> None:
    """Export collected citations."""
    state = load_state()
    
    output_file = bib or state.get("current_bib") or "refs.bib"
    
    all_results = []
    for vibe in state["vibes"]:
        if vibe["results"]:
            all_results.append(vibe["results"])
    
    if not all_results:
        console.print("[yellow]No search results to export. Run 'vc search' first.[/yellow]")
        return
    
    # Combine all results
    combined_results = "\n\n".join(all_results)
    
    # Write to file
    Path(output_file).write_text(combined_results)
    console.print(f"[green]Exported to {output_file}[/green]")


@app.command()
def ls() -> None:
    """Show currently recorded status."""
    state = load_state()
    
    if not state["vibes"]:
        console.print("[yellow]No vibes recorded[/yellow]")
        return
    
    for i, vibe in enumerate(state["vibes"]):
        console.print(f"\n[blue]Vibe {i+1}:[/blue] {vibe['description']}")
        
        if vibe.get("results"):
            console.print("[green]Has parsed results[/green]")
            
            # Show raw response if available
            if vibe.get("raw_results"):
                console.print("\n[bold]Raw Claude Response:[/bold]")
                console.print(f"[dim]{vibe['raw_results'][:500]}{'...' if len(vibe['raw_results']) > 500 else ''}[/dim]")
            
            # Show parsed BibTeX
            console.print("\n[bold]Parsed BibTeX:[/bold]")
            bibtex_entries = extract_bibtex_from_response(vibe.get("raw_results", ""))
            if bibtex_entries:
                for j, entry in enumerate(bibtex_entries):
                    console.print(entry)
            else:
                console.print("[yellow]No BibTeX entries found in response[/yellow]")
                console.print(f"[dim]{vibe['results'][:200]}{'...' if len(vibe['results']) > 200 else ''}[/dim]")
        else:
            console.print("[red]No results yet[/red]")


@app.command()
def clear() -> None:
    """Clear current session."""
    if STATE_FILE.exists():
        STATE_FILE.unlink()
    console.print("[green]Session cleared[/green]")


if __name__ == "__main__":
    app()
