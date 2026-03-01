"""
Vercel serverless function — replaces the FastAPI /api/create-session endpoint.
Place this file at: managed-chatkit/api/create-session.py
"""

from __future__ import annotations

import json
import os
import uuid
from http.server import BaseHTTPRequestHandler
from typing import Any, Mapping

import httpx

DEFAULT_CHATKIT_BASE = "https://api.openai.com"
SESSION_COOKIE_NAME = "chatkit_session_id"
SESSION_COOKIE_MAX_AGE_SECONDS = 60 * 60 * 24 * 30  # 30 days


class handler(BaseHTTPRequestHandler):

    def do_OPTIONS(self):
        """Handle CORS preflight."""
        self.send_response(200)
        self._send_cors_headers()
        self.end_headers()

    def do_POST(self):
        # --- Read body ---
        content_length = int(self.headers.get("Content-Length", 0))
        raw_body = self.rfile.read(content_length) if content_length else b""
        body = parse_json_bytes(raw_body)

        # --- API key ---
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            return self._respond({"error": "Missing OPENAI_API_KEY environment variable"}, 500)

        # --- Workflow ID ---
        workflow_id = resolve_workflow_id(body)
        if not workflow_id:
            return self._respond({"error": "Missing workflow id"}, 400)

        # --- User / session cookie ---
        cookie_header = self.headers.get("Cookie", "")
        existing_session = extract_cookie(cookie_header, SESSION_COOKIE_NAME)
        user_id = existing_session or str(uuid.uuid4())
        set_new_cookie = None if existing_session else user_id

        # --- Call OpenAI ChatKit API ---
        api_base = os.getenv("CHATKIT_API_BASE") or os.getenv("VITE_CHATKIT_API_BASE") or DEFAULT_CHATKIT_BASE

        try:
            with httpx.Client(base_url=api_base, timeout=10.0) as client:
                upstream = client.post(
                    "/v1/chatkit/sessions",
                    headers={
                        "Authorization": f"Bearer {api_key}",
                        "OpenAI-Beta": "chatkit_beta=v1",
                        "Content-Type": "application/json",
                    },
                    json={"workflow": {"id": workflow_id}, "user": user_id},
                )
        except httpx.RequestError as error:
            return self._respond({"error": f"Failed to reach ChatKit API: {error}"}, 502, set_new_cookie)

        payload = parse_json_response(upstream)

        if not upstream.is_success:
            message = None
            if isinstance(payload, Mapping):
                message = payload.get("error")
            message = message or upstream.reason_phrase or "Failed to create session"
            return self._respond({"error": message}, upstream.status_code, set_new_cookie)

        client_secret = None
        expires_after = None
        if isinstance(payload, Mapping):
            client_secret = payload.get("client_secret")
            expires_after = payload.get("expires_after")

        if not client_secret:
            return self._respond({"error": "Missing client secret in response"}, 502, set_new_cookie)

        return self._respond(
            {"client_secret": client_secret, "expires_after": expires_after},
            200,
            set_new_cookie,
        )

    def _respond(self, payload: Mapping[str, Any], status_code: int, cookie_value: str | None = None):
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status_code)
        self._send_cors_headers()
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        if cookie_value:
            is_secure = (os.getenv("VERCEL_ENV") or "") == "production"
            secure_flag = "; Secure" if is_secure else ""
            self.send_header(
                "Set-Cookie",
                f"{SESSION_COOKIE_NAME}={cookie_value}; Max-Age={SESSION_COOKIE_MAX_AGE_SECONDS}; HttpOnly; SameSite=Lax; Path=/{secure_flag}",
            )
        self.end_headers()
        self.wfile.write(body)

    def _send_cors_headers(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization")
        self.send_header("Access-Control-Allow-Credentials", "true")


# ── Helpers ──────────────────────────────────────────────────────────────────

def parse_json_bytes(raw: bytes) -> Mapping[str, Any]:
    if not raw:
        return {}
    try:
        parsed = json.loads(raw)
        return parsed if isinstance(parsed, Mapping) else {}
    except json.JSONDecodeError:
        return {}


def parse_json_response(response: httpx.Response) -> Mapping[str, Any]:
    try:
        parsed = response.json()
        return parsed if isinstance(parsed, Mapping) else {}
    except Exception:
        return {}


def resolve_workflow_id(body: Mapping[str, Any]) -> str | None:
    workflow = body.get("workflow", {})
    workflow_id = None
    if isinstance(workflow, Mapping):
        workflow_id = workflow.get("id")
    workflow_id = workflow_id or body.get("workflowId")
    env_workflow = os.getenv("CHATKIT_WORKFLOW_ID") or os.getenv("VITE_CHATKIT_WORKFLOW_ID")
    if not workflow_id and env_workflow:
        workflow_id = env_workflow
    if workflow_id and isinstance(workflow_id, str) and workflow_id.strip():
        return workflow_id.strip()
    return None


def extract_cookie(cookie_header: str, name: str) -> str | None:
    for part in cookie_header.split(";"):
        part = part.strip()
        if part.startswith(f"{name}="):
            return part[len(f"{name}="):]
    return None
