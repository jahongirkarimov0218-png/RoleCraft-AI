"""The OpenAI-compatible adapter against a real HTTP server on loopback, plus the environment settings.
No external network is used. The API key must never leak: not in errors, reprs, settings views or redirects."""

import json
import re
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

from promptgraphify.llm import (
    MAX_RESPONSE_BYTES,
    LlmConfigError,
    LlmError,
    LlmSettings,
    OpenAICompatibleAdapter,
    get_adapter,
    mask_secrets,
)

KEY = "sk-test-0123456789abcdefSECRET"


class Server:
    """Records requests; ``behaviour(handler)`` decides the answer."""

    def __init__(self, behaviour):
        self.requests: list[dict] = []
        outer = self

        class H(BaseHTTPRequestHandler):
            def do_POST(self):  # noqa: N802
                length = int(self.headers.get("content-length", 0))
                body = self.rfile.read(length)
                outer.requests.append(
                    {
                        "path": self.path,
                        "headers": {k.lower(): v for k, v in self.headers.items()},
                        "body": json.loads(body),
                    }
                )
                behaviour(self)

            def log_message(self, *_):  # keep test output clean
                pass

        self.httpd = ThreadingHTTPServer(("127.0.0.1", 0), H)
        self.url = f"http://127.0.0.1:{self.httpd.server_address[1]}/v1"
        threading.Thread(target=self.httpd.serve_forever, daemon=True).start()

    def close(self):
        self.httpd.shutdown()
        self.httpd.server_close()


def reply(h, status, payload, headers=None):
    raw = payload if isinstance(payload, bytes) else json.dumps(payload).encode()
    h.send_response(status)
    h.send_header("content-type", "application/json")
    h.send_header("content-length", str(len(raw)))
    for k, v in (headers or {}).items():
        h.send_header(k, v)
    h.end_headers()
    h.wfile.write(raw)


def completion(text):
    return {"choices": [{"message": {"role": "assistant", "content": text}}]}


@pytest.fixture()
def serve():
    servers = []

    def start(behaviour):
        s = Server(behaviour)
        servers.append(s)
        return s

    yield start
    for s in servers:
        s.close()


def adapter(server, key=KEY, timeout=5.0):
    return OpenAICompatibleAdapter(LlmSettings("openai-compatible", server.url, "m-1", key, timeout))


def test_a_successful_call_sends_the_documented_request(serve):
    s = serve(lambda h: reply(h, 200, completion('{"nodes": [], "edges": []}')))
    out = adapter(s).complete("SYS", "USER")
    assert out == '{"nodes": [], "edges": []}'
    (req,) = s.requests
    assert req["path"] == "/v1/chat/completions"
    assert req["headers"]["authorization"] == f"Bearer {KEY}"
    assert req["body"] == {
        "model": "m-1",
        "temperature": 0,
        "response_format": {"type": "json_object"},
        "messages": [{"role": "system", "content": "SYS"}, {"role": "user", "content": "USER"}],
    }


def test_no_key_means_no_authorization_header(serve):
    s = serve(lambda h: reply(h, 200, completion("{}")))
    adapter(s, key=None).complete("a", "b")
    assert "authorization" not in s.requests[0]["headers"]


@pytest.mark.parametrize("key", [KEY, "tok_ABCDEFGH12345678"])  # one shaped like an OpenAI key, one not
def test_an_error_body_that_echoes_the_key_is_masked(serve, key):
    s = serve(lambda h: reply(h, 401, {"error": {"message": f"Incorrect API key provided: {key}. See docs."}}))
    with pytest.raises(LlmError) as e:
        adapter(s, key=key).complete("a", "b")
    text = str(e.value)
    assert "HTTP 401" in text and key not in text and key[-8:] not in text and "***" in text


def test_a_redirect_is_not_followed_so_the_key_cannot_reach_another_host(serve):
    other = serve(lambda h: reply(h, 200, completion("{}")))
    s = serve(lambda h: reply(h, 307, {}, {"location": other.url + "/chat/completions"}))
    with pytest.raises(LlmError, match="redirect"):
        adapter(s).complete("a", "b")
    assert other.requests == [] and len(s.requests) == 1


def test_a_slow_provider_times_out_with_a_clear_message(serve):
    s = serve(lambda h: (time.sleep(2), reply(h, 200, completion("{}"))))
    started = time.monotonic()
    with pytest.raises(LlmError, match="did not answer within 0.3 s"):
        adapter(s, timeout=0.3).complete("a", "b")
    assert time.monotonic() - started < 1.9


def test_an_oversized_answer_is_refused(serve):
    s = serve(lambda h: reply(h, 200, b"x" * (MAX_RESPONSE_BYTES + 10)))
    with pytest.raises(LlmError, match="larger than the allowed size"):
        adapter(s).complete("a", "b")


@pytest.mark.parametrize(
    "payload",
    [b"not json", {"choices": []}, {"choices": [{"message": {}}]}, {"choices": [{"message": {"content": 5}}]}, [1]],
)
def test_an_answer_of_the_wrong_shape_is_an_error(serve, payload):
    s = serve(lambda h: reply(h, 200, payload))
    with pytest.raises(LlmError, match="expected shape"):
        adapter(s).complete("a", "b")


def test_a_closed_port_is_an_error_without_the_key():
    dead = LlmSettings("openai-compatible", "http://127.0.0.1:1/v1", "m", KEY, 2.0)
    with pytest.raises(LlmError) as e:
        OpenAICompatibleAdapter(dead).complete("a", "b")
    assert "cannot reach the provider" in str(e.value) and KEY not in str(e.value)


# ------------------------------------------------------------------------------------------ settings
ENV = {
    "PROMPTGRAPHIFY_LLM_PROVIDER": "openai-compatible",
    "PROMPTGRAPHIFY_LLM_MODEL": "gpt-test",
    "PROMPTGRAPHIFY_LLM_API_KEY": KEY,
}


def test_without_a_provider_the_llm_is_off():
    assert LlmSettings.from_env({}) is None and get_adapter({}) is None
    assert LlmSettings.from_env({"PROMPTGRAPHIFY_LLM_API_KEY": KEY}) is None  # a key alone enables nothing


def test_a_configured_provider_yields_an_adapter_with_a_public_view_without_the_key():
    s = LlmSettings.from_env(ENV)
    assert s is not None and (s.model, s.base_url, s.timeout_s) == ("gpt-test", "https://api.openai.com/v1", 30.0)
    assert s.public() == {
        "provider": "openai-compatible",
        "endpoint": "api.openai.com",
        "model": "gpt-test",
        "api_key": "set",
    }
    assert KEY not in repr(s) and KEY not in json.dumps(s.public())
    a = get_adapter(ENV)
    assert a is not None and (a.name, a.model, a.endpoint, a.timeout_s) == (
        "openai-compatible",
        "gpt-test",
        "api.openai.com",
        30.0,
    )
    assert KEY not in repr(a) and KEY not in str(vars(a).get("_s", ""))


@pytest.mark.parametrize(
    ("change", "message"),
    [
        ({"PROMPTGRAPHIFY_LLM_PROVIDER": "anthropic"}, "must be 'openai-compatible'"),
        ({"PROMPTGRAPHIFY_LLM_MODEL": ""}, "MODEL is required"),
        ({"PROMPTGRAPHIFY_LLM_BASE_URL": "ftp://x/v1"}, "http(s) URL"),
        ({"PROMPTGRAPHIFY_LLM_BASE_URL": "not a url"}, "http(s) URL"),
        ({"PROMPTGRAPHIFY_LLM_BASE_URL": "https://user:pw@api.example.com/v1"}, "must not contain credentials"),
        ({"PROMPTGRAPHIFY_LLM_BASE_URL": "http://api.example.com/v1"}, "must use https"),
        ({"PROMPTGRAPHIFY_LLM_TIMEOUT_S": "soon"}, "number of seconds"),
        ({"PROMPTGRAPHIFY_LLM_TIMEOUT_S": "0"}, "between 0 and 300"),
        ({"PROMPTGRAPHIFY_LLM_TIMEOUT_S": "301"}, "between 0 and 300"),
    ],
)
def test_bad_configuration_names_the_variable_never_a_value(change, message):
    with pytest.raises(LlmConfigError, match=re.escape(message)) as e:
        LlmSettings.from_env({**ENV, **change})
    assert KEY not in str(e.value) and "pw@" not in str(e.value)


@pytest.mark.parametrize("url", ["http://127.0.0.1:11434/v1", "http://localhost:1234/v1", "http://[::1]:8080/v1"])
def test_a_local_server_may_use_plain_http(url):
    assert LlmSettings.from_env({**ENV, "PROMPTGRAPHIFY_LLM_BASE_URL": url}) is not None


def test_a_local_server_needs_no_key():
    env = {k: v for k, v in ENV.items() if k != "PROMPTGRAPHIFY_LLM_API_KEY"}
    s = LlmSettings.from_env({**env, "PROMPTGRAPHIFY_LLM_BASE_URL": "http://localhost:11434/v1"})
    assert s is not None and s.api_key is None and s.public()["api_key"] == "not set"


# ------------------------------------------------------------------------------------------ masking
def test_mask_secrets_removes_known_secrets_and_key_shapes():
    assert mask_secrets(f"key={KEY} end", [KEY]) == "key=*** end"
    assert "sk-abcdefghijk" not in mask_secrets("used sk-abcdefghijk here")
    assert "Bearer abc.def-1234567" not in mask_secrets("Authorization: Bearer abc.def-1234567")
    assert mask_secrets("nothing to hide") == "nothing to hide" and mask_secrets("x", [None, "", "ab"]) == "x"
