import json
import logging
import re
import time
from html.parser import HTMLParser
from urllib.parse import ParseResult, unquote, urlencode, urlparse
from urllib.request import Request, urlopen

from langchain.agents import create_agent
from langchain.chat_models import init_chat_model
from langchain.tools import tool

from app.config import get_settings
from app.models import ChatMessage, ChatMessageRole, Tutor


logger = logging.getLogger(__name__)

MAX_SOURCE_CHARS = 500_000
MAX_EXTRACTED_SOURCE_CHARS = 40_000
MAX_EXCERPT_CHARS = 2_500
MAX_HISTORY_MESSAGES = 8


class ConversationAgentError(RuntimeError):
    user_message = "Falha ao executar o agente de conversacao."


class ConversationAgentTimeoutError(ConversationAgentError):
    user_message = "Tempo limite excedido ao consultar o provedor de IA."


class ConversationAgentProviderError(ConversationAgentError):
    def __init__(self, user_message: str) -> None:
        super().__init__(user_message)
        self.user_message = user_message


class _TextExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self._chunks: list[str] = []
        self._skip_depth = 0

    def handle_starttag(self, tag: str, _attrs: list[tuple[str, str | None]]) -> None:
        if tag in {"head", "script", "style", "nav", "footer", "header", "noscript"}:
            self._skip_depth += 1

    def handle_endtag(self, tag: str) -> None:
        if (
            tag in {"head", "script", "style", "nav", "footer", "header", "noscript"}
            and self._skip_depth
        ):
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
    settings = get_settings()
    tools = _build_knowledge_tools(tutor)
    messages = _build_messages(history, user_message)
    started_at = time.monotonic()
    try:
        logger.info(
            "Starting tutor conversation",
            extra={
                "tutor_id": str(tutor.id),
                "model": settings.langchain_model,
                "tool_count": len(tools),
                "timeout_seconds": settings.conversation_agent_timeout_seconds,
            },
        )
        model = init_chat_model(
            settings.langchain_model,
            request_timeout=settings.conversation_agent_timeout_seconds,
        )
        agent = create_agent(
            model=model,
            tools=tools,
            system_prompt=_build_system_prompt(tutor),
        )
        result = agent.invoke({"messages": messages})
    except Exception as exc:  # pragma: no cover - depende do provedor LLM em runtime.
        elapsed_seconds = time.monotonic() - started_at
        if _is_timeout_error(exc):
            logger.warning(
                "Tutor conversation timed out",
                extra={
                    "tutor_id": str(tutor.id),
                    "model": settings.langchain_model,
                    "elapsed_seconds": round(elapsed_seconds, 2),
                    "timeout_seconds": settings.conversation_agent_timeout_seconds,
                    "exception_type": type(exc).__name__,
                },
            )
            raise ConversationAgentTimeoutError() from exc
        if _is_insufficient_credits_error(exc):
            logger.warning(
                "Tutor conversation provider rejected the request due to insufficient credits",
                extra={
                    "tutor_id": str(tutor.id),
                    "model": settings.langchain_model,
                    "elapsed_seconds": round(elapsed_seconds, 2),
                    "exception_type": type(exc).__name__,
                },
            )
            raise ConversationAgentProviderError(
                "O provedor de IA recusou a chamada por creditos insuficientes."
            ) from exc

        logger.exception(
            "Tutor conversation failed",
            extra={
                "tutor_id": str(tutor.id),
                "model": settings.langchain_model,
                "elapsed_seconds": round(elapsed_seconds, 2),
                "exception_type": type(exc).__name__,
            },
        )
        raise ConversationAgentError("Falha ao executar o agente de conversacao.") from exc

    logger.info(
        "Tutor conversation completed",
        extra={
            "tutor_id": str(tutor.id),
            "model": settings.langchain_model,
            "elapsed_seconds": round(time.monotonic() - started_at, 2),
        },
    )

    return _extract_final_answer(result)


def _is_timeout_error(exc: Exception) -> bool:
    current: BaseException | None = exc
    while current is not None:
        text = str(current).lower()
        if "timeout" in text or "timed out" in text:
            return True
        if type(current).__name__.lower() in {"timeout", "timeouterror", "apitimeouterror"}:
            return True
        current = current.__cause__ or current.__context__
    return False


def _is_insufficient_credits_error(exc: Exception) -> bool:
    current: BaseException | None = exc
    while current is not None:
        text = str(current).lower()
        status_code = getattr(current, "status_code", None)
        if status_code == 402 and "insufficient" in text and "credit" in text:
            return True
        if "402" in text and "insufficient" in text and "credit" in text:
            return True
        current = current.__cause__ or current.__context__
    return False


def _build_system_prompt(tutor: Tutor) -> str:
    return "\n".join(
        [
            tutor.system_prompt,
            "",
            "Voce esta em uma conversa de tutoria.",
            "Decida quando usar as ferramentas disponiveis para consultar as fontes do tutor.",
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

    if _is_wikipedia_article_url(parsed):
        wikipedia_extract = _load_wikipedia_extract(parsed)
        if wikipedia_extract is not None:
            return wikipedia_extract

    return _load_html_source_text(location)


def _load_html_source_text(location: str) -> str:
    settings = get_settings()
    user_agent = f"{settings.conversation_agent_name}/{settings.conversation_agent_version}"
    request = Request(
        location,
        headers={
            "Accept": "text/html",
            "Accept-Encoding": "identity",
            "User-Agent": user_agent,
        },
    )
    try:
        with urlopen(request, timeout=10) as response:
            raw_html = response.read(MAX_SOURCE_CHARS).decode("utf-8", errors="ignore")
    except OSError as exc:
        return f"Nao foi possivel ler a fonte {location}: {exc}"

    parser = _TextExtractor()
    parser.feed(raw_html)
    return parser.text()[:MAX_EXTRACTED_SOURCE_CHARS]


def _is_wikipedia_article_url(parsed_url: ParseResult) -> bool:
    hostname = parsed_url.hostname or ""
    return hostname.endswith("wikipedia.org") and parsed_url.path.startswith("/wiki/")


def _load_wikipedia_extract(parsed_url: ParseResult) -> str | None:
    settings = get_settings()
    user_agent = f"{settings.conversation_agent_name}/{settings.conversation_agent_version}"
    article_title = unquote(parsed_url.path.removeprefix("/wiki/"))
    api_query = urlencode(
        {
            "action": "query",
            "format": "json",
            "prop": "extracts",
            "explaintext": "1",
            "redirects": "1",
            "titles": article_title,
        }
    )
    api_url = f"{parsed_url.scheme}://{parsed_url.netloc}/w/api.php?{api_query}"
    request = Request(
        api_url,
        headers={
            "Accept": "application/json",
            "Accept-Encoding": "identity",
            "User-Agent": user_agent,
        },
    )

    try:
        with urlopen(request, timeout=10) as response:
            raw_json = response.read(MAX_SOURCE_CHARS).decode("utf-8", errors="ignore")
    except OSError as exc:
        logger.warning(
            "Wikipedia extract API request failed; falling back to HTML source loading",
            extra={"source_url": parsed_url.geturl(), "exception_type": type(exc).__name__},
        )
        return None

    try:
        payload = json.loads(raw_json)
    except json.JSONDecodeError:
        logger.warning(
            "Wikipedia extract API returned invalid JSON; falling back to HTML source loading",
            extra={"source_url": parsed_url.geturl()},
        )
        return None

    pages = payload.get("query", {}).get("pages", {})
    extracts = [
        page.get("extract", "").strip()
        for page in pages.values()
        if isinstance(page, dict) and page.get("extract")
    ]
    if not extracts:
        return None

    return "\n\n".join(extracts)[:MAX_EXTRACTED_SOURCE_CHARS]


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
