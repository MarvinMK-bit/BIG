NO_QUESTION_MARKERS_MESSAGE = (
    "No question numbers found in this script. The deterministic grader needs numbered "
    "answers (1. / (1) / Item 1). Use the LLM path, or enable unnumbered mode to treat "
    "each line as one question."
)


class NoQuestionMarkersError(ValueError):
    def __init__(self, message: str = NO_QUESTION_MARKERS_MESSAGE) -> None:
        super().__init__(message)
