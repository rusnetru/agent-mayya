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

import threading

from src.agent.conversational import ConversationalAgent
from src.agent.end_to_end import EndToEndAgent
from src.mcp.client import MCPManager
from src.tools.cron import CronStore

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
    t.add_row("Tools", "web · files · terminal · python · memory")
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
    # Prefer executor (human-facing) over researcher (technical)
    for line in transcript:
        if line.startswith("executor: "):
            return line[len("executor: "):]
    for line in transcript:
        if line.startswith("researcher: "):
            return line[len("researcher: "):]
    return ""


def run_task(agent: EndToEndAgent, task: str) -> None:
    """Main dialog path: conversational agent loop (tools + memory), streamed live.
    Falls back to the orchestrator pipeline when no LLM is configured."""
    global last_task, last_reply

    if conv_ref is not None:
        state = {"text_started": False}

        def on_event(ev: dict) -> None:
            if ev["type"] == "tool":
                if state["text_started"]:
                    console.print()
                    state["text_started"] = False
                console.print(f"[dim]⚙ {ev['name']} {ev.get('args', '')[:100]}[/]")
            elif ev["type"] == "text" and ev["delta"]:
                state["text_started"] = True
                console.print(ev["delta"], end="", markup=False, highlight=False, soft_wrap=True)

        console.print()
        try:
            reply = conv_ref.chat(task, on_event=on_event)
        except Exception as e:
            console.print(f"\n[red]ERROR: {e}[/]")
            return
        if state["text_started"]:
            console.print("\n")
        elif reply:  # ответ пришёл без стриминга (например, после fallback)
            console.print(Panel(reply, title="[bold white]Mayya[/]", border_style="cyan"))
    else:
        with Live(Spinner("dots", text="[cyan]...[/]"), refresh_per_second=10, console=console):
            try:
                result = agent.run(task)
                reply = _extract_reply(result.orchestration.get("transcript", []))
            except Exception as e:
                console.print(f"[red]ERROR: {e}[/]")
                return
        if reply:
            console.print(Panel(reply, title="[bold white]Mayya[/]", border_style="cyan"))

    last_task = task
    if reply:
        chat_history.append(f"User: {task}")
        chat_history.append(f"Mayya: {reply}")
        last_reply = reply
    else:
        console.print("[dim](no response)[/]")


def run_pipeline_task(agent: EndToEndAgent, task: str) -> None:
    """Explicit orchestrator path (/task): decompose → subagent team → verify."""
    global last_task, last_reply
    with Live(Spinner("dots", text="[cyan]orchestrating...[/]"), refresh_per_second=10, console=console):
        try:
            result = agent.run(task)
        except Exception as e:
            console.print(f"[red]ERROR: {e}[/]")
            return

    transcript = result.orchestration.get("transcript", [])
    reply = _extract_reply(transcript) or "\n".join(transcript[-3:])
    last_task = task
    if reply:
        chat_history.append(f"User: {task}")
        chat_history.append(f"Mayya: {reply}")
        last_reply = reply
    status = "[green]verified[/]" if result.succeeded else "[yellow]not verified[/]"
    console.print(Panel(
        reply or "(no output)",
        title=f"[bold white]Mayya · pipeline · {status}[/]",
        border_style="cyan",
    ))


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
        "  [cyan]/task <задача>[/]   Прогнать задачу через оркестратор (subagent-команда)\n"
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
    if conv_ref is not None:
        conv_ref.reset()
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
        "  [cyan]web_search[/]    Поиск: Serper/Google → Yandex → DuckDuckGo\n"
        "  [cyan]web_extract[/]   Загрузка и чтение веб-страницы\n"
        "  [cyan]read_file[/]     Чтение файла\n"
        "  [cyan]write_file[/]    Запись в файл\n"
        "  [cyan]edit_file[/]     Точечная правка (find → replace)\n"
        "  [cyan]search_files[/]  Поиск по файлам (regex)\n"
        "  [cyan]list_dir[/]      Список файлов в директории\n"
        "  [cyan]run_command[/]   Команда в терминале\n"
        "  [cyan]python_exec[/]   Выполнение Python-кода\n"
        "  [cyan]remember[/]      Запомнить факт в долговременную память\n"
        "  [cyan]cronjob[/]       Задачи по расписанию (every/daily/in/once)\n"
        "  [cyan]delegate_task[/] Делегировать подзадачу под-агенту\n"
        + (f"  [cyan]MCP[/]           {mcp_ref.status()}\n" if mcp_ref and mcp_ref.servers else "")
        + "\n[dim]Плюс навыки в папке skills/ — Mayya читает их сама по задаче.[/]",
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
conv_ref: ConversationalAgent | None = None
model_ref: str = ""
mcp_ref: MCPManager | None = None


# ── CRON RUNNER ─────────────────────────────────────────────

def _print_cron_result(job: dict, result: str) -> None:
    console.print()
    console.print(Panel(
        result or "(no output)",
        title=f"[bold yellow]⏰ Cron · {job['schedule']} · {job['task'][:50]}[/]",
        border_style="yellow",
    ))


def _cron_loop(client, tools: dict, stop: threading.Event, notify) -> None:
    """Background thread: run due scheduled jobs through a dedicated agent."""
    store = CronStore()
    while not stop.wait(20):
        for job in store.due():
            try:
                worker = ConversationalAgent(client, memory=agent_ref.memory if agent_ref else None,
                                             tools=tools)
                result = worker.chat(job["task"])
            except Exception as e:
                result = f"ERROR: {e}"
            store.mark_ran(job["id"], result)
            try:
                notify(job, result)
            except Exception:
                pass


def start_cron_runner(client, tools: dict, notify=_print_cron_result) -> threading.Event:
    stop = threading.Event()
    threading.Thread(target=_cron_loop, args=(client, tools, stop, notify), daemon=True).start()
    return stop


# ── TELEGRAM MODE ───────────────────────────────────────────

def run_telegram_mode(agent: EndToEndAgent, client, all_tools: dict) -> None:
    from src.channels.telegram import TelegramChannel, run_telegram_loop

    try:
        channel = TelegramChannel.from_env()
        me = channel.get_me()
    except Exception as e:
        console.print(Panel(
            f"[red]Telegram не настроен:[/] {e}\n\n"
            "1. Создай бота у @BotFather → получи токен\n"
            "2. В .env добавь:\n"
            "   TELEGRAM_BOT_TOKEN=123456:ABC-...\n"
            "   TELEGRAM_ALLOWED_USERS=<твой telegram id>\n"
            "3. Запусти снова: python -m src.main --telegram\n\n"
            "[dim]Токен бота Hermes переиспользовать нельзя — конфликт long polling.[/]",
            title="[bold]Telegram setup[/]", border_style="red"))
        return

    conv = ConversationalAgent(client, memory=agent.memory, tools=all_tools)

    def cron_notify(job: dict, result: str) -> None:
        _print_cron_result(job, result)
        if channel.last_chat_id is not None:
            channel.send_message(channel.last_chat_id, f"⏰ {job['task'][:80]}\n\n{result}")

    cron_stop = start_cron_runner(client, all_tools, notify=cron_notify)
    console.print(Panel(
        f"[bold]Mayya в Telegram:[/] @{me.get('username', '?')}\n"
        f"Разрешённые пользователи: {', '.join(channel.allowed_users) or '[red]все (задай TELEGRAM_ALLOWED_USERS!)[/]'}\n"
        "[dim]Ctrl+C — остановить[/]",
        title="[bold]Telegram mode[/]", border_style="green"))
    try:
        run_telegram_loop(channel, conv, on_message=lambda s: console.print(f"[dim]{s}[/]"))
    except KeyboardInterrupt:
        pass
    finally:
        cron_stop.set()


def main() -> None:
    global agent_ref, conv_ref, model_ref, mcp_ref
    load_dotenv()
    use_llm = bool(os.environ.get("DEEPSEEK_API_KEY"))

    # Semantic memory: real embeddings via ChromaDB when available (fallback: hash index)
    vector_index = None
    memory_kind = "hash-index"
    try:
        from src.memory.chroma_index import ChromaVectorIndex
        vector_index = ChromaVectorIndex(persist_dir="chroma_db")
        memory_kind = "ChromaDB embeddings"
    except Exception as e:
        console.print(f"  [dim yellow]ChromaDB недоступен ({str(e)[:60]}) — память на hash-индексе[/]")

    agent = EndToEndAgent(use_llm=use_llm, vector_index=vector_index)
    agent_ref = agent
    client = agent.orchestrator._llm

    # MCP servers (mcp.json): browser, GitHub, etc.
    mcp_ref = MCPManager()
    mcp_ref.connect()
    from src.tools.registry import REGISTRY
    all_tools = {**REGISTRY, **mcp_ref.make_tools()}

    # Telegram mode: serve chats instead of the terminal REPL
    if "--telegram" in sys.argv:
        if client is None:
            console.print("[red]Telegram-режим требует DEEPSEEK_API_KEY[/]")
            return
        try:
            run_telegram_mode(agent, client, all_tools)
        finally:
            if mcp_ref is not None:
                mcp_ref.close()
            agent.close()
        return

    cron_stop = None
    if client is not None:
        conv_ref = ConversationalAgent(client, memory=agent.memory, tools=all_tools)
        cron_stop = start_cron_runner(client, all_tools)
    model = client.model if client else "stubs (offline)"
    model_ref = model
    print_header(agent, model)
    if mcp_ref.servers or mcp_ref.errors:
        console.print(f"  [dim]MCP: {mcp_ref.status()}[/]")
    console.print(f"  [dim]Memory: {memory_kind}[/]")
    pending = len(CronStore().list())
    if pending:
        console.print(f"  [dim]Cron: {pending} задач(и) в расписании[/]")

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
            "[dim]146 тестов · DeepSeek · 4-уровневая память · MCP · Telegram[/]",
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
            elif name == "/task":
                if args.strip():
                    run_pipeline_task(agent, args.strip())
                else:
                    console.print("[dim]Использование: /task <задача>[/]")
            else:
                run_task(agent, task)

    finally:
        console.print("\n[yellow]Saving...[/]", end="")
        if cron_stop is not None:
            cron_stop.set()
        if mcp_ref is not None:
            mcp_ref.close()
        summary = agent.close()
        console.print(f" [dim]done[/]")


if __name__ == "__main__":
    main()
