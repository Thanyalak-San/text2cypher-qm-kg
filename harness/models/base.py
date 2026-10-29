"""What every model adapter takes and returns (guide, Appendix A).

An adapter turns one request in the neutral format (system prompt, messages as in harness/context.py,
tools) into one API call and returns a ModelReply. API errors that may pass (rate limits, overload,
server errors, lost connections) are retried up to MAX_ATTEMPTS times with exponential backoff; if every
attempt fails, ApiFailure is raised and the runner re-queues the episode once.

Tools in the neutral format:
    {"name": str, "description": str, "parameters": <JSON schema of the arguments>}
"""

from __future__ import annotations

from dataclasses import dataclass, field

MAX_ATTEMPTS = 5
BACKOFF_S = (2, 4, 8, 16)       # waits before attempts 2–5


@dataclass
class ModelReply:
    text: str                                   # all text blocks joined ("" if none)
    tool_calls: list[dict]                      # [{"id", "name", "arguments"}], in order
    stop_reason: str                            # as the API reports it (Claude: end_turn, tool_use, max_tokens, ...)
    cut_off: bool                               # the reply hit the output limit (Claude max_tokens, GPT length);
                                                # the loop uses only this, so it works the same for every model
    input_tokens: int
    output_tokens: int
    cached_tokens: int                          # cache reads + writes; should be 0 for Claude (caching off)
    model_returned: str                         # model ID the API reports
    api_version: str
    request_id: str | None
    seconds: float                              # the successful attempt only
    attempts: int = 1
    retry_wait_s: float = 0.0                   # time spent waiting between failed attempts
    errors: list[str] = field(default_factory=list)   # messages of the failed attempts
    reasoning_tokens: int = 0                   # hidden reasoning inside output_tokens (GPT reports it; Claude 0)

    def as_message(self) -> dict:
        """The reply as a neutral assistant message, to append to the conversation."""
        return {"role": "assistant", "text": self.text or None, "tool_calls": self.tool_calls}


def request_settings(adapter, request: dict) -> dict:
    """The settings part of a request (model, limits, temperature, tool choice): prompt content left out."""
    content = getattr(adapter, "content_keys", ("system", "messages", "tools"))
    return {k: v for k, v in request.items() if k not in content}


class ApiFailure(RuntimeError):
    """Every attempt failed with a retryable error; the episode is re-queued once."""
