"""Grounded answering: offline extractive by default, optional compatible chat provider."""
from __future__ import annotations

import json
import re
from typing import Any

import httpx

from ragforge.models import Answer, Citation, SearchHit


class ProviderError(RuntimeError):
    pass


class GroundedGenerator:
    def __init__(self, settings, provider_client: Any = None):
        self.settings = settings
        self.provider_client = provider_client

    @staticmethod
    def _citation(hit: SearchHit, n: int) -> Citation:
        c = hit.chunk
        return Citation(f"[C{n}]", c.id, c.document_id, str(c.metadata.get("title", c.document_id)), c.text, c.start_char, c.end_char)

    def _evidence(self, hits: list[SearchHit]) -> tuple[list[SearchHit], str | None]:
        # Evidence gating deliberately uses component scores, never RRF rank score.
        usable = []
        for h in hits:
            # ``sparse`` is the authoritative overlap signal for BM25 and hybrid
            # retrieval. Dense/hash scores are only used when no lexical signal
            # exists (for explicitly dense configurations), and RRF is never a
            # confidence or evidence score.
            component = h.scores.get(
                "component",
                h.scores.get("lexical", h.scores.get("sparse", h.scores.get("dense", 0.0))),
            )
            if component > 0 and h.chunk.text.strip():
                usable.append(h)
        return usable, None if usable else "No retrieved chunk has query-overlapping evidence"

    @staticmethod
    def _compress(hits: list[SearchHit], limit: int = 6000) -> list[SearchHit]:
        out, used = [], 0
        for h in hits:
            if used >= limit:
                break
            text = h.chunk.text[: max(0, limit - used)]
            if text != h.chunk.text:
                from dataclasses import replace
                h = replace(h, chunk=replace(h.chunk, text=text))
            out.append(h)
            used += len(text)
        return out

    def _offline(self, question: str, hits: list[SearchHit], reason: str | None, compress: bool) -> Answer:
        if reason:
            return Answer(question, "I don't have enough evidence in the indexed documents to answer that.", True, reason, [], hits, {"mode": "offline-extractive", "evidence_gate": "component_score", "limitation": "This is not formal factuality verification."})
        hits = self._compress(hits) if compress else hits
        citations = [self._citation(h, i) for i, h in enumerate(hits, 1)]
        # Extractive output preserves exact source excerpts and stable citation labels.
        answer = " ".join(f"{c.quote} {c.label}" for c in citations)
        return Answer(question, answer, False, None, citations, hits, {"mode": "offline-extractive", "evidence_gate": "component_score", "limitation": "Extractive context is not formal factuality verification."})

    def _provider(self, question: str, hits: list[SearchHit], reason: str | None, compress: bool) -> Answer:
        if reason:
            return self._offline(question, hits, reason, compress)
        hits = self._compress(hits) if compress else hits
        citations = [self._citation(h, i) for i, h in enumerate(hits, 1)]
        context = "\n".join(f"{c.label} {c.quote}" for c in citations)
        payload = {"model": self.settings.provider_model, "temperature": 0, "messages": [{"role": "system", "content": "Answer only from the supplied context. Every factual claim must include an exact inline citation label such as [C1]. Do not invent citations."}, {"role": "user", "content": f"Context:\n{context}\n\nQuestion: {question}"}]}
        headers = {"Content-Type": "application/json"}
        if self.settings.provider_api_key:
            headers["Authorization"] = f"Bearer {self.settings.provider_api_key}"
        try:
            if self.provider_client:
                response = self.provider_client(payload, headers=headers, timeout=self.settings.provider_timeout_seconds)
                data = response.json() if hasattr(response, "json") else response
            else:
                with httpx.Client(timeout=self.settings.provider_timeout_seconds) as client:
                    response = client.post(self.settings.provider_url, json=payload, headers=headers)
                    response.raise_for_status()
                    data = response.json()
            text = data.get("choices", [])[0].get("message", {}).get("content", "")
            labels = set(re.findall(r"\[C\d+\]", text))
            allowed = {c.label for c in citations}
            if not text.strip() or not labels or not labels <= allowed:
                raise ProviderError("Provider response did not contain valid citation labels")
            return Answer(question, text, False, None, citations, hits, {"mode": "provider", "evidence_gate": "component_score", "limitation": "Citation validation checks labels and excerpts, not factuality."})
        except (httpx.HTTPError, KeyError, IndexError, TypeError, ValueError, ProviderError) as exc:
            raise ProviderError(f"Provider response invalid or unavailable: {exc}") from exc

    def transform_query(self, question: str, *, rewrite: bool = False, hyde: bool = False) -> str:
        """Perform opt-in provider query transformations; never silently falls back."""
        if not rewrite and not hyde:
            return question
        if not self.settings.provider_enabled:
            raise ProviderError("rewrite/hyde require a configured provider")
        instruction = "Rewrite the search query for precise retrieval. Return only the rewritten query." if rewrite else "Write a short hypothetical answer useful for retrieving evidence. Return only that text."
        if rewrite and hyde:
            instruction = "Rewrite the query and include the key concepts a hypothetical answer would contain. Return only retrieval text."
        payload = {"model": self.settings.provider_model, "temperature": 0, "messages": [{"role": "system", "content": instruction}, {"role": "user", "content": question}]}
        headers = {"Content-Type": "application/json"}
        if self.settings.provider_api_key:
            headers["Authorization"] = f"Bearer {self.settings.provider_api_key}"
        try:
            if self.provider_client:
                response = self.provider_client(payload, headers=headers, timeout=self.settings.provider_timeout_seconds)
                data = response.json() if hasattr(response, "json") else response
            else:
                with httpx.Client(timeout=self.settings.provider_timeout_seconds) as client:
                    response = client.post(self.settings.provider_url, json=payload, headers=headers)
                    response.raise_for_status()
                    data = response.json()
            text = data.get("choices", [])[0].get("message", {}).get("content", "").strip()
            if not text or len(text) > 10000:
                raise ProviderError("Provider returned an invalid query transformation")
            return text
        except (httpx.HTTPError, KeyError, IndexError, TypeError, ValueError, ProviderError) as exc:
            raise ProviderError(f"Provider query transformation failed: {exc}") from exc

    def answer(self, question: str, hits: list[SearchHit], *, compress: bool = True) -> Answer:
        usable, reason = self._evidence(hits)
        if self.settings.provider_enabled:
            return self._provider(question, usable, reason, compress)
        return self._offline(question, usable, reason, compress)
