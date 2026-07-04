from src.memory.api import Memory


def make_memory(**kwargs) -> Memory:
    return Memory(db_path=":memory:", **kwargs)


def test_store_and_retrieve_episodic():
    memory = make_memory()
    memory.store("user likes coffee")
    result = memory.retrieve("coffee")
    assert any("coffee" in e.content for e in result["episodic"])


def test_consolidate_promotes_recurring_episodes():
    memory = make_memory(consolidate_every=0)
    memory.store("user likes coffee")
    memory.store("user likes coffee")
    promoted = memory.consolidate()
    assert promoted == 1
    assert memory.semantic.has_fact("user likes coffee")


def test_auto_consolidate_triggers_after_n_episodes():
    memory = make_memory(consolidate_every=2)
    memory.store("repeat me")
    memory.store("repeat me")
    assert memory.semantic.has_fact("repeat me")


def test_skill_extract_from_episode_with_plan():
    memory = make_memory()
    memory.store("greet user", context={"plan": "say hello"})
    skill = memory.skill_extract(0)
    assert skill is not None
    assert skill.procedure == "say hello"


def test_skill_extract_returns_none_without_plan():
    memory = make_memory()
    memory.store("no plan event")
    assert memory.skill_extract(0) is None


def test_working_memory_tracks_recent_events():
    memory = make_memory()
    memory.store("event one")
    memory.store("event two")
    assert memory.working.as_list() == ["event one", "event two"]


def test_working_memory_evicts_oldest_when_full():
    memory = make_memory(working_capacity=2)
    memory.store("first")
    memory.store("second")
    memory.store("third")
    assert memory.working.as_list() == ["second", "third"]


def test_custom_vector_index_is_wired_through():
    class SpyIndex:
        def __init__(self):
            self.added, self.searched = [], []

        def add(self, item_id, text):
            self.added.append((item_id, text))

        def remove(self, item_id):
            pass

        def search(self, query, top_k=5):
            self.searched.append(query)
            return [(self.added[0][0], 1.0)] if self.added else []

    spy = SpyIndex()
    memory = Memory(db_path=":memory:", vector_index=spy)
    memory.store("меня зовут Руслан")
    hits = memory.retrieve("как зовут пользователя")["episodic"]

    assert spy.added and spy.searched  # index really used for store + retrieve
    assert hits and hits[0].content == "меня зовут Руслан"
