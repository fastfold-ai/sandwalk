"""
Domain knowledge primer for the ct planner and synthesizer.

Condensed from docs/comprehensive_capabilities.md — provides the LLM with broad awareness
of the drug discovery landscape so it can:
1. Ask more intelligent clarifying questions
2. Suggest richer, more diverse analysis plans
3. Recommend relevant follow-up analyses the researcher might not think of
4. Connect results across disciplines (genomics ↔ chemistry ↔ clinical ↔ structure)

Updated for production tool surface; avoid hardcoded counts in prompt text.

Split across ``primer_tools_*`` (KNOWLEDGE_PRIMER) and ``primer_*`` (SYNTHESIZER_PRIMER)
sibling modules to stay under the file-length cap; this module concatenates them back
into the two public constants.
"""

from agent.knowledge.primer_domain_anchors import PRIMER_DOMAIN_ANCHORS
from agent.knowledge.primer_synthesis_rules import PRIMER_SYNTHESIS_RULES
from agent.knowledge.primer_tools_advanced import PRIMER_TOOLS_ADVANCED
from agent.knowledge.primer_tools_intro import PRIMER_TOOLS_INTRO

__all__ = ["KNOWLEDGE_PRIMER", "SYNTHESIZER_PRIMER"]

KNOWLEDGE_PRIMER = PRIMER_TOOLS_INTRO + PRIMER_TOOLS_ADVANCED
SYNTHESIZER_PRIMER = PRIMER_SYNTHESIS_RULES + PRIMER_DOMAIN_ANCHORS
