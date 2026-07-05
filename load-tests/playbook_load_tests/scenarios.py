"""Locust user classes for Playbook load profiles."""

from __future__ import annotations

import random
import time
from typing import ClassVar

from locust import HttpUser, between, constant, tag, task
from locust.exception import StopUser

from playbook_load_tests.auth import BearerTokenPool, callback_path_from_authorization_url
from playbook_load_tests.config import PlaybookLoadConfig, StreamMode
from playbook_load_tests.runtime import get_config, record_stream_duration
from playbook_load_tests.sse import iter_sse_events

STREAM_TIMEOUT_SECONDS = 75
ATHLETE_PROMPTS = (
    "Can I accept a sponsored social post after compliance review?",
    "What should I do before signing an NIL agreement?",
    "Where do I find the department process for travel reimbursement?",
)
ADMIN_PROMPTS = (
    "What topics are athletes asking about this week?",
    "Summarize unanswered NIL and compliance questions.",
    "Which risk labels need administrator attention?",
)


class PlaybookUser(HttpUser):
    """Base class with shared config/auth helpers."""

    abstract = True
    wait_time = between(1, 3)
    persona: ClassVar[str | None] = None
    token_pool_name: ClassVar[str | None] = None

    def on_start(self) -> None:
        self.config = get_config()
        self.auth_headers = self._resolve_auth_headers(self.config)

    def _resolve_auth_headers(self, config: PlaybookLoadConfig) -> dict[str, str]:
        if not self.token_pool_name:
            return {}
        token_pool = getattr(config, self.token_pool_name)
        if isinstance(token_pool, BearerTokenPool) and token_pool:
            return token_pool.next_header()
        if config.is_local and self.persona:
            self._dev_login(self.persona)
            return {}
        raise StopUser(
            f"{self.__class__.__name__} needs {self.token_pool_name} or local dev auth"
        )

    def _dev_login(self, persona: str) -> None:
        with self.client.get(
            "/api/v1/auth/dev/login",
            params={"persona": persona},
            name="GET /api/v1/auth/dev/login",
            catch_response=True,
        ) as response:
            if response.status_code != 200:
                response.failure("dev auth login unavailable")
                raise StopUser("dev auth login unavailable")
            authorization_url = response.json().get("authorization_url")
            if not isinstance(authorization_url, str) or not authorization_url:
                response.failure("dev auth login returned no callback URL")
                raise StopUser("dev auth login returned no callback URL")

        callback_path = callback_path_from_authorization_url(authorization_url)
        with self.client.get(
            callback_path,
            headers={"Accept": "text/html"},
            name="GET /api/v1/auth/dev/callback",
            allow_redirects=False,
            catch_response=True,
        ) as response:
            if response.status_code not in {200, 303}:
                response.failure("dev auth callback failed")
                raise StopUser("dev auth callback failed")

    def _get(self, path: str, *, name: str, headers: dict[str, str] | None = None) -> None:
        merged_headers = {**self.auth_headers, **(headers or {})}
        self.client.get(path, headers=merged_headers, name=name)

    def _post_json(
        self,
        path: str,
        *,
        name: str,
        payload: dict[str, object],
        headers: dict[str, str] | None = None,
    ):
        merged_headers = {**self.auth_headers, **(headers or {})}
        return self.client.post(path, json=payload, headers=merged_headers, name=name)

    def _wait_for_stream(self, stream_url: str, *, name: str) -> None:
        start = time.perf_counter()
        with self.client.get(
            stream_url,
            headers=self.auth_headers,
            name=name,
            stream=True,
            timeout=STREAM_TIMEOUT_SECONDS,
            catch_response=True,
        ) as response:
            if response.status_code != 200:
                response.failure("stream endpoint did not return 200")
                return
            for event in iter_sse_events(response.iter_lines(decode_unicode=True)):
                if event.event == "error":
                    response.failure("stream returned terminal error")
                    return
                if event.event == "complete":
                    elapsed_ms = (time.perf_counter() - start) * 1000
                    record_stream_duration(elapsed_ms)
                    response.success()
                    return
            response.failure("stream ended without terminal event")


class PublicReadinessUser(PlaybookUser):
    """Unauthenticated health/readiness checks."""

    @tag("cheap", "public")
    @task(3)
    def health(self) -> None:
        self._get("/api/v1/health", name="GET /api/v1/health")

    @tag("cheap", "public")
    @task(2)
    def ready(self) -> None:
        self._get("/api/v1/ready", name="GET /api/v1/ready")

    @tag("cheap", "public")
    @task(1)
    def auth_providers(self) -> None:
        self._get("/api/v1/auth/providers", name="GET /api/v1/auth/providers")


class AthleteReadOnlyUser(PlaybookUser):
    """Authenticated athlete read-only API checks."""

    persona = "athlete"
    token_pool_name = "athlete_tokens"

    @tag("cheap", "athlete")
    @task(2)
    def current_user(self) -> None:
        self._get("/api/v1/users/me", name="GET /api/v1/users/me")

    @tag("cheap", "athlete")
    @task(3)
    def conversations(self) -> None:
        self._get(
            "/api/v1/conversations?limit=20&offset=0",
            name="GET /api/v1/conversations",
        )


class AdminReadOnlyUser(PlaybookUser):
    """Authenticated admin read-only API checks."""

    persona = "admin"
    token_pool_name = "admin_tokens"

    @tag("cheap", "admin")
    @task(2)
    def analytics_summary(self) -> None:
        self._get(
            "/api/v1/admin/analytics/summary?window=7d",
            name="GET /api/v1/admin/analytics/summary",
        )

    @tag("cheap", "admin")
    @task(2)
    def analytics_queries(self) -> None:
        self._get(
            "/api/v1/admin/analytics/queries?window=7d&limit=20&offset=0",
            name="GET /api/v1/admin/analytics/queries",
        )

    @tag("cheap", "admin")
    @task(1)
    def kb_collections(self) -> None:
        self._get("/api/v1/admin/kb/collections", name="GET /api/v1/admin/kb/collections")

    @tag("cheap", "admin")
    @task(1)
    def kb_documents(self) -> None:
        self._get(
            "/api/v1/admin/kb/documents?limit=20&offset=0",
            name="GET /api/v1/admin/kb/documents",
        )


class AthleteChatEnqueueUser(PlaybookUser):
    """Live athlete chat enqueue scenario with optional SSE wait."""

    persona = "athlete"
    token_pool_name = "athlete_tokens"
    wait_time = between(4, 8)

    @tag("live", "athlete-chat")
    @task
    def start_conversation(self) -> None:
        response = self._post_json(
            "/api/v1/conversations",
            name="POST /api/v1/conversations",
            payload={"content": random.choice(ATHLETE_PROMPTS)},
        )
        if self.config.stream_mode != StreamMode.WAIT or response.status_code != 202:
            return
        stream_url = response.json().get("stream_url")
        if isinstance(stream_url, str) and stream_url:
            self._wait_for_stream(
                stream_url,
                name="GET /api/v1/conversations/[id]/messages/[id]/stream",
            )


class AdminChatUser(PlaybookUser):
    """Live admin chat enqueue scenario with optional SSE wait."""

    persona = "admin"
    token_pool_name = "admin_tokens"
    wait_time = between(5, 10)

    def on_start(self) -> None:
        super().on_start()
        self.session_id: str | None = None

    @tag("live", "admin-chat")
    @task
    def ask_admin_question(self) -> None:
        if self.session_id is None:
            response = self._post_json(
                "/api/v1/admin/chat/sessions",
                name="POST /api/v1/admin/chat/sessions",
                payload={"title": "Load Test Admin Session"},
            )
            if response.status_code != 201:
                return
            session_id = response.json().get("id")
            self.session_id = session_id if isinstance(session_id, str) else None
        if self.session_id is None:
            return

        response = self._post_json(
            f"/api/v1/admin/chat/sessions/{self.session_id}/messages",
            name="POST /api/v1/admin/chat/sessions/[id]/messages",
            payload={"question": random.choice(ADMIN_PROMPTS), "window": "7d"},
        )
        if self.config.stream_mode != StreamMode.WAIT or response.status_code != 202:
            return
        stream_url = response.json().get("stream_url")
        if isinstance(stream_url, str) and stream_url:
            self._wait_for_stream(
                stream_url,
                name="GET /api/v1/admin/chat/sessions/[id]/messages/[id]/stream",
            )


class KBSearchUser(PlaybookUser):
    """Direct KB-service search scenario for staging-only service testing."""

    wait_time = between(2, 5)

    def on_start(self) -> None:
        self.config = get_config()
        if not (
            self.config.kb_base_url
            and self.config.kb_api_secret
            and self.config.organization_id
        ):
            raise StopUser("KB search scenario requires KB URL, token, and organization ID")
        self.auth_headers = {"Authorization": f"Bearer {self.config.kb_api_secret}"}

    @tag("live", "kb")
    @task
    def search(self) -> None:
        self.client.post(
            f"{self.config.kb_base_url}/api/kb/search",
            headers=self.auth_headers,
            json={
                "query": "What should athletes do before signing an NIL agreement?",
                "organization_id": self.config.organization_id,
                "visibility_context": {"role": "athlete"},
                "source_types": ["admin_upload"],
                "limit": 5,
                "score_threshold": 0.0,
            },
            name="POST /api/kb/search",
        )


class RateLimitProbeUser(PlaybookUser):
    """Purposefully hot read-only probe where 429 is expected and allowed."""

    persona = "athlete"
    token_pool_name = "athlete_tokens"
    wait_time = constant(0.1)

    @tag("rate-limit")
    @task
    def conversations_burst(self) -> None:
        self._get(
            "/api/v1/conversations?limit=1&offset=0",
            name="GET /api/v1/conversations",
        )
