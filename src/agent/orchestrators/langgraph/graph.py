from __future__ import annotations

from langgraph.graph import END, StateGraph

from agent.core.nodes.evaluate import evaluate
from agent.core.nodes.execute import execute
from agent.core.nodes.generate import generate
from agent.core.nodes.plan import plan
from agent.core.nodes.reflect import reflect
from agent.core.state import SessionState, SessionStatus
from agent.llm.client import LLMClient
from agent.persistence.db import save_session
from agent.sandbox.runner import SandboxRunner

NODE_PLAN = "plan"
NODE_GENERATE = "generate"
NODE_EXECUTE = "execute"
NODE_EVALUATE = "evaluate"
NODE_REFLECT = "reflect"

TERMINAL_STATUSES = {
    SessionStatus.SUCCEEDED,
    SessionStatus.FAILED,
    SessionStatus.ABORTED_BUDGET,
}


def _route_after(session: SessionState) -> str:
    if session.status in TERMINAL_STATUSES:
        return END
    status_to_node = {
        SessionStatus.PLANNING: NODE_PLAN,
        SessionStatus.GENERATING: NODE_GENERATE,
        SessionStatus.EXECUTING: NODE_EXECUTE,
        SessionStatus.EVALUATING: NODE_EVALUATE,
        SessionStatus.REFLECTING: NODE_REFLECT,
    }
    return status_to_node[session.status]


def build_graph(llm_client: LLMClient, sandbox_runner: SandboxRunner, persist: bool = True):
    graph = StateGraph(SessionState)

    async def plan_node(session: SessionState) -> SessionState:
        result = await plan(session, llm_client)
        if persist:
            save_session(result)
        return result

    async def generate_node(session: SessionState) -> SessionState:
        result = await generate(session, llm_client)
        if persist:
            save_session(result)
        return result

    def execute_node(session: SessionState) -> SessionState:
        result = execute(session, sandbox_runner)
        if persist:
            save_session(result)
        return result

    async def evaluate_node(session: SessionState) -> SessionState:
        result = await evaluate(session, llm_client)
        if persist:
            save_session(result)
        return result

    async def reflect_node(session: SessionState) -> SessionState:
        result = await reflect(session, llm_client)
        if persist:
            save_session(result)
        return result

    graph.add_node(NODE_PLAN, plan_node)
    graph.add_node(NODE_GENERATE, generate_node)
    graph.add_node(NODE_EXECUTE, execute_node)
    graph.add_node(NODE_EVALUATE, evaluate_node)
    graph.add_node(NODE_REFLECT, reflect_node)

    graph.set_entry_point(NODE_PLAN)

    graph.add_conditional_edges(NODE_PLAN, _route_after)
    graph.add_conditional_edges(NODE_GENERATE, _route_after)
    graph.add_conditional_edges(NODE_EXECUTE, _route_after)
    graph.add_conditional_edges(NODE_EVALUATE, _route_after)
    graph.add_conditional_edges(NODE_REFLECT, _route_after)

    return graph.compile()


class LangGraphOrchestrator:
    def __init__(self, llm_client: LLMClient | None = None, sandbox_runner: SandboxRunner | None = None) -> None:
        self._llm_client = llm_client or LLMClient()
        self._sandbox_runner = sandbox_runner or SandboxRunner()

    async def run(self, prompt: str, persist: bool = True) -> SessionState:
        session = SessionState(prompt=prompt, status=SessionStatus.PLANNING)
        compiled_graph = build_graph(self._llm_client, self._sandbox_runner, persist=persist)
        final_state = await compiled_graph.ainvoke(session)
        if isinstance(final_state, SessionState):
            return final_state
        return SessionState.model_validate(final_state)
