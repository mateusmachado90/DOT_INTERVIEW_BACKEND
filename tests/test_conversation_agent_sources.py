import json
import sys
import types
import unittest
from unittest.mock import patch


settings = types.SimpleNamespace(
    conversation_agent_name="test-agent",
    conversation_agent_version="1.0",
)

models_module = types.ModuleType("app.models")
models_module.ChatMessage = object
models_module.ChatMessageRole = types.SimpleNamespace(USER="user", ASSISTANT="assistant")
models_module.Tutor = object
sys.modules.setdefault("app.models", models_module)

config_module = types.ModuleType("app.config")
config_module.get_settings = lambda: settings
sys.modules.setdefault("app.config", config_module)

langchain_agents = types.ModuleType("langchain.agents")
langchain_agents.create_agent = lambda *args, **kwargs: None
sys.modules.setdefault("langchain.agents", langchain_agents)

langchain_chat_models = types.ModuleType("langchain.chat_models")
langchain_chat_models.init_chat_model = lambda *args, **kwargs: None
sys.modules.setdefault("langchain.chat_models", langchain_chat_models)

langchain_tools = types.ModuleType("langchain.tools")
langchain_tools.tool = lambda func: func
sys.modules.setdefault("langchain.tools", langchain_tools)

from app import conversation_agent  # noqa: E402


class _FakeResponse:
    def __init__(self, body: str) -> None:
        self._body = body.encode("utf-8")

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback) -> None:
        return None

    def read(self, _size: int) -> bytes:
        return self._body


class SourceLoadingTests(unittest.TestCase):
    def test_wikipedia_url_uses_plain_text_extract_api(self) -> None:
        payload = {
            "query": {
                "pages": {
                    "123": {
                        "extract": (
                            "A Revolucao Francesa foi um periodo de intensa mudanca "
                            "politica e social na Franca."
                        )
                    }
                }
            }
        }
        requests = []

        def fake_urlopen(request, timeout):
            requests.append(request)
            return _FakeResponse(json.dumps(payload))

        with patch.object(conversation_agent, "urlopen", side_effect=fake_urlopen):
            text = conversation_agent._load_source_text(
                "https://pt.wikipedia.org/wiki/Revolu%C3%A7%C3%A3o_Francesa"
            )

        self.assertIn("Revolucao Francesa", text)
        self.assertIn("/w/api.php?", requests[0].full_url)
        self.assertIn("explaintext=1", requests[0].full_url)

    def test_generic_html_loader_skips_head_and_reads_body_text(self) -> None:
        html = (
            "<html><head><title>Revolucao Francesa - Wikipedia</title>"
            f"<style>{'x' * 20_000}</style></head>"
            "<body><main><h1>Revolucao Francesa</h1>"
            "<p>Conteudo textual sobre jacobinos, girondinos e Assembleia Nacional.</p>"
            "</main></body></html>"
        )

        with patch.object(conversation_agent, "urlopen", return_value=_FakeResponse(html)):
            text = conversation_agent._load_source_text("https://example.com/revolucao")

        self.assertNotIn("Wikipedia", text)
        self.assertIn("jacobinos", text)
        self.assertIn("Assembleia Nacional", text)

    def test_wikipedia_loader_falls_back_to_html_when_api_has_no_extract(self) -> None:
        html = (
            "<html><head><title>Pagina</title></head>"
            "<body><p>Texto do corpo carregado pelo fallback HTML.</p></body></html>"
        )

        with patch.object(
            conversation_agent,
            "urlopen",
            side_effect=[
                _FakeResponse(json.dumps({"query": {"pages": {"123": {}}}})),
                _FakeResponse(html),
            ],
        ):
            text = conversation_agent._load_source_text("https://pt.wikipedia.org/wiki/Teste")

        self.assertIn("fallback HTML", text)


if __name__ == "__main__":
    unittest.main()
