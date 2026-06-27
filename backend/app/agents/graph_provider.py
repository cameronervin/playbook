"""Process-local cache for compiled Playbook agent graphs."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from langchain_core.language_models import BaseChatModel

from app.agents.builders.graphs_builder import (
    compile_athlete_chat_graph,
    compile_conversation_title_graph,
)
from app.core.config import Settings


@dataclass(frozen=True, slots=True)
class AgentGraphProviderKey:
    """Identity tuple for a worker-process graph provider."""

    settings_signature: str
    chat_model_id: int
    title_model_id: int
    checkpointer_id: int | None

    @classmethod
    def from_dependencies(
        cls,
        *,
        chat_model: BaseChatModel,
        title_model: BaseChatModel,
        settings: Settings,
        checkpointer: Any | None,
    ) -> AgentGraphProviderKey:
        """Return the cache key for these graph dependencies."""
        return cls(
            settings_signature=settings.model_dump_json(),
            chat_model_id=id(chat_model),
            title_model_id=id(title_model),
            checkpointer_id=id(checkpointer) if checkpointer is not None else None,
        )


class AgentGraphProvider:
    """Lazily compile and reuse static agent graphs for one worker process."""

    def __init__(
        self,
        *,
        chat_model: BaseChatModel,
        title_model: BaseChatModel,
        settings: Settings,
        checkpointer: Any | None,
    ) -> None:
        self.chat_model = chat_model
        self.title_model = title_model
        self.settings = settings
        self.checkpointer = checkpointer
        self._athlete_chat_graph: Any | None = None
        self._conversation_title_graph: Any | None = None

    def athlete_chat_graph(self) -> Any:
        """Return the cached compiled athlete chat graph."""
        if self._athlete_chat_graph is None:
            self._athlete_chat_graph = compile_athlete_chat_graph(
                chat_model=self.chat_model,
                checkpointer=self.checkpointer,
                app_settings=self.settings,
            )
        return self._athlete_chat_graph

    def conversation_title_graph(self) -> Any:
        """Return the cached compiled conversation title graph."""
        if self._conversation_title_graph is None:
            self._conversation_title_graph = compile_conversation_title_graph(
                title_model=self.title_model,
                checkpointer=self.checkpointer,
                app_settings=self.settings,
            )
        return self._conversation_title_graph


class AgentGraphProviderCache:
    """Process-local cache for a dependency-matched graph provider."""

    def __init__(self) -> None:
        self._provider: AgentGraphProvider | None = None
        self._key: AgentGraphProviderKey | None = None

    def get_or_create(
        self,
        *,
        chat_model: BaseChatModel,
        title_model: BaseChatModel,
        settings: Settings,
        checkpointer: Any | None,
    ) -> AgentGraphProvider:
        """Return the current provider or replace it when dependencies change."""
        key = AgentGraphProviderKey.from_dependencies(
            chat_model=chat_model,
            title_model=title_model,
            settings=settings,
            checkpointer=checkpointer,
        )
        if self._provider is None or self._key != key:
            self._provider = AgentGraphProvider(
                chat_model=chat_model,
                title_model=title_model,
                settings=settings,
                checkpointer=checkpointer,
            )
            self._key = key
        return self._provider

    def clear(self) -> None:
        """Clear cached graph provider state."""
        self._provider = None
        self._key = None
