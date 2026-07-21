"""
OCR Service for FairMark Backend
Integrates with the OCR module to extract text from uploaded papers
and parse structured data (Student Info, Q&A pairs)
"""
import os
import re
import io
import base64
import time
import tempfile
import logging
from pathlib import Path
from typing import List, Dict, Optional
from dotenv import load_dotenv

# Setup logging — level controlled by LOG_LEVEL env var (default INFO)
# A5: Do NOT call basicConfig here; logging is configured centrally in main.py
logger = logging.getLogger(__name__)

# Load environment variables from the consolidated backend/.env
BACKEND_ENV_PATH = Path(__file__).parent.parent / '.env'
logger.info(f"Loading env from: {BACKEND_ENV_PATH}")
load_dotenv(dotenv_path=BACKEND_ENV_PATH)


# Shared structured-OCR prompt for vision LLM providers (Groq, etc.).
_OCR_PROMPT = """Look at this exam paper image and extract ONLY the text that is actually visible and handwritten/printed on the paper.

CRITICAL RULES:
1. If there are NO questions visible, return empty qa_pairs array
2. If there are NO answers visible, return empty qa_pairs array
3. DO NOT make up or invent any text
4. ONLY extract text you can actually see in the image
5. If the image is blank or has no Q&A, return: {"subject": "None", "qa_pairs": []}
6. Copy the printed question ID/number exactly. If the question ID or answer is unclear, set needs_teacher_correction=true and confidence <= 0.5
7. Do not infer a model/correct answer; extract only the student's visible answer

Return ONLY valid JSON (no markdown, no extra text):
{
  "student_name": "name if visible or empty string",
  "student_id": "ID if visible or empty string",
  "subject": "subject name if visible or General",
  "total_marks": "total marks number if visible on paper header or null",
  "qa_pairs": [
    {
      "question_number": 1,
      "question_id": "printed ID such as Q1 if visible",
      "question": "ONLY actual visible question text",
      "answer": "ONLY actual visible answer text",
      "confidence": 0.0,
      "needs_teacher_correction": false
    }
  ]
}

If you cannot see clear printed question IDs and answers, return empty qa_pairs array."""


class OCRService:
    """
    Simple OCR service using OpenRouter's vision models
    Falls back to RapidAPI if OpenRouter fails
    """
    
    def __init__(self):
        # Support multiple OpenRouter keys (different accounts have independent
        # free-tier quotas) for failover: OPENROUTER_API_KEY, OPENROUTER_API_KEY_2..9
        self.openrouter_keys = []
        _primary = os.getenv('OPENROUTER_API_KEY')
        if _primary:
            self.openrouter_keys.append(_primary)
        for _i in range(2, 10):
            _k = os.getenv(f'OPENROUTER_API_KEY_{_i}')
            if _k:
                self.openrouter_keys.append(_k)
        self.openrouter_key = self.openrouter_keys[0] if self.openrouter_keys else None  # back-compat
        self.site_url = os.getenv('OPENROUTER_SITE_URL', 'http://localhost:3000')

        # Groq vision OCR keys (separate free-tier quota): GROQ_API_KEY, GROQ_API_KEY_2..9
        self.groq_api_keys = []
        _gq = os.getenv('GROQ_API_KEY')
        if _gq:
            self.groq_api_keys.append(_gq)
        for _i in range(2, 10):
            _k = os.getenv(f'GROQ_API_KEY_{_i}')
            if _k:
                self.groq_api_keys.append(_k)

        # Support multiple Gemini keys for rate-limit failover
        self.gemini_api_keys = [
            k for k in [
                os.getenv('GEMINI_API_KEY', ''),
                os.getenv('GEMINI_API_KEY_2', ''),
                os.getenv('GEMINI_API_KEY_3', ''),
            ] if k
        ]

        # Only treat a key as configured if it's non-empty AND not a placeholder
        def _valid_key(val):
            if not val:
                return None
            if val.startswith('your_') or val == 'placeholder':
                return None
            return val

        self.rapidapi_keys = {
            'pen_to_print': _valid_key(os.getenv('PEN_TO_PRINT_API_KEY')),
            'ocr_extract':  _valid_key(os.getenv('OCR_EXTRACT_API_KEY')),
            'ocr_document_pro': _valid_key(os.getenv('OCR_DOCUMENT_PRO_API_KEY')),
        }
        # Log which keys are configured (never log key values)
        logger.info(f"Groq keys configured: {len(self.groq_api_keys)}")
        logger.info(f"Gemini keys configured: {len(self.gemini_api_keys)}")
        logger.info(f"OpenRouter keys configured: {len(self.openrouter_keys)}")
        logger.info(f"Pen-to-Print key configured: {bool(self.rapidapi_keys.get('pen_to_print'))}")
        logger.info(f"OCR Extract key configured: {bool(self.rapidapi_keys.get('ocr_extract'))}")
    
    # ── 1. Image downscale ────────────────────────────────────────────
    # Shrink large photos once; every provider downstream benefits from
    # the smaller payload (faster upload, lower token count).
    MAX_EDGE_PX = 2000          # longest-edge cap (raise toward 2500 if OCR regresses)
    JPEG_QUALITY = 85

    # Gemini OCR models tried in order (env override: GEMINI_OCR_MODELS, comma-separated).
    # If one model's free tier is exhausted (429) or unavailable (404), the next is tried.
    # 2.5-flash is first because 2.0-flash's free tier is frequently capped at 0,
    # so leading with it wastes a round-trip on every request.
    GEMINI_OCR_MODELS = [
        m.strip() for m in os.getenv(
            'GEMINI_OCR_MODELS', 'gemini-2.5-flash,gemini-2.0-flash,gemini-1.5-flash'
        ).split(',') if m.strip()
    ]

    # Groq vision (multimodal) OCR models, tried in order (env: GROQ_OCR_MODELS).
    # Groq has a separate, generous free tier and is fast (~2-5s).
    GROQ_OCR_MODELS = [
        m.strip() for m in os.getenv(
            'GROQ_OCR_MODELS',
            'meta-llama/llama-4-scout-17b-16e-instruct,meta-llama/llama-4-maverick-17b-128e-instruct'
        ).split(',') if m.strip()
    ]

    @staticmethod
    def _summarize_provider_error(e) -> str:
        """Turn a noisy SDK/HTTP error into a short, readable one-liner."""
        s = str(e)
        if '429' in s or 'RESOURCE_EXHAUSTED' in s or 'quota' in s.lower():
            m = (re.search(r'retry in ~?([\d.]+)\s*s', s, re.IGNORECASE)
                 or re.search(r"retryDelay'?\s*:?\s*'?(\d+)s", s))
            hint = f"; retry in ~{m.group(1)}s" if m else ""
            return f"rate limited / free-tier quota exhausted{hint}"
        s = re.sub(r'\s+', ' ', s).strip()
        return (s[:180] + '…') if len(s) > 180 else s

    @staticmethod
    def _downscale_image(file_bytes: bytes, max_edge: int, jpeg_quality: int) -> bytes:
        """Downscale if longest edge > max_edge; re-encode as JPEG q85."""
        from PIL import Image
        img = Image.open(io.BytesIO(file_bytes))
        w, h = img.size
        longest = max(w, h)
        if longest <= max_edge:
            return file_bytes                       # already small enough
        scale = max_edge / longest
        new_w, new_h = int(w * scale), int(h * scale)
        img = img.resize((new_w, new_h), Image.LANCZOS)
        if img.mode in ('RGBA', 'P'):
            img = img.convert('RGB')
        buf = io.BytesIO()
        img.save(buf, format='JPEG', quality=jpeg_quality)
        logger.info(f"Downscaled image {w}x{h} -> {new_w}x{new_h} ({len(file_bytes)} -> {buf.tell()} bytes)")
        return buf.getvalue()

    @staticmethod
    def _pdf_to_image_bytes(pdf_bytes: bytes, dpi: int = 200) -> bytes:
        """
        Convert a PDF document to a single JPEG image.
        All pages are rendered and stitched vertically into one tall image.
        """
        try:
            import fitz  # PyMuPDF
        except ImportError as e:
            # PDFs ARE supported — the renderer dependency is just missing.
            raise RuntimeError(
                "PDF support requires PyMuPDF, which isn't installed. "
                "Run: pip install -r backend/requirements.txt (then restart the backend)."
            ) from e
        from PIL import Image

        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
        page_images = []
        for page_num in range(len(doc)):
            page = doc[page_num]
            # Render at the specified DPI (default matrix is 72 DPI)
            zoom = dpi / 72.0
            mat = fitz.Matrix(zoom, zoom)
            pix = page.get_pixmap(matrix=mat)
            img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
            page_images.append(img)
        doc.close()

        if not page_images:
            raise ValueError("PDF has no pages")

        # Stitch pages vertically
        if len(page_images) == 1:
            combined = page_images[0]
        else:
            total_width = max(img.width for img in page_images)
            total_height = sum(img.height for img in page_images)
            combined = Image.new("RGB", (total_width, total_height), (255, 255, 255))
            y_offset = 0
            for img in page_images:
                combined.paste(img, (0, y_offset))
                y_offset += img.height

        buf = io.BytesIO()
        combined.save(buf, format="JPEG", quality=90)
        logger.info(f"PDF rendered: {len(page_images)} page(s) -> {combined.width}x{combined.height} JPEG ({buf.tell()} bytes)")
        return buf.getvalue()

    def extract_text_from_bytes(self, file_bytes: bytes, filename: str) -> dict:
        """
        Extract text from file bytes (images or PDFs).

        Args:
            file_bytes: Raw file bytes
            filename: Original filename (for extension detection)

        Returns:
            dict with 'success', 'text', 'model', 'platform' keys
        """
        # ── PDF conversion: render pages to a single JPEG image ──────
        if file_bytes[:5] == b'%PDF-' or filename.lower().endswith('.pdf'):
            try:
                file_bytes = self._pdf_to_image_bytes(file_bytes)
                filename = 'converted.jpg'
                logger.info("PDF converted to JPEG image for OCR processing")
            except Exception as e:
                logger.error(f"PDF conversion failed: {type(e).__name__}: {e}")
                # Be accurate: PDFs are supported; this specific PDF couldn't be read.
                return {'success': False, 'error': f'Could not read this PDF: {e}'}

        # Downscale once — every provider gets the smaller image
        try:
            file_bytes = self._downscale_image(file_bytes, self.MAX_EDGE_PX, self.JPEG_QUALITY)
            ext = '.jpg'        # re-encoded as JPEG after downscale
        except Exception as e:
            logger.warning(f"Downscale skipped ({type(e).__name__}): {e}")
            ext = Path(filename).suffix.lower() or '.png'

        with tempfile.NamedTemporaryFile(suffix=ext, delete=False) as tmp:
            tmp.write(file_bytes)
            tmp_path = tmp.name

        try:
            result = self._extract_from_file(tmp_path)
            return result
        finally:
            try:
                os.unlink(tmp_path)
            except:
                pass
    
    # ── 2. Minimum viable OCR output length ─────────────────────────
    # A 200-OK that returns fewer chars than this is treated as garbage
    # and the cascade continues to the next provider.
    _MIN_OCR_CHARS = 15

    @staticmethod
    def _is_plausible_ocr(text: str) -> bool:
        """Reject empty / implausibly short responses that look like garbage."""
        if not text or not text.strip():
            return False
        stripped = text.strip()
        # After stripping JSON wrappers, must have real content
        if len(stripped) < 15:
            return False
        return True

    @staticmethod
    def _has_qa_content(result: dict) -> bool:
        """Return True if the OCR result actually extracted Q&A pairs.
        A structured JSON response that parsed student info but returned
        empty qa_pairs is only a *partial* success — the cascade should
        keep trying other providers before settling for it."""
        parsed = result.get('parsed_json')
        if parsed is not None and not parsed.get('qa_pairs'):
            return False
        return True

    def _extract_from_file(self, image_path: str) -> dict:
        """Extract text from image file using available OCR services."""
        errors = []
        # Partial result: a provider that returned student info but empty
        # qa_pairs.  Kept as a fallback in case no provider extracts Q&A.
        partial_result = None
        cascade_start = time.time()
        logger.info(f"Starting OCR extraction for: {image_path}")

        def _accept_or_save(result, provider_label, elapsed):
            """Return the result if it has Q&A content, else save as partial."""
            nonlocal partial_result
            if self._has_qa_content(result):
                logger.info(f"{provider_label} succeeded with Q&A in {elapsed:.1f}s")
                return result
            # Student info extracted but no questions — save and keep trying
            if partial_result is None:
                partial_result = result
            logger.warning(f"{provider_label} returned empty qa_pairs ({elapsed:.1f}s); trying next provider")
            errors.append(f"{provider_label} ({elapsed:.1f}s): extracted student info but empty qa_pairs")
            return None

        # ── Groq vision (fast, separate free-tier quota — tried first) ──
        if self.groq_api_keys:
            t0 = time.time()
            logger.info(f"Attempting Groq OCR ({len(self.groq_api_keys)} key(s))...")
            result = self._try_groq(image_path)
            elapsed = time.time() - t0
            if result.get('success') and self._is_plausible_ocr(result.get('text', '')):
                accepted = _accept_or_save(result, "Groq", elapsed)
                if accepted:
                    return accepted
            else:
                detail = result.get('error', 'short/empty output')
                if result.get('details'):
                    detail += " - " + "; ".join(str(d) for d in result['details'][:3])
                logger.warning(f"Groq failed ({elapsed:.1f}s): {detail}")
                errors.append(f"Groq ({elapsed:.1f}s): {detail}")
        else:
            errors.append("Groq: API key not configured")

        # ── Gemini (try all configured keys) ──
        if self.gemini_api_keys:
            for key_idx, api_key in enumerate(self.gemini_api_keys):
                t0 = time.time()
                logger.info(f"Attempting Gemini OCR (key {key_idx + 1}/{len(self.gemini_api_keys)})...")
                result = self._try_gemini(image_path, api_key)
                elapsed = time.time() - t0
                if result.get('success') and self._is_plausible_ocr(result.get('text', '')):
                    accepted = _accept_or_save(result, f"Gemini key {key_idx + 1}", elapsed)
                    if accepted:
                        return accepted
                else:
                    err = result.get('error', 'short/empty output')
                    logger.warning(f"Gemini key {key_idx + 1} failed ({elapsed:.1f}s): {err}")
                    errors.append(f"Gemini key {key_idx + 1} ({elapsed:.1f}s): {err}")
        else:
            errors.append("Gemini: no API keys configured")

        # ── OpenRouter (AI Vision) ──
        if self.openrouter_keys:
            t0 = time.time()
            logger.info(f"Attempting OpenRouter OCR ({len(self.openrouter_keys)} key(s))...")
            result = self._try_openrouter(image_path)
            elapsed = time.time() - t0
            if result.get('success') and self._is_plausible_ocr(result.get('text', '')):
                accepted = _accept_or_save(result, "OpenRouter", elapsed)
                if accepted:
                    return accepted
            else:
                logger.warning(f"OpenRouter failed ({elapsed:.1f}s): {result.get('error', 'short/empty output')}")
                detail = result.get('error', 'short/empty output')
                if result.get('details'):
                    detail += " - " + "; ".join(str(d) for d in result['details'][:3])
                errors.append(f"OpenRouter ({elapsed:.1f}s): {detail}")
        else:
            errors.append("OpenRouter: API key not configured")

        # ── RapidAPI Pen-to-Print ──
        if self.rapidapi_keys.get('pen_to_print'):
            t0 = time.time()
            logger.info("Attempting Pen-to-Print OCR...")
            result = self._try_pen_to_print(image_path)
            elapsed = time.time() - t0
            if result.get('success') and self._is_plausible_ocr(result.get('text', '')):
                logger.info(f"Pen-to-Print OCR succeeded in {elapsed:.1f}s")
                return result
            logger.warning(f"Pen-to-Print failed ({elapsed:.1f}s): {result.get('error', 'short/empty output')}")
            errors.append(f"Pen-to-Print ({elapsed:.1f}s): {result.get('error', 'short/empty output')}")
        else:
            errors.append("Pen-to-Print: API key not configured")

        # ── RapidAPI OCR Extract ──
        if self.rapidapi_keys.get('ocr_extract'):
            t0 = time.time()
            logger.info("Attempting OCR Extract...")
            result = self._try_ocr_extract(image_path)
            elapsed = time.time() - t0
            if result.get('success') and self._is_plausible_ocr(result.get('text', '')):
                logger.info(f"OCR Extract succeeded in {elapsed:.1f}s")
                return result
            logger.warning(f"OCR Extract failed ({elapsed:.1f}s): {result.get('error', 'short/empty output')}")
            errors.append(f"OCR Extract ({elapsed:.1f}s): {result.get('error', 'short/empty output')}")
        else:
            errors.append("OCR Extract: API key not configured")

        # ── Tesseract (terminal fallback — local, zero latency, no rate limit) ──
        t0 = time.time()
        tesseract_result = self._try_tesseract(image_path)
        elapsed = time.time() - t0
        if tesseract_result.get('success') and self._is_plausible_ocr(tesseract_result.get('text', '')):
            logger.info(f"Tesseract local OCR succeeded in {elapsed:.1f}s (last-resort fallback)")
            return tesseract_result
        errors.append(f"Tesseract ({elapsed:.1f}s): {tesseract_result.get('error', 'short/empty output')}")

        # ── All providers exhausted — use partial result if available ──
        # A partial result has student info from a vision model; the Q&A
        # was empty but we can still return it so the caller can at least
        # record the student and flag manual review.
        if partial_result is not None:
            logger.warning("No provider extracted Q&A. Using partial result with student info.")
            return partial_result

        total = time.time() - cascade_start
        logger.error(f"All OCR methods failed after {total:.1f}s. Errors: {errors}")
        return {
            'success': False,
            'error': 'All OCR providers are currently unavailable (rate-limited or not configured)',
            'details': errors,
            'hint': (
                'Free-tier quota is exhausted. Wait ~1 minute and retry, or set up a '
                'fallback: install Tesseract for offline OCR '
                '(https://github.com/UB-Mannheim/tesseract/wiki), or add a RapidAPI '
                'Pen-to-Print key (handwriting OCR) in backend/.env.'
            ),
        }
    _RETRY_QA_PROMPT = (
        "The image contains an exam paper. You already confirmed student info is "
        "visible, so the image IS readable.\n\n"
        "Now extract EVERY question and its handwritten answer. Questions are "
        "typically labelled Q1, Q2, etc. and may include printed text like "
        "\"What is photosynthesis?\"  Handwritten answers appear below or beside "
        "each question.\n\n"
        "Return ONLY valid JSON (no markdown):\n"
        '{"qa_pairs": [\n'
        '  {"question_number": 1, "question": "exact printed question text", '
        '"answer": "exact handwritten answer text", "confidence": 0.9, '
        '"needs_teacher_correction": false}\n'
        "]}\n\n"
        "If a question or answer is hard to read, still include it with "
        "needs_teacher_correction=true and lower confidence."
    )

    def _retry_qa_extraction(self, file_bytes: bytes, filename: str, first_pass_json: dict) -> list:
        """Re-send the image with a forceful prompt that demands Q&A extraction.
        Called when the first pass returned student info but empty qa_pairs."""
        import json as _json

        # Downscale once (may already be done, but this is idempotent)
        try:
            img_bytes = self._downscale_image(file_bytes, self.MAX_EDGE_PX, self.JPEG_QUALITY)
        except Exception:
            img_bytes = file_bytes

        # Try Groq first (fastest), then Gemini, then OpenRouter
        result = None
        if self.groq_api_keys:
            result = self._retry_via_groq(img_bytes, filename)
        if not result and self.gemini_api_keys:
            result = self._retry_via_gemini(img_bytes, filename)
        if not result and self.openrouter_keys:
            result = self._retry_via_openrouter(img_bytes, filename)

        if not result:
            return []

        # Parse the retry response
        qa_pairs = []
        for qa in result.get('qa_pairs', []):
            q_text = qa.get('question') or f"Question {len(qa_pairs) + 1}"
            q_marks = extract_question_marks(q_text)
            entry = _with_parse_metadata({
                'question_number': qa.get('question_number', len(qa_pairs) + 1),
                'question_text': clean_ocr_question_text(q_text),
                'answer_text': qa.get('answer', '')
            }, qa.get('confidence'), 'retry_extraction', qa.get('needs_teacher_correction'))
            if q_marks is not None:
                entry['max_marks'] = q_marks
            qa_pairs.append(entry)
        return qa_pairs

    def _retry_via_groq(self, img_bytes: bytes, filename: str) -> dict:
        import requests, json as _json
        image_data = base64.b64encode(img_bytes).decode('utf-8')
        image_url = f"data:image/jpeg;base64,{image_data}"

        for api_key in self.groq_api_keys:
            for model in self.GROQ_OCR_MODELS:
                try:
                    resp = requests.post(
                        "https://api.groq.com/openai/v1/chat/completions",
                        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
                        json={
                            "model": model,
                            "messages": [{"role": "user", "content": [
                                {"type": "text", "text": self._RETRY_QA_PROMPT},
                                {"type": "image_url", "image_url": {"url": image_url}},
                            ]}],
                            "max_tokens": 4096, "temperature": 0,
                        },
                        timeout=(3.0, 30.0),
                    )
                    if resp.status_code == 200:
                        text = resp.json()["choices"][0]["message"]["content"]
                        parsed = self._parse_vision_json(text)
                        if parsed and parsed.get('qa_pairs'):
                            logger.info(f"Retry via Groq/{model} extracted {len(parsed['qa_pairs'])} Q&A pairs")
                            return parsed
                    elif resp.status_code == 429:
                        break
                except Exception as e:
                    logger.warning(f"Retry Groq/{model}: {e}")
        return None

    def _retry_via_gemini(self, img_bytes: bytes, filename: str) -> dict:
        try:
            from google import genai
            from google.genai import types
            import json as _json
        except ImportError:
            return None

        for api_key in self.gemini_api_keys:
            client = genai.Client(api_key=api_key)
            for model_name in self.GEMINI_OCR_MODELS:
                try:
                    response = client.models.generate_content(
                        model=model_name,
                        contents=[types.Content(parts=[
                            types.Part.from_text(text=self._RETRY_QA_PROMPT),
                            types.Part.from_bytes(data=img_bytes, mime_type='image/jpeg'),
                        ])],
                        config=types.GenerateContentConfig(response_mime_type='application/json'),
                    )
                    text = response.text
                    if text:
                        clean = re.sub(r',\s*([\]}])', r'\1', text.strip())
                        parsed = _json.loads(clean)
                        if parsed.get('qa_pairs'):
                            logger.info(f"Retry via Gemini/{model_name} extracted {len(parsed['qa_pairs'])} Q&A pairs")
                            return parsed
                except Exception as e:
                    logger.warning(f"Retry Gemini/{model_name}: {self._summarize_provider_error(e)}")
        return None

    def _retry_via_openrouter(self, img_bytes: bytes, filename: str) -> dict:
        import requests
        image_data = base64.b64encode(img_bytes).decode('utf-8')
        image_url = f"data:image/jpeg;base64,{image_data}"

        for api_key in self.openrouter_keys:
            for model in self.OPENROUTER_VISION_MODELS:
                try:
                    resp = requests.post(
                        "https://openrouter.ai/api/v1/chat/completions",
                        headers={
                            "Authorization": f"Bearer {api_key}",
                            "HTTP-Referer": self.site_url,
                            "Content-Type": "application/json",
                        },
                        json={
                            "model": model,
                            "messages": [{"role": "user", "content": [
                                {"type": "text", "text": self._RETRY_QA_PROMPT},
                                {"type": "image_url", "image_url": {"url": image_url}},
                            ]}],
                            "max_tokens": 4096,
                        },
                        timeout=(3.0, 15.0),
                    )
                    if resp.status_code == 200:
                        text = resp.json()["choices"][0]["message"]["content"]
                        parsed = self._parse_vision_json(text)
                        if parsed and parsed.get('qa_pairs'):
                            logger.info(f"Retry via OpenRouter/{model} extracted {len(parsed['qa_pairs'])} Q&A pairs")
                            return parsed
                    elif resp.status_code == 429:
                        break
                except Exception as e:
                    logger.warning(f"Retry OpenRouter/{model}: {e}")
        return None

    def _try_gemini(self, image_path: str, api_key: str = None) -> dict:
        """Try Google Gemini vision OCR across the configured model list.
        A model that is rate-limited (429) or unavailable (404) falls through
        to the next, so a single dead free-tier model doesn't sink the attempt."""
        try:
            from google import genai
            from google.genai import types
            import json as _json
        except ImportError:
            return {'success': False, 'error': 'google-genai not installed (pip install google-genai)'}

        try:
            client = genai.Client(api_key=api_key or self.gemini_api_keys[0])
            with open(image_path, 'rb') as f:
                image_bytes = f.read()
            ext = Path(image_path).suffix.lower()
            mime_type = {
                '.jpg': 'image/jpeg', '.jpeg': 'image/jpeg',
                '.png': 'image/png', '.webp': 'image/webp',
            }.get(ext, 'image/jpeg')
        except Exception as e:
            return {'success': False, 'error': self._summarize_provider_error(e)}

        prompt = """Look at this exam paper image and extract ONLY the text that is actually visible and handwritten/printed on the paper.

CRITICAL RULES:
1. If there are NO questions visible, return empty qa_pairs array
2. If there are NO answers visible, return empty qa_pairs array
3. DO NOT make up or invent any text
4. ONLY extract text you can actually see in the image
5. If the image is blank or has no Q&A, return: {"subject": "None", "qa_pairs": []}
6. Copy the printed question ID/number exactly. If the question ID or answer is unclear, set needs_teacher_correction=true and confidence <= 0.5
7. Do not infer a model/correct answer; extract only the student's visible answer

Return ONLY valid JSON (no markdown, no extra text):
{
  "student_name": "name if visible or empty string",
  "student_id": "ID if visible or empty string",
  "subject": "subject name if visible or General",
  "total_marks": "total marks number if visible on paper header or null",
  "qa_pairs": [
    {
      "question_number": 1,
      "question_id": "printed ID such as Q1 if visible",
      "question": "ONLY actual visible question text",
      "answer": "ONLY actual visible answer text",
      "confidence": 0.0,
      "needs_teacher_correction": false
    }
  ]
}

If you cannot see clear printed question IDs and answers, return empty qa_pairs array."""

        last_err = 'no Gemini models configured'
        for model_name in self.GEMINI_OCR_MODELS:
            try:
                response = client.models.generate_content(
                    model=model_name,
                    contents=[
                        types.Content(parts=[
                            types.Part.from_text(text=prompt),
                            types.Part.from_bytes(data=image_bytes, mime_type=mime_type),
                        ])
                    ],
                    config=types.GenerateContentConfig(
                        response_mime_type='application/json',
                    ),
                )
                text = response.text
                if text and text.strip():
                    try:
                        clean_text = re.sub(r',\s*([\]}])', r'\1', text.strip())
                        parsed = _json.loads(clean_text)
                        return {'success': True, 'text': text, 'parsed_json': parsed,
                                'model': model_name, 'platform': 'Gemini'}
                    except _json.JSONDecodeError:
                        return {'success': True, 'text': text,
                                'model': model_name, 'platform': 'Gemini'}
                last_err = f'empty response ({model_name})'
            except Exception as e:
                last_err = self._summarize_provider_error(e)
                logger.warning(f"Gemini {model_name}: {last_err}; trying next model")
                continue

        return {'success': False, 'error': last_err}

    # Configurable OpenRouter vision model list.
    # Ordered by observed reliability from backend logs.
    # nemotron-nano-12b is the fastest and most reliable (~9-15s).
    # Trim further if you see consistent failures in the logs.
    OPENROUTER_VISION_MODELS = [
        "nvidia/nemotron-nano-12b-v2-vl:free",
        "nvidia/nemotron-3-nano-omni-30b-a3b-reasoning:free",
        "openrouter/free",
    ]

    @staticmethod
    def _parse_vision_json(text):
        """Strip markdown fences / trailing commas and parse JSON; None on failure."""
        import json as _json
        clean = text.strip()
        if clean.startswith('```'):
            clean = re.sub(r'^```[a-zA-Z]*\n?', '', clean)
            if clean.endswith('```'):
                clean = clean.rsplit('```', 1)[0]
        clean = re.sub(r',\s*([\]}])', r'\1', clean.strip())
        try:
            return _json.loads(clean)
        except Exception:
            return None

    def _try_groq(self, image_path: str) -> dict:
        """Groq vision OCR via the OpenAI-compatible endpoint. Tries each key x
        model and fails over to the next key on 429 (Groq has a separate quota)."""
        import requests
        import base64

        try:
            with open(image_path, 'rb') as f:
                image_data = base64.b64encode(f.read()).decode('utf-8')
            ext = Path(image_path).suffix.lower()
            mime_type = {
                '.jpg': 'image/jpeg', '.jpeg': 'image/jpeg', '.png': 'image/png',
                '.webp': 'image/webp', '.gif': 'image/gif',
            }.get(ext, 'image/jpeg')
            image_url = f"data:{mime_type};base64,{image_data}"
        except Exception as e:
            return {'success': False, 'error': self._summarize_provider_error(e)}

        errors = []
        for key_idx, api_key in enumerate(self.groq_api_keys, 1):
            for model in self.GROQ_OCR_MODELS:
                t0 = time.time()
                try:
                    resp = requests.post(
                        "https://api.groq.com/openai/v1/chat/completions",
                        headers={
                            "Authorization": f"Bearer {api_key}",
                            "Content-Type": "application/json",
                        },
                        json={
                            "model": model,
                            "messages": [{
                                "role": "user",
                                "content": [
                                    {"type": "text", "text": _OCR_PROMPT},
                                    {"type": "image_url", "image_url": {"url": image_url}},
                                ],
                            }],
                            "max_tokens": 4096,
                            "temperature": 0,
                        },
                        timeout=(3.0, 30.0),
                    )
                    elapsed = time.time() - t0
                    if resp.status_code == 200:
                        text = resp.json()["choices"][0]["message"]["content"]
                        if text and text.strip():
                            result = {'success': True, 'text': text, 'model': model, 'platform': 'Groq'}
                            parsed = self._parse_vision_json(text)
                            if parsed is not None:
                                result['parsed_json'] = parsed
                            logger.info(f"Groq key {key_idx} model {model} succeeded in {elapsed:.1f}s")
                            return result
                        errors.append(f"key{key_idx}/{model} ({elapsed:.1f}s): empty response")
                    elif resp.status_code == 429:
                        errors.append(f"key{key_idx}/{model} ({elapsed:.1f}s): rate limited")
                        break  # account exhausted — fail over to the next key
                    else:
                        errors.append(f"key{key_idx}/{model} ({elapsed:.1f}s): HTTP {resp.status_code} {resp.text[:120]}")
                except Exception as e:
                    errors.append(f"key{key_idx}/{model}: {self._summarize_provider_error(e)}")

        return {'success': False, 'error': 'All Groq models failed', 'details': errors}

    def _try_openrouter(self, image_path: str) -> dict:
        """Try each OpenRouter key against the vision model list.

        Free-tier limits are per-account, so when a key is rate-limited we skip
        its remaining models and fail over to the next key (a different account
        with its own quota).
        """
        errors = []
        for key_idx, api_key in enumerate(self.openrouter_keys, 1):
            for model in self.OPENROUTER_VISION_MODELS:
                t0 = time.time()
                logger.info(f"Attempting OpenRouter key {key_idx}, model: {model}")
                result = self._call_openrouter_model(image_path, model, api_key)
                elapsed = time.time() - t0
                if result.get('success') and self._is_plausible_ocr(result.get('text', '')):
                    logger.info(f"OpenRouter key {key_idx} model {model} succeeded in {elapsed:.1f}s")
                    return result

                error_msg = result.get('error', 'short/empty output') if not result.get('success') \
                    else 'implausibly short output'
                errors.append(f"key{key_idx}/{model} ({elapsed:.1f}s): {error_msg}")

                low = str(error_msg).lower()
                if '429' in low or 'rate' in low or 'quota' in low:
                    logger.warning(f"OpenRouter key {key_idx} rate-limited; failing over to next key")
                    break  # this account is exhausted — go to the next key

        return {'success': False, 'error': 'All OpenRouter models failed', 'details': errors}

    def _call_openrouter_model(self, image_path: str, model_name: str, api_key: str = None) -> dict:
        """Helper to call a specific OpenRouter vision model with a given key."""
        try:
            import requests
            import base64
            
            # Encode image
            with open(image_path, 'rb') as f:
                image_data = base64.b64encode(f.read()).decode('utf-8')
            
            ext = Path(image_path).suffix.lower()
            mime_type = {
                '.jpg': 'image/jpeg',
                '.jpeg': 'image/jpeg',
                '.png': 'image/png',
                '.gif': 'image/gif',
                '.webp': 'image/webp'
            }.get(ext, 'image/jpeg')
            
            image_url = f"data:{mime_type};base64,{image_data}"
            
            headers = {
                "Authorization": f"Bearer {api_key or self.openrouter_key}",
                "HTTP-Referer": self.site_url,
                "Content-Type": "application/json"
            }

            payload = {
                "model": model_name,
                "messages": [{
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": """Look at this exam paper image and extract ONLY the text that is actually visible and handwritten/printed on the paper.

CRITICAL RULES:
1. If there are NO questions visible, return empty qa_pairs array
2. If there are NO answers visible, return empty qa_pairs array  
3. DO NOT make up or invent any text
4. ONLY extract text you can actually see in the image
5. If the image is blank or has no Q&A, return: {"subject": "None", "qa_pairs": []}
6. Copy the printed question ID/number exactly. If the question ID or answer is unclear, set needs_teacher_correction=true and confidence <= 0.5
7. Do not infer a model/correct answer; extract only the student's visible answer

Return ONLY valid JSON (no markdown, no extra text):
{
  "student_name": "name if visible or empty string",
  "student_id": "ID if visible or empty string",
  "subject": "subject name if visible or General",
  "total_marks": "total marks number if visible on paper header or null",
  "qa_pairs": [
    {
      "question_number": 1,
      "question_id": "printed ID such as Q1 if visible",
      "question": "ONLY actual visible question text",
      "answer": "ONLY actual visible answer text",
      "confidence": 0.0,
      "needs_teacher_correction": false
    }
  ]
}

If you cannot see clear printed question IDs and answers, return empty qa_pairs array."""
                        },
                        {
                            "type": "image_url",
                            "image_url": {"url": image_url}
                        }
                    ]
                }],
                "max_tokens": 4096
            }
            
            response = requests.post(
                "https://openrouter.ai/api/v1/chat/completions",
                headers=headers,
                json=payload,
                timeout=(3.0, 15.0)
            )
            response.raise_for_status()
            response_json = response.json()
            text = response_json["choices"][0]["message"]["content"]
            
            if text and text.strip():
                # Try to parse JSON response
                try:
                    import json
                    # Clean up the response - remove markdown formatting if present
                    clean_text = text.strip()
                    # Strip markdown code fences (```json ... ``` or ``` ... ```)
                    if clean_text.startswith('```'):
                        clean_text = re.sub(r'^```[a-zA-Z]*\n?', '', clean_text)
                    if clean_text.endswith('```'):
                        clean_text = clean_text.rsplit('```', 1)[0]
                    clean_text = clean_text.strip()
                    # Remove trailing commas before } or ] (common LLM JSON mistake)
                    clean_text = re.sub(r',\s*([\]}])', r'\1', clean_text)

                    parsed = json.loads(clean_text)
                    return {
                        'success': True,
                        'text': text,
                        'parsed_json': parsed,
                        'model': model_name,
                        'platform': 'OpenRouter'
                    }
                except json.JSONDecodeError:
                    # Return raw text if JSON parsing fails
                    return {
                        'success': True,
                        'text': text,
                        'model': model_name,
                        'platform': 'OpenRouter'
                    }
            else:
                return {'success': False, 'error': 'Empty response from model'}
                
        except Exception as e:
            summary = self._summarize_provider_error(e)
            logger.error(f"OpenRouter model {model_name} error: {summary}")
            return {'success': False, 'error': summary}
    
    def _try_pen_to_print(self, image_path: str) -> dict:
        """Try RapidAPI Pen-to-Print OCR"""
        try:
            import requests
            
            ext = Path(image_path).suffix.lower()
            mime_type = "image/png" if ext == ".png" else "image/jpeg"
            
            with open(image_path, 'rb') as f:
                file_data = f.read()
            files = {
                'srcImg': (Path(image_path).name, file_data, mime_type)
            }
            data = {'Session': 'string'}
            headers = {
                'x-rapidapi-key': self.rapidapi_keys['pen_to_print'],
                'x-rapidapi-host': "pen-to-print-handwriting-ocr.p.rapidapi.com"
            }

            response = requests.post(
                "https://pen-to-print-handwriting-ocr.p.rapidapi.com/recognize/",
                files=files,
                data=data,
                headers=headers,
                timeout=30
            )
            
            result = response.json()
            text = result.get('value', '')
            
            if text and text.strip():
                return {
                    'success': True,
                    'text': text,
                    'model': 'Pen-to-Print',
                    'platform': 'RapidAPI'
                }
            else:
                return {'success': False, 'error': f'Empty response: {result}'}
                
        except Exception as e:
            return {'success': False, 'error': str(e)}
    
    def _try_ocr_extract(self, image_path: str) -> dict:
        """Try RapidAPI OCR Extract Text"""
        try:
            import requests
            
            # Read and encode image
            with open(image_path, 'rb') as f:
                image_data = base64.b64encode(f.read()).decode('utf-8')
            
            ext = Path(image_path).suffix.lower()
            mime_type = "image/png" if ext == ".png" else "image/jpeg"
            
            payload = {
                "base64": f"data:{mime_type};base64,{image_data}",
                "language": "eng"
            }
            
            headers = {
                "content-type": "application/json",
                "x-rapidapi-key": self.rapidapi_keys['ocr_extract'],
                "x-rapidapi-host": "ocr-extract-text.p.rapidapi.com"
            }
            
            response = requests.post(
                "https://ocr-extract-text.p.rapidapi.com/ocr",
                json=payload,
                headers=headers,
                timeout=30
            )
            
            result = response.json()
            text = result.get('text', '')
            
            if text and text.strip():
                return {
                    'success': True,
                    'text': text,
                    'model': 'OCR-Extract',
                    'platform': 'RapidAPI'
                }
            else:
                return {'success': False, 'error': f'Empty response: {result}'}
                
        except Exception as e:
            return {'success': False, 'error': str(e)}


    def _try_tesseract(self, image_path: str) -> dict:
        """
        Last-resort local OCR using Tesseract.
        Requires Tesseract binary installed on the system.
        Windows: https://github.com/UB-Mannheim/tesseract/wiki
        Linux:   sudo apt install tesseract-ocr
        macOS:   brew install tesseract
        """
        try:
            import pytesseract
            import shutil
            from PIL import Image

            # Locate the Tesseract binary: explicit env override → PATH → common
            # install locations (Windows/Linux/macOS). Without this the offline
            # fallback silently fails when tesseract isn't on PATH.
            tess_cmd = os.getenv('TESSERACT_CMD') or shutil.which('tesseract')
            if not tess_cmd:
                for candidate in (
                    r'C:\Program Files\Tesseract-OCR\tesseract.exe',
                    r'C:\Program Files (x86)\Tesseract-OCR\tesseract.exe',
                    os.path.expanduser(r'~\AppData\Local\Programs\Tesseract-OCR\tesseract.exe'),
                    os.path.expanduser(r'~\AppData\Local\Tesseract-OCR\tesseract.exe'),
                    '/usr/bin/tesseract', '/usr/local/bin/tesseract', '/opt/homebrew/bin/tesseract',
                ):
                    if os.path.exists(candidate):
                        tess_cmd = candidate
                        break
            if tess_cmd:
                pytesseract.pytesseract.tesseract_cmd = tess_cmd

            img = Image.open(image_path)
            # Use PSM 6 (assume uniform block of text) for exam papers
            text = pytesseract.image_to_string(img, config='--psm 6')

            if text and text.strip():
                logger.info(f"Tesseract extracted {len(text)} chars")
                return {
                    'success': True,
                    'text': text,
                    'model': 'Tesseract',
                    'platform': 'Local'
                }
            return {'success': False, 'error': 'Tesseract returned empty text'}

        except pytesseract.TesseractNotFoundError:
            return {
                'success': False,
                'error': (
                    'Tesseract binary not found. Install it from '
                    'https://github.com/UB-Mannheim/tesseract/wiki (Windows) '
                    'or run: sudo apt install tesseract-ocr (Linux)'
                )
            }
        except ImportError:
            return {'success': False, 'error': 'pytesseract not installed (pip install pytesseract pillow)'}
        except Exception as e:
            return {'success': False, 'error': f'Tesseract error: {type(e).__name__}: {e}'}


# Singleton instance
ocr_service = OCRService()


def parse_student_info(text: str) -> Dict[str, Optional[str]]:
    """
    Parse student information from extracted text.
    
    Returns:
        dict with keys: student_name, student_id, subject
    """
    result = {
        'student_name': None,
        'student_id': None,
        'subject': None,
        'total_marks': None
    }
    
    # Patterns for student name (various formats)
    name_patterns = [
        r'STUDENT[_\s]*NAME[:\s]*([^\n\r]+)',
        r'NAME[:\s]*([^\n\r]+)',
        r'Student\s*:\s*([^\n\r]+)',
        r'Name\s*:\s*([^\n\r]+)',
    ]
    
    for pattern in name_patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            name = match.group(1).strip()
            # Clean up common artifacts
            name = re.sub(r'[_\-]+$', '', name).strip()
            if name and len(name) > 1:
                result['student_name'] = name
                break
    
    # Patterns for student ID
    id_patterns = [
        r'STUDENT[_\s]*ID[:\s]*([A-Za-z0-9\-]+)',
        r'ROLL[_\s]*(?:NO|NUMBER|#)?[:\s]*([A-Za-z0-9\-]+)',
        r'ID[:\s]*([A-Za-z0-9\-]+)',
        r'Reg(?:istration)?[_\s]*(?:No|Number)?[:\s]*([A-Za-z0-9\-]+)',
    ]
    
    for pattern in id_patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            student_id = match.group(1).strip()
            if student_id and len(student_id) > 1:
                result['student_id'] = student_id
                break
    
    # Patterns for subject
    subject_patterns = [
        r'SUBJECT[:\s]*([^\n\r]+)',
        r'COURSE[:\s]*([^\n\r]+)',
        r'Paper[:\s]*([^\n\r]+)',
        r'Exam[:\s]*([^\n\r]+)',
        r'SCHOOL\s*SYSTEM\s*[\r\n]+([^\r\n]+(?:\s*-\s*[^\r\n]+)?)', # Matches template: IM SCHOOL SYSTEM \n Subject - Test
        r'^([^\n\r]+(?:\s*-\s*[^\n\r]+)?\s*(?:Test|Exam))' # Matches line ending with Test or Exam at the top
    ]
    
    for pattern in subject_patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            subject = match.group(1).strip()
            # Clean up common artifacts
            subject = re.sub(r'[_\-]+$', '', subject).strip()
            if subject and len(subject) > 1:
                result['subject'] = subject
                break
    
    # Patterns for total marks
    marks_patterns = [
        r'TOTAL[_\s]*MARKS[:\s]*(\d+(?:\.\d+)?)',
        r'MAX(?:IMUM)?[_\s]*MARKS[:\s]*(\d+(?:\.\d+)?)',
        r'MARKS[:\s]*(\d+(?:\.\d+)?)',
        r'Total[:\s]*(\d+(?:\.\d+)?)\s*(?:marks|Marks)',
    ]

    for pattern in marks_patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            result['total_marks'] = _parse_total_marks(match.group(1))
            break

    logger.info(f"Parsed student info: {result}")
    return result


def salvage_qa_from_malformed_json(text: str) -> List[Dict[str, str]]:
    """
    Salvage question-answer pairs from a malformed or truncated JSON string.
    """
    qa_pairs = []
    # Split text by '{' to get potential Q&A objects
    blocks = text.split('{')
    for block in blocks:
        block = block.strip()
        if not block or '"question"' not in block:
            continue
        
        # Extract question_number
        q_num_match = re.search(r'"question_number"\s*:\s*(\d+)', block)
        q_num = int(q_num_match.group(1)) if q_num_match else (len(qa_pairs) + 1)
        
        # Extract question (handling escaped quotes)
        q_text_match = re.search(r'"question"\s*:\s*"((?:[^"\\]|\\.)*)"', block, re.DOTALL)
        if not q_text_match:
            q_text_match = re.search(r'"question"\s*:\s*\'((?:[^\'\\]|\\.)*)\'', block, re.DOTALL)
        
        q_text = None
        if q_text_match:
            q_text = q_text_match.group(1).strip()
        else:
            # Salvage truncated question
            q_trunc_match = re.search(r'"question"\s*:\s*"(.*?)$', block, re.DOTALL)
            if q_trunc_match:
                q_text = q_trunc_match.group(1).strip()
                q_text = re.sub(r'["\s,{}]+$', '', q_text)
                
        # Extract answer
        ans_text_match = re.search(r'"answer"\s*:\s*"((?:[^"\\]|\\.)*)"', block, re.DOTALL)
        if not ans_text_match:
            ans_text_match = re.search(r'"answer"\s*:\s*\'((?:[^\'\\]|\\.)*)\'', block, re.DOTALL)
            
        ans_text = ''
        if ans_text_match:
            ans_text = ans_text_match.group(1).strip()
        else:
            # Salvage truncated answer
            ans_trunc_match = re.search(r'"answer"\s*:\s*"(.*?)$', block, re.DOTALL)
            if ans_trunc_match:
                ans_text = ans_trunc_match.group(1).strip()
                ans_text = re.sub(r'["\s,{}]+$', '', ans_text)
                
        # Clean up escapes
        if q_text:
            q_text = q_text.replace('\\"', '"').replace("\\'", "'").replace('\\n', '\n').replace('\\t', '\t')
        if ans_text:
            ans_text = ans_text.replace('\\"', '"').replace("\\'", "'").replace('\\n', '\n').replace('\\t', '\t')
            
        if q_text:
            q_marks = extract_question_marks(q_text)
            entry = _with_parse_metadata({
                'question_number': q_num,
                'question_text': clean_ocr_question_text(q_text),
                'answer_text': ans_text
            }, 0.55, 'salvaged_json')
            if q_marks is not None:
                entry['max_marks'] = q_marks
            qa_pairs.append(entry)
    return qa_pairs


def extract_question_marks(q_text: str) -> Optional[float]:
    """Extract per-question marks from patterns like [5 Marks] or (5 marks) at the end of question text."""
    if not q_text:
        return None
    match = re.search(r'[\[\(]\s*(\d+(?:\.\d+)?)\s*[mM]arks?\s*[\]\)]', q_text)
    if match:
        try:
            return float(match.group(1))
        except (ValueError, TypeError):
            return None
    return None


def clean_ocr_question_text(q_text: str) -> str:
    if not q_text:
        return ""
    # Remove leading Q1, Q2. etc
    q_text = re.sub(r'^(?:Question|Q)\s*\d+[\.\)\:]?\s*', '', q_text, flags=re.IGNORECASE)
    # Remove trailing [5 Marks] or (5 marks)
    q_text = re.sub(r'\s*[\[\(]\d+\s*[mM]arks?[\]\)]\s*$', '', q_text, flags=re.IGNORECASE)
    # Clean up trailing punctuation if it's just dots
    q_text = re.sub(r'[\.\s\?]+\s*$', '?', q_text)
    if not q_text.endswith('?') and len(q_text) > 2:
        q_text += '?'
    return q_text.strip()


def _bounded_confidence(value, default: float) -> float:
    try:
        confidence = float(value)
    except (TypeError, ValueError):
        confidence = 0.85 if default is None else float(default)
    return max(0.0, min(1.0, confidence))


def _is_generic_question_text(question_text: str) -> bool:
    normalized = (question_text or '').strip().lower()
    return (
        not normalized
        or normalized == 'full response'
        or re.fullmatch(r'question\s+\d+\??', normalized) is not None
    )


def _with_parse_metadata(
    qa: Dict[str, str],
    confidence: float,
    parse_status: str,
    needs_teacher_correction: Optional[bool] = None,
) -> Dict[str, str]:
    q_text = qa.get('question_text', '')
    answer_text = qa.get('answer_text', '')
    bounded = _bounded_confidence(confidence, confidence)
    if needs_teacher_correction is None:
        needs_teacher_correction = (
            bounded < 0.7
            or _is_generic_question_text(q_text)
            or not answer_text.strip()
        )
    qa['ocr_confidence'] = round(bounded, 3)
    qa['parse_status'] = parse_status
    qa['needs_teacher_correction'] = bool(needs_teacher_correction)
    return qa

def parse_question_answers(text: str) -> List[Dict[str, str]]:
    """
    Parse question-answer pairs from extracted text.
    
    Returns:
        List of dicts with keys: question_number, question_text, answer_text
    """
    qa_pairs = []
    
    # Try parsing using specific QUESTION / ANSWER blocks first (most reliable for text output)
    # Matches:
    # QUESTION 1: What is...?
    # ANSWER 1: It is...
    qa_blocks = re.findall(
        r'Q(?:uestion)?\s*(\d+)[:\.\)]\s*(.+?)\s*(?:A(?:nswer|ns)?\s*(?:\1[:\.\)]|[:\)=])\s*)(.+?)(?=Q(?:uestion)?\s*\d+[:\.\)]|$)',
        text,
        re.IGNORECASE | re.DOTALL
    )
    if qa_blocks:
        for q_num, q_val, a_val in qa_blocks:
            q_marks = extract_question_marks(q_val)
            entry = _with_parse_metadata({
                'question_number': int(q_num),
                'question_text': clean_ocr_question_text(q_val.strip()),
                'answer_text': a_val.strip()
            }, 0.92, 'question_answer_block')
            if q_marks is not None:
                entry['max_marks'] = q_marks
            qa_pairs.append(entry)
        logger.info(f"Parsed {len(qa_pairs)} Q&A pairs using QUESTION/ANSWER blocks")
        return qa_pairs
    
    # Multiple patterns to match different Q&A formats
    # Pattern 1: Q1: answer or Question 1: answer
    pattern1 = r'Q(?:uestion)?[\s]*(\d+)[:\.\)]\s*(.+?)(?=Q(?:uestion)?[\s]*\d+[:\.\)]|$)'
    
    # Try pattern 1 (Q1, Question 1 format)
    matches = re.findall(pattern1, text, re.IGNORECASE | re.DOTALL)
    
    if matches:
        for q_num, answer in matches:
            answer_clean = answer.strip()
            # Remove trailing question markers
            answer_clean = re.sub(r'\s*Q(?:uestion)?[\s]*\d+.*$', '', answer_clean, flags=re.IGNORECASE)
            
            question_text = f"Question {q_num}"
            if '?' in answer_clean:
                parts = answer_clean.split('?', 1)
                question_prompt = parts[0].strip()
                # Ensure it's a reasonable question prompt (not too long)
                if len(question_prompt) < 200:
                    question_text = f"{question_prompt}?"
                    answer_clean = parts[1].strip()
            
            if answer_clean or question_text != f"Question {q_num}":
                q_marks = extract_question_marks(question_text)
                parsed_question = clean_ocr_question_text(question_text)
                confidence = 0.72 if not _is_generic_question_text(parsed_question) else 0.45
                entry = _with_parse_metadata({
                    'question_number': int(q_num),
                    'question_text': parsed_question,
                    'answer_text': answer_clean.strip()
                }, confidence, 'loose_question_marker')
                if q_marks is not None:
                    entry['max_marks'] = q_marks
                qa_pairs.append(entry)
    
    # If no Q&A pattern found, treat entire text as one answer
    if not qa_pairs and text.strip():
        # Remove header info before treating as answer
        answer_text = text
        # Remove common header patterns
        answer_text = re.sub(r'^.*?(?:STUDENT|NAME|ID|ROLL|SUBJECT|COURSE).*?\n', '', answer_text, flags=re.IGNORECASE | re.MULTILINE)
        answer_text = answer_text.strip()
        
        if answer_text:
            qa_pairs.append(_with_parse_metadata({
                'question_number': 1,
                'question_text': "Full Response",
                'answer_text': answer_text[:1000]  # Limit to 1000 chars
            }, 0.2, 'full_response_fallback', True))
    
    logger.info(f"Parsed {len(qa_pairs)} Q&A pairs")
    return qa_pairs


def _parse_total_marks(value) -> float | None:
    """Safely convert an OCR-extracted total_marks value to float."""
    if value is None or value == '' or value == 'null':
        return None
    try:
        v = float(value)
        return v if v > 0 else None
    except (ValueError, TypeError):
        # Try extracting a number from strings like "50 marks"
        m = re.search(r'(\d+(?:\.\d+)?)', str(value))
        if m:
            return float(m.group(1))
        return None


def extract_text(file_bytes: bytes, filename: str) -> dict:
    """
    Extract and parse text from file bytes.
    
    Returns:
        dict with keys:
        - success: bool
        - raw_text: str (full extracted text)
        - student_name: str or None
        - student_id: str or None
        - subject: str or None
        - total_marks: float or None
        - questions: list of Q&A dicts
        - model: str (model name used)
        - platform: str ('OpenRouter' or 'RapidAPI')
        - error: str (if failed)
    """
    # First, extract raw text using OCR
    ocr_result = ocr_service.extract_text_from_bytes(file_bytes, filename)
    
    if not ocr_result.get('success'):
        return ocr_result
    
    raw_text = ocr_result.get('text', '')
    
    # Check if we have parsed JSON from OCR (new structured prompt)
    parsed_json = ocr_result.get('parsed_json')
    
    if parsed_json:
        # Use structured JSON response directly
        logger.info("Using structured JSON response from OCR")

        student_name = parsed_json.get('student_name', '') or None
        student_id = parsed_json.get('student_id', '') or None
        subject = parsed_json.get('subject', '') or None
        total_marks = _parse_total_marks(parsed_json.get('total_marks'))

        # Convert qa_pairs to our format
        qa_pairs = []
        for qa in parsed_json.get('qa_pairs', []):
            q_text = qa.get('question') or qa.get('question_id') or f"Question {len(qa_pairs) + 1}"
            q_marks = extract_question_marks(q_text)
            entry = _with_parse_metadata({
                'question_number': qa.get('question_number', len(qa_pairs) + 1),
                'question_text': clean_ocr_question_text(q_text),
                'answer_text': qa.get('answer', '')
            }, qa.get('confidence'), 'structured_json', qa.get('needs_teacher_correction'))
            if q_marks is not None:
                entry['max_marks'] = q_marks
            qa_pairs.append(entry)

        # If the vision model extracted student info but returned empty qa_pairs,
        # it was overly conservative.  Retry the SAME provider with a forceful
        # follow-up prompt that references the student info it already found,
        # proving the image IS readable.
        if not qa_pairs and (student_name or student_id):
            logger.warning(
                "Vision model returned student info but empty qa_pairs — "
                "retrying with explicit extraction prompt"
            )
            retry_result = ocr_service._retry_qa_extraction(file_bytes, filename, parsed_json)
            if retry_result:
                qa_pairs = retry_result
                logger.info(f"Retry extracted {len(qa_pairs)} Q&A pairs")

        logger.info(f"Parsed JSON: {len(qa_pairs)} Q&A pairs, Student: {student_name}")
    else:
        # Fallback to regex parsing
        logger.info("Falling back to regex parsing")

        # If raw text looks like JSON (OCR returned JSON but it was unparseable),
        # try once more after aggressive cleaning before falling back to regex
        salvaged = None
        stripped = raw_text.strip()
        if stripped.startswith('{') or stripped.startswith('['):
            try:
                import json as _json
                clean = re.sub(r',\s*([\]}])', r'\1', stripped)
                salvaged = _json.loads(clean)
                logger.info("Salvaged JSON from raw_text on second attempt")
            except Exception:
                salvaged = None

        if salvaged:
            student_name = salvaged.get('student_name', '') or None
            student_id = salvaged.get('student_id', '') or None
            subject = salvaged.get('subject', '') or None
            total_marks = _parse_total_marks(salvaged.get('total_marks'))
            qa_pairs = []
            for qa in salvaged.get('qa_pairs', []):
                q_text = qa.get('question') or qa.get('question_id') or f"Question {len(qa_pairs) + 1}"
                q_marks = extract_question_marks(q_text)
                entry = _with_parse_metadata({
                    'question_number': qa.get('question_number', len(qa_pairs) + 1),
                    'question_text': clean_ocr_question_text(q_text),
                    'answer_text': qa.get('answer', '')
                }, qa.get('confidence'), 'recovered_json', qa.get('needs_teacher_correction'))
                if q_marks is not None:
                    entry['max_marks'] = q_marks
                qa_pairs.append(entry)
        elif '"question"' in raw_text or '"answer"' in raw_text or '"qa_pairs"' in raw_text:
            # Salvage from malformed or truncated JSON using the robust regex-based salvage parser
            logger.info("Salvaging Q&A pairs and info from malformed/truncated JSON")
            qa_pairs = salvage_qa_from_malformed_json(raw_text)
            
            student_name_match = re.search(r'"student_name"\s*:\s*"((?:[^"\\]|\\.)*)"', raw_text)
            student_name = student_name_match.group(1) if student_name_match else None
            if student_name:
                student_name = student_name.replace('\\"', '"').replace("\\'", "'").replace('\\n', '\n').replace('\\t', '\t')
                
            student_id_match = re.search(r'"student_id"\s*:\s*"((?:[^"\\]|\\.)*)"', raw_text)
            student_id = student_id_match.group(1) if student_id_match else None
            if student_id:
                student_id = student_id.replace('\\"', '"').replace("\\'", "'").replace('\\n', '\n').replace('\\t', '\t')
                
            subject_match = re.search(r'"subject"\s*:\s*"((?:[^"\\]|\\.)*)"', raw_text)
            subject = subject_match.group(1) if subject_match else None
            if subject:
                subject = subject.replace('\\"', '"').replace("\\'", "'").replace('\\n', '\n').replace('\\t', '\t')

            total_marks_match = re.search(r'"total_marks"\s*:\s*"?(\d+(?:\.\d+)?)"?', raw_text)
            total_marks = _parse_total_marks(total_marks_match.group(1)) if total_marks_match else None
        else:
            # Parse student info
            student_info = parse_student_info(raw_text)
            student_name = student_info.get('student_name')
            student_id = student_info.get('student_id')
            subject = student_info.get('subject')
            total_marks = student_info.get('total_marks')

            # Parse Q&A pairs
            qa_pairs = parse_question_answers(raw_text)
    
    logger.info(f"OCR complete. Found {len(qa_pairs)} questions, Student: {student_name}")
    
    return {
        'success': True,
        'raw_text': raw_text,
        'student_name': student_name,
        'student_id': student_id,
        'subject': subject,
        'total_marks': total_marks,
        'questions': qa_pairs,
        'model': ocr_result.get('model'),
        'platform': ocr_result.get('platform')
    }
