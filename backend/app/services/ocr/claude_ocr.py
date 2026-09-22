import base64

from anthropic import AsyncAnthropic

from app.core.config import get_settings
from app.services.ocr.base import OCREngine, OCRPage, OCRResult
from app.services.ocr.registry import register

MAX_OUTPUT_TOKENS = 16000

_IMAGE_MIME_TYPES = {"image/jpeg", "image/png", "image/webp"}

_PAGE_BREAK = "<<<PAGE_BREAK>>>"

SYSTEM_PROMPT = f"""\
You are transcribing a handwritten exam script into Markdown, verbatim, so it can be \
graded automatically. Follow these rules exactly:

- Preserve the student's own question numbering exactly as written, including \
sub-parts such as 3(a)(ii). Do not renumber, reorder, or reformat it.
- For each question or sub-part, keep the student's working above their final answer, \
transcribed exactly as written.
- End each question or sub-part with its final answer alone on its own line, starting \
with "Answer:" (for example "Answer: 56"), so a parser can find it. If the student \
gave no final answer, omit the "Answer:" line for that question.
- Transcribe exactly what is on the page, including mistakes, crossed-out work, and \
wrong answers. Never correct, complete, or improve the student's work.
- If a word, symbol, or line is illegible, write [illegible] in its place instead of \
guessing what it says.
- If the input has more than one page, insert a line containing exactly \
"{_PAGE_BREAK}" between the transcription of each page, and nowhere else.
- Output only the transcription. No preamble, no commentary, no explanations, and no \
markdown code fences.
"""


@register
class ClaudeOCREngine(OCREngine):
    name = "claude"

    async def extract(self, file_bytes: bytes, mime_type: str) -> OCRResult:
        settings = get_settings()
        if not settings.ANTHROPIC_API_KEY:
            raise RuntimeError("ANTHROPIC_API_KEY is not set; the claude OCR engine is unavailable")

        data = base64.standard_b64encode(file_bytes).decode("ascii")

        if mime_type in _IMAGE_MIME_TYPES:
            content_block = {
                "type": "image",
                "source": {"type": "base64", "media_type": mime_type, "data": data},
            }
        elif mime_type == "application/pdf":
            content_block = {
                "type": "document",
                "source": {"type": "base64", "media_type": "application/pdf", "data": data},
            }
        else:
            raise ValueError(f"Unsupported mime type for Claude OCR: {mime_type!r}")

        model = settings.OCR_MODEL
        async with AsyncAnthropic(api_key=settings.ANTHROPIC_API_KEY) as client:
            response = await client.messages.create(
                model=model,
                max_tokens=MAX_OUTPUT_TOKENS,
                system=SYSTEM_PROMPT,
                messages=[
                    {
                        "role": "user",
                        "content": [
                            content_block,
                            {"type": "text", "text": "Transcribe this exam script."},
                        ],
                    }
                ],
            )

        raw_text = "".join(block.text for block in response.content if block.type == "text")
        page_texts = [page.strip() for page in raw_text.split(_PAGE_BREAK)]
        page_texts = [page for page in page_texts if page] or [raw_text.strip()]

        pages = [
            OCRPage(page_number=index, markdown=page_text, confidence=None)
            for index, page_text in enumerate(page_texts, start=1)
        ]

        return OCRResult(
            pages=pages,
            engine_name="claude",
            engine_version=model,
            raw_response=response.model_dump(),
        )
