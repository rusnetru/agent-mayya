from src.tasks.task_graph import TaskGraph


def test_add_task_defaults_to_pending():
    graph = TaskGraph(db_path=":memory:")
    task = graph.add_task("write the spec")
    assert task.status == "pending"
    assert task.depends_on == []


def test_ready_tasks_excludes_unmet_dependencies():
    graph = TaskGraph(db_path=":memory:")
    a = graph.add_task("design")
    b = graph.add_task("implement", depends_on=[a.id])

    ready_ids = [t.id for t in graph.ready_tasks()]
    assert a.id in ready_ids
    assert b.id not in ready_ids

    graph.set_status(a.id, "done")
    ready_ids = [t.id for t in graph.ready_tasks()]
    assert b.id in ready_ids


def test_run_ready_executes_and_marks_status():
    graph = TaskGraph(db_path=":memory:")
    graph.add_task("succeeds")
    graph.add_task("fails")

    def execute(task):
        return task.description == "succeeds"

    completed = graph.run_ready(execute)
    assert completed == 1

    statuses = {t.description: t.status for t in graph.all_tasks()}
    assert statuses["succeeds"] == "done"
    assert statuses["fails"] == "failed"


def test_tasks_persist_across_connections(tmp_path):
    db_path = tmp_path / "tasks.db"

    graph1 = TaskGraph(db_path=db_path)
    graph1.add_task("unfinished work")
    graph1.close()

    graph2 = TaskGraph(db_path=db_path)
    tasks = graph2.all_tasks()
    graph2.close()

    assert len(tasks) == 1
    assert tasks[0].description == "unfinished work"
    assert tasks[0].status == "pending"
