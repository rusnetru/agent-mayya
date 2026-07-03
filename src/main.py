"""Mayya — rich terminal interface with dialog context."""

import os
import time
import re

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
TAGLINE = "autonomous agent · deepseek"

console = Console()
chat_history: list[str] = []


def build_status_table(use_llm: bool, memory_size: int) -> Table:
    t = Table(box=box.SIMPLE, show_header=False, padding=(0, 2))
    t.add_column(style="dim")
    t.add_column(style="bold cyan")
    t.add_row("LLM", "DeepSeek (deepseek-chat)" if use_llm else "stubs (offline)")
    t.add_row("Memory", f"{memory_size} episodes")
    t.add_row("Tools", "web_search · file R/W · python_exec")
    t.add_row("Session", time.strftime("%Y-%m-%d %H:%M"))
    return t


def print_header(agent: EndToEndAgent, use_llm: bool) -> None:
    console.print(LOGO, style="bold cyan", highlight=False)
    console.print(f"  {TAGLINE}", style="dim italic")
    console.print()
    status = build_status_table(use_llm, agent.memory.episodic.count())
    console.print(Panel(status, title="[bold]Mayya[/]", border_style="blue"))
    soul_path = "soul.md"
    if os.path.isfile(soul_path):
        console.print(f"  [dim]soul.md · {os.path.getsize(soul_path)} bytes[/]")
    else:
        console.print("  [yellow]soul.md not found[/]")
    console.print()


def _extract_reply(transcript: list[str]) -> str:
    """Extract the agent's actual reply from transcript, skip system noise."""
    for line in transcript:
        if line.startswith("executor: "):
            return line[len("executor: "):]
        if line.startswith("researcher: "):
            return line[len("researcher: "):]
    return ""


def run_task(agent: EndToEndAgent, task: str) -> None:
    transcript_lines: list[str] = []

    # Build message with dialog context
    if chat_history:
        context = "История диалога:\n" + "\n".join(chat_history[-6:]) + f"\n\nНовое сообщение: {task}"
    else:
        context = task

    with Live(Spinner("dots", text="[cyan]...[/]"), refresh_per_second=10, console=console):
        try:
            result = agent.run(context)
            transcript_lines = result.orchestration.get("transcript", [])
        except Exception as e:
            console.print(f"[red]ERROR: {e}[/]")
            return

    reply = _extract_reply(transcript_lines)
    if reply:
        chat_history.append(f"User: {task}")
        chat_history.append(f"Mayya: {reply}")
        console.print(Panel(reply, title="[bold white]Mayya[/]", border_style="cyan"))
    else:
        console.print("[dim](no response)[/]")


def main() -> None:
    load_dotenv()
    use_llm = bool(os.environ.get("DEEPSEEK_API_KEY"))

    agent = EndToEndAgent(use_llm=use_llm)
    print_header(agent, use_llm)

    console.print("[dim]Type a message, or[/] [bold]/help[/] [dim]·[/] [bold]exit[/]\n")

    # First-run onboarding
    if agent.memory.episodic.count() == 0:
        console.print(Panel(
            "[bold]Привет! Я Mayya — автономный AI-агент.[/]\n\n"
            "Я умею:\n"
            "• Искать в интернете\n"
            "• Читать и писать файлы\n"
            "• Выполнять код на Python\n"
            "• Помнить контекст диалога\n"
            "• Самообучаться на успешных задачах\n\n"
            "[dim]87 тестов · DeepSeek · 4-уровневая память[/]",
            title="[bold white]Mayya[/]",
            border_style="cyan"
        ))
        console.print()

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
                    "  [bold]Just type a message[/] — Mayya replies.",
                    border_style="blue"
                ))
                continue
            elif cmd == "/status":
                s = agent.memory.episodic.count()
                t = len(agent.task_graph.all_tasks())
                g = len(agent.memory.semantic._graph.nodes)
                console.print(f"  [dim]Episodes: {s}  ·  Tasks: {t}  ·  Facts: {g}[/]")
                continue

            run_task(agent, task)

    finally:
        console.print("\n[yellow]Saving...[/]", end="")
        summary = agent.close()
        console.print(f" [dim]done[/]")


if __name__ == "__main__":
    main()
