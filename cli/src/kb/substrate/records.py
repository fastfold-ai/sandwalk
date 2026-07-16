"""Dataclasses for the knowledge substrate: entities, evidence, claims, relations."""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any


@dataclass
class KBEntity:
    id: str
    entity_type: str
    name: str
    synonyms: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
    first_seen: float = field(default_factory=time.time)
    last_seen: float = field(default_factory=time.time)


@dataclass
class KBEvidence:
    id: str
    source_type: str
    source_ref: str
    summary: str
    score: float = 0.5
    tags: list[str] = field(default_factory=list)
    timestamp: float = field(default_factory=time.time)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class KBClaim:
    evidence_id: str
    polarity: str = "support"  # support | contradict | neutral
    score: float = 0.5
    timestamp: float = field(default_factory=time.time)


@dataclass
class KBRelation:
    id: str
    subject_id: str
    predicate: str
    object_id: str
    claims: list[KBClaim] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
    first_seen: float = field(default_factory=time.time)
    last_seen: float = field(default_factory=time.time)
