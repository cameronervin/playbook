from __future__ import annotations

from types import SimpleNamespace
from uuid import UUID, uuid4

import pytest
from langgraph.checkpoint.memory import InMemorySaver

from app.agents.executors.conversation_title_executor import ConversationTitleExecutor


class CapturingGraph:
    def __init__(self) -> None:
        self.config: dict[str, object] | None = None

    async def ainvoke(
        self,
        input: dict[str, object],
        config: dict[str, object] | None = None,
    ) -> dict[str, str]:
        self.config = config
        return {"conversation_title": "Captured Title"}


class FakeMessageRepository:
    def __init__(self, *, task_id: str, provisional_title: str) -> None:
        self.task_id = task_id
        self.provisional_title = provisional_title

    async def get(self, message_id: UUID) -> SimpleNamespace:
        return SimpleNamespace(
            status="complete",
            message_metadata={
                "task_id": self.task_id,
                "is_first_turn": True,
                "provisional_title": self.provisional_title,
            },
        )


class FakeConversationRepository:
    def __init__(self, *, title: str) -> None:
        self.title = title

    async def get_for_athlete(self, **_: object) -> SimpleNamespace:
        return SimpleNamespace(title=self.title)


@pytest.mark.asyncio
async def test_conversation_title_executor_passes_checkpointer_config(
    test_settings,
) -> None:
    task_id = "task-title-config"
    provisional_title = "Can I accept this NIL deal"
    conversation_id = uuid4()
    athlete_user_id = uuid4()
    user_message_id = uuid4()
    assistant_message_id = uuid4()
    organization_id = uuid4()
    graph = CapturingGraph()

    def graph_factory(**_: object) -> CapturingGraph:
        return graph

    executor = ConversationTitleExecutor(
        session=object(),
        title_model=object(),
        settings=test_settings,
        checkpointer=InMemorySaver(),
        graph_factory=graph_factory,
    )
    executor.message_repo = FakeMessageRepository(
        task_id=task_id,
        provisional_title=provisional_title,
    )
    executor.conversation_repo = FakeConversationRepository(title=provisional_title)

    title = await executor.execute(
        task_id=task_id,
        conversation_id=conversation_id,
        athlete_user_id=athlete_user_id,
        user_message_id=user_message_id,
        assistant_message_id=assistant_message_id,
        organization_id=organization_id,
    )

    assert title == "Captured Title"
    assert graph.config is not None
    assert graph.config["recursion_limit"] == test_settings.AGENT_GRAPH_RECURSION_LIMIT
    configurable = graph.config["configurable"]
    assert configurable["thread_id"] == str(conversation_id)
    assert configurable["phase"] == "title"
    assert configurable["mode"] == "conversation_title"
    assert configurable["checkpoint_ns"] == f"conversation_title:{assistant_message_id}"
    assert configurable["task_id"] == task_id
    assert configurable["assistant_message_id"] == str(assistant_message_id)
    assert configurable["organization_id"] == str(organization_id)
    assert configurable["user_message_id"] == str(user_message_id)
