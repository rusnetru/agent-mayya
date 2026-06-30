# Развёртывание и обновление Next Gen Agent

Репозиторий: https://github.com/rusnetru/next-gen-agent

Основной способ развёртывания — **git-клон + venv**, а не сборка отдельного `.exe`.
Это даёт пользователю встроенный путь обновления: `git pull` подтягивает новый код
без переустановки. Сборка standalone `.exe` (PyInstaller) остаётся опциональной —
см. раздел 4.

---

## 1. Требования

| Что | Версия |
|---|---|
| Python | 3.11+ |
| Git | любой современный |
| ОС | Windows 10/11 (основная цель); Linux/macOS — тоже подходит |

```powershell
python --version
git --version
```

Если Python не найден — поставить с [python.org](https://www.python.org/downloads/) (отметить "Add python.exe to PATH").

---

## 2. Первичная установка

```powershell
git clone https://github.com/rusnetru/next-gen-agent.git
cd next-gen-agent
.\install.ps1
```

`install.ps1` создаёт `.venv` и ставит зависимости (`pip install -r requirements.txt`). Если PowerShell блокирует выполнение скриптов:

```powershell
Set-ExecutionPolicy -Scope CurrentUser RemoteSigned
```

Проверить, что всё работает:

```powershell
.\.venv\Scripts\python.exe -m pytest -q
```

Запустить агента:

```powershell
.\.venv\Scripts\python.exe src\main.py
```

Рядом появится `memory.db` — персистентная episodic-память (SQLite), переживает перезапуск.

---

## 3. Обновление (git pull)

Когда в репозитории на GitHub появляется новый код, на машине пользователя достаточно:

```powershell
cd next-gen-agent
.\update.ps1
```

Что делает `update.ps1`:
1. Проверяет, что в рабочей копии нет незакоммиченных изменений — если есть, останавливается и просит закоммитить/застешить (чтобы не потерять локальные правки).
2. `git fetch` + `git pull --ff-only` — подтягивает новые коммиты только fast-forward'ом (никаких автослияний; если история разошлась, скрипт сообщит об этом явно, а не попытается смержить вслепую).
3. Если в обновлении менялся `requirements.txt` — автоматически переустанавливает зависимости.

### Программный self-update (для самого агента)

Та же логика доступна агенту изнутри как Python API — `src/update/self_update.py`:

```python
from src.update.self_update import self_update, check_for_updates

if check_for_updates("."):
    result = self_update(".")
    if result.updated:
        print(f"updated {result.before_commit[:7]} -> {result.after_commit[:7]}")
        if result.dependencies_changed:
            print("requirements.txt changed — reinstall dependencies")
    else:
        print(f"update skipped: {result.message}")
```

`self_update()` никогда не апдейтит поверх грязного дерева и никогда не делает merge/rebase — только fast-forward `git pull`. Это можно вызывать из самого agent loop (например, на старте сессии) или из планировщика задач (cron/Task Scheduler), чтобы агент периодически подтягивал новый код самостоятельно.

---

## 4. (Опционально) Сборка отдельного .exe

Если конкретному пользователю нужен один файл без Python и без git вообще — можно по-прежнему собрать standalone `.exe`. Это **не основной путь развёртывания**: такой `.exe` не умеет git pull и не обновляется — для обновления его придётся пересобирать и заново копировать на машину.

```powershell
.\.venv\Scripts\python.exe -m pip install pyinstaller
.\build.ps1
```

Результат — `dist\next-gen-agent.exe` (~230 МБ, тянет тяжёлые транзитивные зависимости `chromadb`). Подходит для разовой раздачи на машину, где git/Python ставить не хотят или нельзя — но для штатного сценария с обновлениями используйте git-клон (разделы 2–3).

---

## 5. Типичные проблемы

| Проблема | Решение |
|---|---|
| `python`/`git`: command not found | Установить, добавить в PATH, перезапустить терминал |
| PowerShell не даёт запустить `.ps1` | `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned` |
| `update.ps1` отказывается обновлять: "Uncommitted local changes" | Закоммитить или `git stash` локальные правки, затем повторить |
| `git pull --ff-only` падает (история разошлась) | Кто-то менял код локально и в origin одновременно — разобраться вручную (`git log`, `git merge`/`git rebase` осознанно), скрипт намеренно не делает это автоматически |
| `pip install` падает на `chromadb` (нет интернета / мало места) | Самые тяжёлые пакеты в `requirements.txt`; нужен стабильный интернет и от 2 ГБ свободного места |

---

## 6. Что дальше

Текущий agent loop (`src/main.py`) — минимальный пример (Фаза 0) поверх полноценной памяти/оркестратора/планирования/эволюции (Фазы 1–5), которые реализованы как библиотека, но ещё не связаны в единый end-to-end сценарий — см. [docs/00_progress_log.md](00_progress_log.md), раздел «Следующий шаг».
