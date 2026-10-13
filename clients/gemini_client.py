# clients/gemini_client.py
import json
import streamlit as st
from google import genai
from google.genai import types


@st.cache_resource
def _get_client() -> genai.Client:
    return genai.Client(api_key=st.secrets["gemini"]["api_key"])


EXTRACTION_PROMPT = """\
You are a receipt parser. Look at the attached receipt image and return ONLY
a JSON object with these keys. Use null for any field you cannot determine.

{
  "merchant": string | null,
  "or_number": string | null,
  "transaction_date": "YYYY-MM-DD" | null,
  "documentation_date": "YYYY-MM-DD" | null,
  "currency": "PHP" | "USD" | "EUR" | "JPY" | null,
  "total_amount": number | null,
  "category": "Groceries" | "Utilities" | "Transport" | "Meals" | "Office" | "Other" | null,
  "description": string | null,
  "image_context": string,
  "raw_text": string
}

Rules:
- Numbers must be unquoted JSON numbers, no currency symbols.
- Dates must be ISO 8601 (YYYY-MM-DD).
- If total_amount and a line-item sum disagree, trust the printed total.
- Do not wrap the JSON in markdown fences.
"""


def _coerce_to_bytes_and_mime(source, mime_type=None) -> tuple[bytes, str]:
    """
    Accept either:
      - a Streamlit UploadedFile (has .getvalue() and .type)
      - raw bytes + explicit mime_type
    Return (bytes, mime_type).
    """
    # UploadedFile-like
    if hasattr(source, "getvalue") and hasattr(source, "type"):
        return source.getvalue(), source.type or "image/jpeg"

    # raw bytes path
    if isinstance(source, (bytes, bytearray)):
        if not mime_type:
            raise ValueError(
                "mime_type is required when passing raw bytes to extract_receipt."
            )
        return bytes(source), mime_type

    # BytesIO or file-like
    if hasattr(source, "read"):
        data = source.read()
        if not mime_type:
            mime_type = getattr(source, "type", None) or "image/jpeg"
        return data, mime_type

    raise TypeError(
        f"extract_receipt expected UploadedFile, bytes, or file-like; got {type(source)}"
    )


def extract_receipt(source, mime_type: str | None = None) -> dict:
    image_bytes, mime = _coerce_to_bytes_and_mime(source, mime_type)

    client = _get_client()
    response = client.models.generate_content(
        model="gemini-3.8-flash",
        contents=[
            types.Part.from_bytes(data=image_bytes, mime_type=mime),
            EXTRACTION_PROMPT,
        ],
        config=types.GenerateContentConfig(
            temperature=0.1,
            response_mime_type="application/json",
        ),
    )
    return json.loads(response.text)


def chat_over_receipt(question: str, context: dict, history: list | None = None) -> str:
    client = _get_client()
    compact = {
        "merchant": context.get("merchant"),
        "date": context.get("transaction_date"),
        "amount": context.get("total_amount"),
        "currency": context.get("currency"),
        "category": context.get("category"),
        "raw_text": (context.get("raw_text") or "")[:2000],
    }
    contents = [
        "You are a helpful receipt assistant. Answer questions about the "
        "receipt below. Be concise.\n\n"
        f"Receipt:\n{json.dumps(compact, ensure_ascii=False)}"
    ]
    for turn in history or []:
        contents.append(f"{turn['role'].capitalize()}: {turn['text']}")
    contents.append(f"User: {question}")

    response = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=contents,
        config=types.GenerateContentConfig(temperature=0.2),
    )
    return response.text