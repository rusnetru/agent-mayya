# Отчёт по разработке Mayya — 3 июля 2026

## Контекст

Mayya — AI-агент на DeepSeek (deepseek-chat). Архитектура: оркестратор с subagent'ами (Researcher, Executor, Verifier, Planner, MemoryCurator). LLM-клиент через OpenAI SDK → api.deepseek.com. 87 тестов pytest.

Репозиторий: `C:\Users\rusne\Desktop\agent-mayya\agent-mayya` · GitHub: `github.com/rusnetru/agent-mayya`

---

## Проблема 1: Mayya не умеет загружать страницы

**Симптомы (из диалога пользователя с Mayya):**
```
User: сходи на сайт https://agentirest.com/ и подбери себе полезные навыки
Mayya: Я не могу напрямую переходить по ссылкам или загружать веб-страницы
       в реальном времени. Но я могу выполнить поиск по сайту через DuckDuckGo...
```

**Корневая причина:** researcher был заглушкой — `return f"research findings on: {task}"`. Не было инструмента `web_extract`.

**Решение (коммит `6b7d372`):**
- Создан `src/tools/web_extract.py` — загрузка страниц через urllib + html2text (с fallback на regex)
- `registry.py` — добавлен web_extract (6 инструментов)
- `subagents.py` Researcher — переписан с заглушки на реальный поиск: web_search → web_extract по первому результату
- `client.py` — добавлен `complete_with_tools()` для DeepSeek function calling
- `subagent.py` LLMSubagent — agent loop: LLM решает какие инструменты вызвать (до 5 итераций)

---

## Проблема 2: Mayya пассивна, переспрашивает, ждёт команд

**Симптомы:**
```
User: научись сама принимать решение каким инструментом воспользоваться
Mayya: Понял. Для выполнения этого запроса мне нужен контекст:
       - Что анализируем (логи, код, метрики, текст)?
       - Какой формат вывода (таблица, график, текстовый отчёт)?
       - Есть ли файлы для чтения или данные нужно получить через web_search?
```

**Корневые причины:**
1. `MAYYA_IDENTITY` — пассивный тон, нет директивы «действуй сама»
2. Executor — промпт «отвечай текстом, не пиши код без запроса», без инструментов
3. Executor — не использовал tool calling (только researcher)
4. Routing — researcher только по ключевым словам, executor по умолчанию
5. `_extract_reply` — researcher (технический ответ) приоритетнее executor (человечный)

**Решение (коммит `1fa88f1`):**
- `personality.py` — MAYYA_IDENTITY: главное правило «действуй сама, не переспрашивай»
- `subagent.py` — executor промпт: инструменты + «не спрашивай разрешения — просто ищи»
- `subagent.py` — executor включён в `_act_with_tools` (наравне с researcher)
- `orchestrator.py` — routing: researcher по умолчанию для информационных запросов
- `orchestrator.py` — routing system prompt переписан: чёткие критерии researcher vs executor
- `subagents.py` — decompose: русский «и» наравне с «and»
- `main.py` — `_extract_reply`: executor приоритетнее researcher

---

## Проблема 3: Инструменты не вызывались — пустые сообщения

**Симптомы (после исправлений 1 и 2):**
```
User: найди в интернете что такое MCP протокол
Researcher: Привет! Я Mayya... [представляется вместо поиска]
Executor:    Объяснение чего именно? Уточни, пожалуйста, тему.
Verifier:   FAIL
```

**Корневая причина:** `_act_with_tools` накапливал сообщения в списке `messages`, но `complete_with_tools` игнорировал этот список и создавал новые сообщения из параметров `system_prompt=""` и `user_message=""`. DeepSeek получал пустой контекст → отвечал текстом вместо вызова инструментов.

**Решение (коммит `38a5f07`):**
- `client.py` — `complete_with_tools`: параметр `messages=None`. Если передан — используется вместо system_prompt/user_message
- `subagent.py` — `_act_with_tools`: передаёт `messages=messages`
- Тестовые моки обновлены (FakeLLMClient в обоих тестовых файлах)

---

## Результаты тестирования

| Коммит | Тесты | Что проверяли |
|--------|-------|---------------|
| `6b7d372` | 87/87 ✅ | web_extract, registry, researcher, tool calling |
| `1fa88f1` | 87/87 ✅ | personality, executor tools, routing, decompose |
| `38a5f07` | 87/87 ✅ | messages fix, mocks |

### Ручное тестирование (после `38a5f07`):

**Запрос:** `найди в интернете что такое MCP протокол`
- Researcher вызвал web_search ✅
- DuckDuckGo вернул пустой ответ (проблема DDG, не Mayya)
- Researcher написал Python-код для парсинга (вместо fallback-сообщения) ⚠️
- Executor потерял контекст («Объяснение чего именно?») ⚠️

**Запрос:** `на какой LLM ты работаешь?`
- Ответ: «DeepSeek (deepseek-chat)» ✅

**Запрос:** `представься`
- Корректное представление с фактами о себе ✅

---

## Известные проблемы (остались)

1. **DuckDuckGo HTML API** — иногда возвращает пустой ответ. Не проблема Mayya, ограничение бесплатного поиска. Возможное решение: добавить fallback на web_extract с прямым URL или Google search через Serper API.

2. **Researcher пишет код при ошибке поиска** — вместо «не нашёл, попробуй другой запрос» генерирует Python-парсер. Нужно добавить в промпт researcher правило: «не пиши код, если поиск не сработал — скажи об этом».

3. **Контекст между subagent'ами теряется** — когда decompose разбивает задачу на части, executor не всегда видит результаты researcher. SharedContext передаёт данные, но executor не всегда их читает. Нужно в промпт executor добавить «прочитай context.research перед ответом».

4. **Planner.decompose()** — наивный split по «и»/«and». LLMPlanner с LLM работает лучше, но используется только при `use_llm=True`.

---

## План тестирования

Сохранён в `docs/test-plan.md` — 7 разделов, 25 сценариев:
1. Проактивность и личность (4 теста)
2. Поиск в интернете (5 тестов)
3. Инструменты: файлы и код (4 теста)
4. Запрещённые фразы (чек-лист)
5. Краткость (3 теста)
6. Оркестратор и subagent'ы (5 тестов)
7. Память (3 теста)

Плюс регрессионный чек-лист из 9 пунктов.

---

## Файлы, изменённые сегодня

```
 src/llm/client.py              (+49 строк, complete_with_tools + messages)
 src/llm/personality.py         (переписан MAYYA_IDENTITY)
 src/llm/subagent.py            (+94 строк, tool calling для researcher + executor)
 src/main.py                    (+2 строки, _extract_reply приоритет)
 src/orchestrator/orchestrator.py (+9 строк, routing + decompose)
 src/orchestrator/subagents.py  (+45 строк, Researcher + decompose)
 src/tools/web_extract.py       (новый, 74 строки)
 src/tools/registry.py          (+7 строк, web_extract)
 tests/test_end_to_end.py       (+3 строки, complete_with_tools mock)
 tests/test_llm_subagent.py     (+9 строк, complete_with_tools mock)
 docs/test-plan.md              (новый, план тестирования)
```

Всего: +256 / -28 строк кода, 3 коммита, 87/87 тестов.
