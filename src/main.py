"""Mayya — rich terminal interface with dialog context and commands."""

import os
import time
import datetime
import subprocess
import sys

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
session_title: str = ""
last_task: str = ""
last_reply: str = ""


def build_status_table(client_model: str, memory_size: int) -> Table:
    t = Table(box=box.SIMPLE, show_header=False, padding=(0, 2))
    t.add_column(style="dim")
    t.add_column(style="bold cyan")
    t.add_row("LLM", client_model)
    t.add_row("Memory", f"{memory_size} episodes")
    t.add_row("Tools", "web_search · file R/W · python_exec")
    t.add_row("Session", time.strftime("%Y-%m-%d %H:%M"))
    if session_title:
        t.add_row("Title", session_title)
    return t


def print_header(agent: EndToEndAgent, model: str) -> None:
    console.print(LOGO, style="bold cyan", highlight=False)
    console.print(f"  {TAGLINE}", style="dim italic")
    console.print()
    status = build_status_table(model, agent.memory.episodic.count())
    console.print(Panel(status, title="[bold]Mayya[/]", border_style="blue"))
    soul_path = "soul.md"
    if os.path.isfile(soul_path):
        console.print(f"  [dim]soul.md · {os.path.getsize(soul_path)} bytes[/]")
    else:
        console.print("  [yellow]soul.md not found[/]")
    console.print()


def _extract_reply(transcript: list[str]) -> str:
    for line in transcript:
        if line.startswith("executor: "):
            return line[len("executor: "):]
        if line.startswith("researcher: "):
            return line[len("researcher: "):]
    return ""


def run_task(agent: EndToEndAgent, task: str) -> None:
    global last_task, last_reply
    transcript_lines: list[str] = []

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
    last_task = task
    if reply:
        chat_history.append(f"User: {task}")
        chat_history.append(f"Mayya: {reply}")
        last_reply = reply
        console.print(Panel(reply, title="[bold white]Mayya[/]", border_style="cyan"))
    else:
        console.print("[dim](no response)[/]")


# ── SLASH COMMANDS ──────────────────────────────────────────

def cmd_help() -> None:
    console.print(Panel(
        "[bold]Управление сессией[/]\n"
        "  [cyan]/new, /reset[/]     Новая сессия (сброс контекста)\n"
        "  [cyan]/clear[/]           Очистить экран\n"
        "  [cyan]/retry[/]           Повторить последнее сообщение\n"
        "  [cyan]/title <name>[/]    Назвать сессию\n"
        "  [cyan]/history[/]         Показать историю диалога\n"
        "\n[bold]Инструменты[/]\n"
        "  [cyan]/tools[/]           Список инструментов\n"
        "  [cyan]/model [name][/]    Показать/сменить модель\n"
        "\n[bold]Утилиты[/]\n"
        "  [cyan]/save[/]            Сохранить диалог в файл\n"
        "  [cyan]/copy[/]            Скопировать последний ответ в буфер\n"
        "  [cyan]/status[/]          Состояние памяти и сессии\n"
        "  [cyan]/usage[/]           Статистика использования\n"
        "\n[bold]Выход[/]\n"
        "  [cyan]/quit, /exit, /q[/] Выйти с сохранением\n"
        "\n[dim]Любое другое сообщение — диалог с Mayya[/]",
        title="[bold]Команды[/]", border_style="blue"))


def cmd_clear() -> None:
    console.clear()
    print_header(agent_ref, model_ref)


def cmd_new() -> None:
    global chat_history, session_title
    chat_history.clear()
    session_title = ""
    console.print("[yellow]Новая сессия. Контекст сброшен.[/]")


def cmd_retry() -> None:
    if last_task:
        console.print(f"[dim]Повтор: {last_task}[/]")
        run_task(agent_ref, last_task)
    else:
        console.print("[dim]Нечего повторять.[/]")


def cmd_title(args: str) -> None:
    global session_title
    if args.strip():
        session_title = args.strip()
        console.print(f"[green]Сессия названа: {session_title}[/]")
    else:
        console.print(f"[dim]Текущее название: {session_title or '(нет)'}[/]")


def cmd_history() -> None:
    if not chat_history:
        console.print("[dim]История пуста.[/]")
        return
    lines = []
    for i, line in enumerate(chat_history[-20:]):
        style = "bold cyan" if line.startswith("User:") else "bold white"
        lines.append(f"[{style}]{line}[/]")
    console.print(Panel("\n".join(lines), title="[bold]История[/]", border_style="blue"))


def cmd_save() -> None:
    if not chat_history:
        console.print("[dim]Нечего сохранять.[/]")
        return
    ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    path = f"mayya_chat_{ts}.md"
    with open(path, "w", encoding="utf-8") as f:
        f.write(f"# Mayya Chat — {ts}\n")
        if session_title:
            f.write(f"## {session_title}\n")
        f.write("\n".join(chat_history))
    console.print(f"[green]Сохранено: {path}[/]")


def cmd_copy() -> None:
    if not last_reply:
        console.print("[dim]Нечего копировать.[/]")
        return
    try:
        subprocess.run(["clip"], input=last_reply, text=True, shell=True)
        console.print("[green]Скопировано в буфер.[/]")
    except Exception:
        console.print("[dim](буфер обмена недоступен в этом терминале)[/]")


def cmd_status(agent: EndToEndAgent) -> None:
    s = agent.memory.episodic.count()
    t = len(agent.task_graph.all_tasks())
    g = len(agent.memory.semantic._graph.nodes)
    console.print(Panel(
        f"[bold]Память[/]\n"
        f"  Episodes: {s}\n"
        f"  Tasks:    {t}\n"
        f"  Facts:    {g}\n\n"
        f"[bold]Диалог[/]\n"
        f"  Сообщений: {len(chat_history)}\n"
        f"  Сессия:    {session_title or '(нет)'}",
        title="[bold]Статус[/]", border_style="blue"))


def cmd_usage(agent: EndToEndAgent) -> None:
    s = agent.memory.episodic.count()
    t = len(agent.task_graph.all_tasks())
    console.print(Panel(
        f"[bold]Сессия[/]\n"
        f"  Сообщений в диалоге:  {len(chat_history)}\n"
        f"  Эпизодов в памяти:    {s}\n"
        f"  Задач в графе:        {t}\n"
        f"  Время сессии:         {time.strftime('%H:%M:%S')}",
        title="[bold]Статистика[/]", border_style="blue"))


def cmd_tools() -> None:
    console.print(Panel(
        "[bold]Доступные инструменты[/]\n\n"
        "  [cyan]web_search[/]   Поиск в интернете (DuckDuckGo)\n"
        "  [cyan]read_file[/]    Чтение файла\n"
        "  [cyan]write_file[/]   Запись в файл\n"
        "  [cyan]list_dir[/]     Список файлов в директории\n"
        "  [cyan]python_exec[/]  Выполнение Python-кода\n\n"
        "[dim]Инструменты вызываются автоматически через LLM.[/]",
        title="[bold]Tools[/]", border_style="cyan"))


def cmd_model(args: str, agent: EndToEndAgent) -> None:
    current = agent.orchestrator._llm.model if agent.orchestrator._llm else "stubs"
    if not args.strip():
        console.print(f"[bold]Текущая модель:[/] [cyan]{current}[/]")
        console.print("[dim]Доступные: deepseek-chat, deepseek-reasoner[/]")
        console.print("[dim]Смена: /model deepseek-chat[/]")
        return
    console.print(f"[yellow]Смена модели требует перезапуска. Текущая: {current}[/]")


# ── GLOBALS FOR COMMANDS ────────────────────────────────────

agent_ref: EndToEndAgent = None  # type: ignore[assignment]
model_ref: str = ""


def main() -> None:
    global agent_ref, model_ref
    load_dotenv()
    use_llm = bool(os.environ.get("DEEPSEEK_API_KEY"))

    agent = EndToEndAgent(use_llm=use_llm)
    agent_ref = agent
    model = agent.orchestrator._llm.model if agent.orchestrator._llm else "stubs (offline)"
    model_ref = model
    print_header(agent, model)

    console.print("[dim]Введите сообщение или[/] [bold]/help[/] [dim]для списка команд[/]\n")

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

            # ── Command dispatch ──
            cmd = task.lower().split(maxsplit=1)
            name = cmd[0]
            args = cmd[1] if len(cmd) > 1 else ""

            if name in ("exit", "quit", "q", "/quit", "/exit", "/q"):
                break
            elif name in ("/help", "/commands", "/?"):
                cmd_help()
            elif name in ("/new", "/reset"):
                cmd_new()
            elif name == "/clear":
                cmd_clear()
            elif name == "/retry":
                cmd_retry()
            elif name == "/title":
                cmd_title(args)
            elif name == "/history":
                cmd_history()
            elif name == "/save":
                cmd_save()
            elif name == "/copy":
                cmd_copy()
            elif name == "/status":
                cmd_status(agent)
            elif name == "/usage":
                cmd_usage(agent)
            elif name == "/tools":
                cmd_tools()
            elif name == "/model":
                cmd_model(args, agent)
            else:
                run_task(agent, task)

    finally:
        console.print("\n[yellow]Saving...[/]", end="")
        summary = agent.close()
        console.print(f" [dim]done[/]")


if __name__ == "__main__":
    main()
