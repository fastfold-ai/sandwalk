"""Ingestion from literature APIs (PubMed, OpenAlex)."""

from __future__ import annotations

import time
from typing import Any


class _LiteratureMixin:
    def ingest_pubmed(self, *, query: str, max_results: int = 10) -> dict[str, Any]:
        from tools.literature import pubmed_search

        result = pubmed_search(query=query, max_results=max_results)
        if result.get("error"):
            return {"error": result["error"], "source": "pubmed"}

        articles = result.get("articles", []) or []
        query_entities = self._get_or_create_query_entities(query)
        n_links = 0
        for art in articles:
            pmid = str(art.get("pmid", "")).strip()
            title = str(art.get("title", "")).strip()
            if not pmid:
                continue
            pub = self.substrate.upsert_entity(
                entity_type="publication",
                name=title or f"PMID {pmid}",
                identifier=f"PMID:{pmid}",
                metadata={"pmid": pmid, "journal": art.get("journal", "")},
            )
            ev = self.substrate.add_evidence(
                source_type="pubmed",
                source_ref=f"PMID:{pmid}",
                summary=title,
                score=0.75,
                tags=["literature"],
                metadata={"year": art.get("publication_year")},
            )
            for eid in query_entities:
                self.substrate.link_entities(
                    subject_id=eid,
                    predicate="supported_by_literature",
                    object_id=pub.id,
                    evidence_id=ev.id,
                    polarity="support",
                    score=0.75,
                )
                n_links += 1
        self._state["source_runs"]["pubmed"] = time.time()
        self.save_state()
        self.substrate.save()
        return {
            "summary": f"Ingested {len(articles)} PubMed article(s) for '{query}'.",
            "source": "pubmed",
            "ingested_articles": len(articles),
            "links_created": n_links,
        }

    def ingest_openalex(self, *, query: str, max_results: int = 10) -> dict[str, Any]:
        from tools.literature import openalex_search

        result = openalex_search(query=query, max_results=max_results)
        if result.get("error"):
            return {"error": result["error"], "source": "openalex"}

        articles = result.get("articles", []) or []
        query_entities = self._get_or_create_query_entities(query)
        n_links = 0
        for art in articles:
            doi = str(art.get("doi", "")).strip()
            title = str(art.get("title", "")).strip()
            if not doi and not title:
                continue
            pub_id = doi or title
            pub = self.substrate.upsert_entity(
                entity_type="publication",
                name=title or pub_id,
                identifier=pub_id,
                metadata={
                    "doi": doi,
                    "source": art.get("source", ""),
                    "year": art.get("publication_year"),
                    "cited_by_count": art.get("cited_by_count", 0),
                },
            )
            ev = self.substrate.add_evidence(
                source_type="openalex",
                source_ref=pub_id,
                summary=title,
                score=0.72,
                tags=["literature"],
            )
            for eid in query_entities:
                self.substrate.link_entities(
                    subject_id=eid,
                    predicate="supported_by_literature",
                    object_id=pub.id,
                    evidence_id=ev.id,
                    polarity="support",
                    score=0.72,
                )
                n_links += 1
        self._state["source_runs"]["openalex"] = time.time()
        self.save_state()
        self.substrate.save()
        return {
            "summary": f"Ingested {len(articles)} OpenAlex work(s) for '{query}'.",
            "source": "openalex",
            "ingested_works": len(articles),
            "links_created": n_links,
        }
