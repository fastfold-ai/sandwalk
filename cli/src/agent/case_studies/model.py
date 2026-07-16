"""The CaseStudy dataclass shared by the case study registry modules."""

from dataclasses import dataclass, field


@dataclass
class CaseStudy:
    """A curated drug case study for demo/showcase purposes."""

    id: str
    name: str
    compound: str
    targets: list[str]
    indication: str
    description: str
    thread_goals: list[dict] = field(default_factory=list)
