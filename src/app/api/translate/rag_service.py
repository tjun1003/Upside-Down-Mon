from __future__ import annotations

import html
import re
from typing import Any, Dict, List, Optional
from urllib.parse import parse_qs, unquote, urlparse

import httpx

from translation_config import (
    EXTERNAL_RAG_ALLOWED_DOMAINS,
    EXTERNAL_RAG_ENABLED,
    EXTERNAL_RAG_FETCH_PAGE_CONTENT,
    EXTERNAL_RAG_MAX_RESULTS,
    EXTERNAL_RAG_PAGE_FETCH_TIMEOUT_SEC,
    EXTERNAL_RAG_PAGE_MAX_CHARS,
    EXTERNAL_RAG_PROVIDER,
    EXTERNAL_RAG_QUERY_SUFFIX,
    EXTERNAL_RAG_SEARCH_TIMEOUT_SEC,
    EXTERNAL_RAG_SEARCH_URL,
)

class RAGService:
    """Coordinates RAG retrieval/writes across Mongo and fallback KB."""

    def __init__(self, default_kb: Any, logger: Any, top_k: int = 3, text_field: str = "text"):
        self._default_kb = default_kb
        self._logger = logger
        self._top_k = top_k
        self._text_field = text_field
        self._mongo_kb_store: Optional[Any] = None
        self._external_enabled = EXTERNAL_RAG_ENABLED
        self._external_provider = EXTERNAL_RAG_PROVIDER
        self._external_search_url = EXTERNAL_RAG_SEARCH_URL
        self._external_allowed_domains = set(EXTERNAL_RAG_ALLOWED_DOMAINS)
        self._external_query_suffix = EXTERNAL_RAG_QUERY_SUFFIX
        self._external_max_results = max(1, EXTERNAL_RAG_MAX_RESULTS)
        self._external_search_timeout_sec = max(1.0, EXTERNAL_RAG_SEARCH_TIMEOUT_SEC)
        self._external_fetch_page_content = EXTERNAL_RAG_FETCH_PAGE_CONTENT
        self._external_page_fetch_timeout_sec = max(1.0, EXTERNAL_RAG_PAGE_FETCH_TIMEOUT_SEC)
        self._external_page_max_chars = max(500, EXTERNAL_RAG_PAGE_MAX_CHARS)

    def set_mongo_store(self, mongo_kb_store: Optional[Any]) -> None:
        self._mongo_kb_store = mongo_kb_store

    @staticmethod
    def _strip_html(raw_html: str) -> str:
        text = re.sub(r"<script[\s\S]*?</script>", " ", raw_html, flags=re.IGNORECASE)
        text = re.sub(r"<style[\s\S]*?</style>", " ", text, flags=re.IGNORECASE)
        text = re.sub(r"<[^>]+>", " ", text)
        text = html.unescape(text)
        return re.sub(r"\s+", " ", text).strip()

    def _is_domain_allowed(self, url: str) -> bool:
        if not self._external_allowed_domains:
            return True
        try:
            host = (urlparse(url).hostname or "").lower()
        except Exception:
            return False
        return any(host == domain or host.endswith(f".{domain}") for domain in self._external_allowed_domains)

    @staticmethod
    def _unwrap_duckduckgo_redirect(url: str) -> str:
        parsed = urlparse(url)
        if "duckduckgo.com" not in (parsed.netloc or "") and "duckduckgo.com" not in url:
            return url
        qs = parse_qs(parsed.query)
        uddg = qs.get("uddg", [])
        if uddg:
            return unquote(uddg[0])
        return url

    async def _duckduckgo_search(self, query: str) -> List[Dict[str, str]]:
        search_query = query.strip()
        if self._external_query_suffix:
            search_query = f"{search_query} {self._external_query_suffix}".strip()

        self._logger.info(f"External RAG: searching web for '{search_query}'")
        async with httpx.AsyncClient(timeout=self._external_search_timeout_sec) as client:
            response = await client.post(
                self._external_search_url,
                data={"q": search_query},
                headers={
                    "User-Agent": "Mozilla/5.0",
                    "Content-Type": "application/x-www-form-urlencoded",
                },
            )
            response.raise_for_status()
            html_body = response.text

        results: List[Dict[str, str]] = []
        pattern = re.compile(
            r'<a[^>]*class="result__a"[^>]*href="([^"]+)"[^>]*>(.*?)</a>',
            flags=re.IGNORECASE | re.DOTALL,
        )

        for match in pattern.finditer(html_body):
            raw_url = html.unescape(match.group(1).strip())
            url = self._unwrap_duckduckgo_redirect(raw_url)
            if not self._is_domain_allowed(url):
                continue

            title = self._strip_html(match.group(2))
            if not title:
                continue

            results.append({"title": title, "url": url, "snippet": ""})
            if len(results) >= self._external_max_results:
                break

        return results

    async def _fetch_page_snippet(self, url: str) -> str:
        if not self._external_fetch_page_content:
            return ""
        try:
            async with httpx.AsyncClient(timeout=self._external_page_fetch_timeout_sec, follow_redirects=True) as client:
                response = await client.get(url, headers={"User-Agent": "Mozilla/5.0"})
                response.raise_for_status()
                text = self._strip_html(response.text)
                return text[: self._external_page_max_chars].strip()
        except Exception as exc:
            self._logger.warning(f"External RAG: page fetch failed for {url}: {exc}")
            return ""

    async def _external_retrieve_context(self, message: str) -> str:
        if not self._external_enabled:
            return ""
        if self._external_provider != "duckduckgo_html":
            self._logger.warning(f"External RAG provider unsupported: {self._external_provider}")
            return ""

        try:
            hits = await self._duckduckgo_search(message)
        except Exception as exc:
            self._logger.warning(f"External RAG search failed: {exc}")
            return ""

        if not hits:
            self._logger.info("External RAG: no web results")
            return ""

        chunks: List[str] = []
        for idx, hit in enumerate(hits, 1):
            snippet = await self._fetch_page_snippet(hit["url"])
            if not snippet:
                snippet = hit.get("snippet", "")
            preview = (snippet or "").strip()
            if not preview:
                continue
            chunks.append(
                f"[Web {idx}] {hit['title']}\nSource: {hit['url']}\n{preview}"
            )

        if not chunks:
            self._logger.info("External RAG: web results had no usable content")
            return ""

        context = "\n---\n".join(chunks)
        self._logger.info(f"External RAG: prepared {len(chunks)} context chunk(s)")
        return context

    async def retrieve_context(self, message: str) -> str:
        self._logger.info("RAGService: start retrieval (internal first, external fallback)")

        internal_context = ""
        if self._default_kb.ready:
            try:
                internal_context = self._default_kb.retrieve(message)
            except Exception as exc:
                self._logger.warning(f"Internal KB retrieval failed: {exc}")

        if internal_context.strip():
            self._logger.info("RAGService: internal RAG hit")
            return internal_context

        self._logger.info("RAGService: internal RAG miss, trying external web RAG")
        external_context = await self._external_retrieve_context(message)
        if external_context.strip():
            return external_context

        self._logger.info("RAGService: no context from internal/external RAG")
        return ""

    async def add_documents(self, documents: List[Dict[str, Any]]) -> int:
        mongo_added = 0
        if self._mongo_kb_store is not None:
            try:
                mongo_added = await self._mongo_kb_store.add_documents(documents)
            except Exception as exc:
                self._logger.warning(f"Mongo KB write failed, using default KB only: {exc}")

        self._default_kb.add_documents(documents)
        return mongo_added
