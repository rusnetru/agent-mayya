"""End-to-end agent (Phase 6 — sequential integration).

Wires together pieces that, until now, only existed as independent tested
modules: Orchestrator (Phase 2) executes the task through a subagent team
(optionally LLM-backed, Phase 6), wrapped in the Phase 3 inner self-correction
loop (retry on failed verification) and Phase 4 strategy adaptation (which
execution pattern to try, learned per task class). Goal Stack and Tracer
record what happened for observability (Phase 5).
"""

from __future__ import annotations

from dataclasses import dataclass

from src.evolution.skill_evolution import SkillEvolutionEngine
from src.evolution.strategy_adaptation import StrategyAdapter
from src.evolution.team_composition import TeamCompositionLearner
from src.goals.goal_stack import GoalStack
from src.llm.client import LLMClient
from src.llm.subagent import build_llm_subagent_pool
from src.loops.self_correction import inner_loop, meta_loop, outer_loop
from src.memory.api import Memory
from src.memory.semantic import SemanticGraph
from src.observability.tracer import Tracer
from src.orchestrator.orchestrator import Orchestrator
from src.safety.governance import HumanApprovalGate, SelfModificationPolicy
from src.safety.memory_guard import MemorySafetyGuard
from src.tasks.task_graph import TaskGraph

EXECUTION_PATTERNS = ["sequential", "parallel", "hierarchical"]

CRITICAL_ACTIONS = {
    "delete_memory",
    "modify_system_prompt",
    "self_update",
    "execute_untrusted_code",
}
SELF_MOD_ALLOWED_KEYS = {"max_retries", "temperature", "consolidate_every", "working_capacity"}


@dataclass
class EndToEndResult:
    task: str
    succeeded: bool
    strategy: str
    attempts: int
    orchestration: dict


class EndToEndAgent:
    def __init__(
        self,
        memory: Memory | None = None,
        use_llm: bool = False,
        llm_client: LLMClient | None = None,
    ) -> None:
        guard = MemorySafetyGuard(SemanticGraph(), min_confidence=0.4)  # will be wired to memory's semantic
        self.memory = memory or Memory(db_path="memory.db", safety_guard=guard)
        guard.semantic = self.memory.semantic  # wire to the real semantic graph
        self.goals = GoalStack()
        self.tracer = Tracer()
        self.strategy_adapter = StrategyAdapter(EXECUTION_PATTERNS)
        self.approval_gate = HumanApprovalGate(CRITICAL_ACTIONS)
        self.self_mod_policy = SelfModificationPolicy(SELF_MOD_ALLOWED_KEYS)
        self.task_graph = TaskGraph(db_path="tasks.db")
        self.skill_evolution = SkillEvolutionEngine(self.memory)
        self.team_learner = TeamCompositionLearner(self.memory.semantic)

        client = None
        if use_llm:
            client = llm_client or LLMClient()

        self.orchestrator = Orchestrator(memory=self.memory, llm_client=client)

        if client is not None:
            for role, agent in build_llm_subagent_pool(client, self.memory).items():
                self.orchestrator.register(role, agent)

    def run(self, task: str, task_class: str = "default", max_retries: int = 2) -> EndToEndResult:
        node = self.task_graph.add_task(task)
        self.tracer.record("task_graph", "task_added", {"id": node.id, "description": task})

        goal = self.goals.push(task, horizon="task")
        self.tracer.record("end_to_end", "goal_pushed", {"task": task})

        strategy = self.strategy_adapter.select(task_class)
        self.tracer.record("end_to_end", "strategy_selected", {"task_class": task_class, "strategy": strategy})

        last_orchestration: dict = {}

        def attempt(attempt_number: int) -> dict:
            nonlocal last_orchestration
            last_orchestration = self.orchestrator.run(task, pattern=strategy)
            self.tracer.record(
                "orchestrator", "attempt", {"attempt": attempt_number, "verified": last_orchestration["verified"]}
            )
            return last_orchestration

        def verify(orchestration: dict) -> bool:
            return bool(orchestration["verified"])

        outcome = inner_loop(act=attempt, verify=verify, max_retries=max_retries)

        self.strategy_adapter.observe(task_class, strategy, outcome.succeeded)
        self.goals.revise(goal, active=False)
        self.task_graph.set_status(node.id, "done" if outcome.succeeded else "failed")
        self.team_learner.record(task_class, list(self.orchestrator.pool.keys()), outcome.succeeded)
        self.tracer.record(
            "end_to_end", "completed", {"task": task, "succeeded": outcome.succeeded, "attempts": outcome.attempts}
        )

        return EndToEndResult(
            task=task,
            succeeded=outcome.succeeded,
            strategy=strategy,
            attempts=outcome.attempts,
            orchestration=last_orchestration,
        )

    def run_session(self, tasks: list[str], task_class: str = "default") -> list[EndToEndResult]:
        """Run multiple tasks with outer loop: reflect between tasks, switch strategies on failure."""
        results: list[EndToEndResult] = []

        def run_with_strategy(strategy: str) -> bool:
            for task in tasks:
                r = self.run(task, task_class=task_class)
                results.append(r)
                if not r.succeeded:
                    return False
            return True

        def reflect(success: bool) -> str | None:
            if not success:
                idx = EXECUTION_PATTERNS.index(self.strategy_adapter.select(task_class))
                return EXECUTION_PATTERNS[(idx + 1) % len(EXECUTION_PATTERNS)]
            return None

        outer_loop(run_episode=run_with_strategy, reflect=reflect, strategies=EXECUTION_PATTERNS, max_episodes=3)
        return results

    def close(self) -> dict:
        """Run meta loop: consolidate memory, evolve skills, persist semantic graph.
        Call at session end or before shutdown."""
        self.memory.consolidate()
        evolved = self.skill_evolution.extract_from_successful_episodes()
        self.skill_evolution.auto_combine_sequential_pairs()
        self.memory.semantic.save("semantic_graph.json")
        self.task_graph.close()
        self.memory.close()
        return {
            "consolidated": True,
            "skills_extracted": len(evolved),
            "semantic_persisted": "semantic_graph.json",
        }
