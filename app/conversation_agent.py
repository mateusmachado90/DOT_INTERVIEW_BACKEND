import re
from html.parser import HTMLParser
from urllib.parse import urlparse
from urllib.request import Request, urlopen

from langchain.agents import create_agent
from langchain.tools import tool

from app.config import get_settings
from app.models import ChatMessage, ChatMessageRole, Tutor


MAX_SOURCE_CHARS = 16_000
MAX_EXCERPT_CHARS = 2_500
MAX_HISTORY_MESSAGES = 8


class ConversationAgentError(RuntimeError):
    pass


class _TextExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self._chunks: list[str] = []
        self._skip_depth = 0

    def handle_starttag(self, tag: str, _attrs: list[tuple[str, str | None]]) -> None:
        if tag in {"script", "style", "nav", "footer", "header"}:
            self._skip_depth += 1

    def handle_endtag(self, tag: str) -> None:
        if tag in {"script", "style", "nav", "footer", "header"} and self._skip_depth:
            self._skip_depth -= 1

    def handle_data(self, data: str) -> None:
        if self._skip_depth:
            return
        text = " ".join(data.split())
        if text:
            self._chunks.append(text)

    def text(self) -> str:
        return "\n".join(self._chunks)


def run_tutor_conversation(
    *,
    tutor: Tutor,
    history: list[ChatMessage],
    user_message: str,
) -> str:
    tools = _build_knowledge_tools(tutor)
    agent = create_agent(
        model=get_settings().langchain_model,
        tools=tools,
        system_prompt=_build_system_prompt(tutor),
    )

    messages = _build_messages(history, user_message)
    try:
        result = agent.invoke({"messages": messages})
    except Exception as exc:  # pragma: no cover - depende do provedor LLM em runtime.
        raise ConversationAgentError("Falha ao executar o agente de conversacao.") from exc

    return _extract_final_answer(result)


def _build_system_prompt(tutor: Tutor) -> str:
    return "\n".join(
        [
            tutor.system_prompt,
            "",
            "Voce esta em uma conversa de tutoria.",
            "Decida quando usar as ferramentas disponiveis para consultar as fontes do tutor.",
            "Nao use estrategia de RAG, embeddings, banco vetorial ou indice vetorial externo.",
            "Quando usar uma fonte, mencione quais fontes ajudaram na resposta.",
            "Se as fontes nao forem suficientes, diga isso claramente e responda apenas com o que for seguro.",
        ]
    )


def _build_messages(history: list[ChatMessage], user_message: str) -> list[dict[str, str]]:
    recent_history = history[-MAX_HISTORY_MESSAGES:]
    messages = [
        {"role": message.role.value, "content": message.content}
        for message in recent_history
        if message.role in {ChatMessageRole.USER, ChatMessageRole.ASSISTANT}
    ]
    messages.append({"role": "user", "content": user_message})
    return messages


def _build_knowledge_tools(tutor: Tutor) -> list:
    enabled_sources = [source for source in tutor.sources if source.enabled]
    sources_by_name = {source.name.lower(): source for source in enabled_sources}

    @tool
    def listar_fontes_disponiveis() -> str:
        """Lista as fontes de conhecimento habilitadas para o tutor."""
        if not enabled_sources:
            return "Nenhuma fonte habilitada para este tutor."
        return "\n".join(
            f"- {source.name} ({source.type.value}): {source.location}"
            for source in enabled_sources
        )

    @tool
    def buscar_trechos_na_fonte(nome_da_fonte: str, consulta: str) -> str:
        """Busca trechos textuais em uma fonte URL do tutor usando correspondencia lexical simples."""
        source = sources_by_name.get(nome_da_fonte.lower())
        if source is None:
            available = ", ".join(source.name for source in enabled_sources) or "nenhuma"
            return f"Fonte nao encontrada. Fontes disponiveis: {available}."

        text = _load_source_text(source.location)
        return _find_relevant_excerpt(text, consulta)

    @tool
    def compilar_contexto_das_fontes(consulta: str) -> str:
        """Compila trechos das fontes habilitadas sem usar embeddings ou banco vetorial."""
        if not enabled_sources:
            return "Nenhuma fonte habilitada para compilar contexto."

        chunks = []
        for source in enabled_sources:
            text = _load_source_text(source.location)
            excerpt = _find_relevant_excerpt(text, consulta)
            chunks.append(f"Fonte: {source.name}\nURL: {source.location}\nTrecho:\n{excerpt}")

        return "\n\n---\n\n".join(chunks)

    return [listar_fontes_disponiveis, buscar_trechos_na_fonte, compilar_contexto_das_fontes]


def _load_source_text(location: str) -> str:
    parsed = urlparse(location)
    if parsed.scheme not in {"http", "https"}:
        return f"Tipo de fonte ainda nao suportado para leitura automatica: {location}"

    request = Request(location, headers={"User-Agent": "DOT-Interview-Tutor-MVP/1.0"})
    try:
        with urlopen(request, timeout=10) as response:
            raw_html = response.read(MAX_SOURCE_CHARS).decode("utf-8", errors="ignore")
    except OSError as exc:
        return f"Nao foi possivel ler a fonte {location}: {exc}"

    parser = _TextExtractor()
    parser.feed(raw_html)
    return parser.text()


def _find_relevant_excerpt(text: str, query: str) -> str:
    normalized_text = " ".join(text.split())
    if not normalized_text:
        return "Nenhum texto legivel encontrado na fonte."

    terms = [term.lower() for term in re.findall(r"\w+", query) if len(term) > 3]
    lower_text = normalized_text.lower()
    positions = [lower_text.find(term) for term in terms if lower_text.find(term) >= 0]
    center = min(positions) if positions else 0
    start = max(center - MAX_EXCERPT_CHARS // 2, 0)
    end = min(start + MAX_EXCERPT_CHARS, len(normalized_text))
    return normalized_text[start:end]


def _extract_final_answer(result: dict) -> str:
    messages = result.get("messages", [])
    if not messages:
        return "Nao foi possivel gerar uma resposta."

    content = getattr(messages[-1], "content", "")
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "\n".join(
            block.get("text", str(block)) if isinstance(block, dict) else str(block)
            for block in content
        )
    return str(content)
