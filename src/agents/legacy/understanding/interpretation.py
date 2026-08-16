from pydantic import BaseModel

from src.agents.legacy.context_models import ConversationContext
from src.agents.legacy.understanding.models import UnderstandingResult
from src.agents.legacy.understanding.rewrite_models import RewriteDecision, RewriteResult


class TurnInterpretation(BaseModel):
    context: ConversationContext
    rewrite_decision: RewriteDecision
    rewrite_result: RewriteResult
    understanding: UnderstandingResult

    @property
    def effective_text(self) -> str:
        return self.rewrite_result.rewritten_text
