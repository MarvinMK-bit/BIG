from app.services.ocr.base import OCREngine, OCRPage, OCRResult
from app.services.ocr.registry import register

_SAMPLE_MARKDOWN = """\
1. Work out 7 x 8.
   Answer: 56

2. Simplify 3x + 5x.
   Answer: 8x

3. Solve for x: 2x + 3 = 11.
   Answer: x = 5

4. Work out 15% of 60.
   Answer: 9
"""


@register
class StubOCREngine(OCREngine):
    name = "stub"

    async def extract(self, file_bytes: bytes, mime_type: str) -> OCRResult:
        return OCRResult(
            pages=[
                OCRPage(page_number=1, markdown=_SAMPLE_MARKDOWN, confidence=1.0),
            ],
            engine_name="stub",
            engine_version="1.0",
            raw_response=None,
        )
