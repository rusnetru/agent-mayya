"""Next Gen Agent — rich terminal interface."""

import os
import time

from dotenv import load_dotenv
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.live import Live
from rich.spinner import Spinner
from rich.text import Text
from rich import box

from src.agent.end_to_end import EndToEndAgent

LOGO = r"""
 __  __
|  \/  |__ _ _  _ _  _ __ _
| |\/| / _` | || | || / _` |
|_|  |_\__,_|\_, |\_, \__,_|
             |__/ |__/
"""
TAGLINE = "autonomous agent · deepseek · 87 tests · 12 phases"

console = Console()


def build_status_table(use_llm: bool, memory_size: int) -> Table:
    t = Table(box=box.SIMPLE, show_header=False, padding=(0, 2))
    t.add_column(style="dim")
    t.add_column(style="bold cyan")
    t.add_row("LLM", "DeepSeek (deepseek-chat)" if use_llm else "stubs (offline)")
    t.add_row("Memory", f"{memory_size} episodes")
    t.add_row("Tools", "web_search · file R/W · python_exec")
    t.add_row("Safety", "MemoryGuard · ApprovalGate · SelfModPolicy")
    t.add_row("Session", time.strftime("%Y-%m-%d %H:%M"))
    return t


def print_header(agent: EndToEndAgent, use_llm: bool) -> None:
    console.print(LOGO, style="bold cyan", highlight=False)
    console.print(f"  {TAGLINE}", style="dim italic")
    console.print()

    # Status panel
    status = build_status_table(use_llm, agent.memory.episodic.count())
    console.print(Panel(status, title="[bold]Mayya[/]", border_style="blue"))

    # Soul.md indicator
    soul_path = "soul.md"
    if os.path.isfile(soul_path):
        size = os.path.getsize(soul_path)
        console.print(f"  [dim]soul.md loaded · {size} bytes · портрет + правила безопасности[/]")
    else:
        console.print("  [yellow]soul.md not found[/]")
    console.print()


def run_task(agent: EndToEndAgent, task: str) -> None:
    """Execute task with spinner + live transcript."""
    transcript_lines = []
    done = False

    with Live(Spinner("dots", text="[cyan]Thinking...[/]"), refresh_per_second=10, console=console) as live:
        try:
            result = agent.run(task)
            transcript_lines = result.orchestration.get("transcript", [])
            done = result.succeeded
        except Exception as e:
            live.update(f"[red]ERROR: {e}[/]")
            return

    # Print results
    status_style = "green" if done else "red"
    status_text = "✓ OK" if done else "✗ FAIL"
    console.print(f"\n[{status_style} bold]{status_text}[/]  strategy={result.strategy}  attempts={result.attempts}")

    if transcript_lines:
        lines = transcript_lines[-6:]  # last 6 lines
        for line in lines:
            console.print(f"  [dim]{line}[/]")


def main() -> None:
    load_dotenv()
    use_llm = bool(os.environ.get("DEEPSEEK_API_KEY"))

    agent = EndToEndAgent(use_llm=use_llm)
    print_header(agent, use_llm)

    console.print("[dim]Type a task, or[/] [bold]/help[/] [dim]·[/] [bold]/status[/] [dim]·[/] [bold]exit[/]\n")

    try:
        while True:
            try:
                task = console.input("[bold cyan]▸[/] ").strip()
            except (EOFError, KeyboardInterrupt):
                console.print("\n[yellow]Shutting down...[/]")
                break

            if not task:
                continue

            cmd = task.lower()

            if cmd in ("exit", "quit", "q"):
                break
            elif cmd == "/help":
                console.print(Panel(
                    "  [bold]Commands:[/]\n"
                    "  [cyan]/help[/]    — this message\n"
                    "  [cyan]/status[/]  — memory & session info\n"
                    "  [cyan]exit[/]     — save & quit\n\n"
                    "  [bold]Just type any task[/] — agent executes it.",
                    border_style="blue"
                ))
                continue
            elif cmd == "/status":
                s = agent.memory.episodic.count()
                t = len(agent.task_graph.all_tasks())
                console.print(f"  [dim]Episodes: {s}  ·  Tasks: {t}  ·  Semantic facts: {len(agent.memory.semantic._graph.nodes)}[/]")
                continue

            run_task(agent, task)

    finally:
        console.print("\n[yellow]Saving session...[/]", end="")
        summary = agent.close()
        console.print(f" [dim]skills={summary['skills_extracted']}  semantic→{summary['semantic_persisted']}[/]")


if __name__ == "__main__":
    main()
