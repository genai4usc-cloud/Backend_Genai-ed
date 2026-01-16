from __future__ import annotations

from typing import List, Dict, Any, Optional, Tuple
import re
import io

import httpx
from pypdf import PdfReader
from docx import Document

from supabase import create_client
from core.config import SUPABASE_URL, SUPABASE_SERVICE_KEY
from core.azure_openai import call_azure_openai
from services.prompt_builder import build_script_prompt

supabase = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)

# -----------------------------
# File text extraction helpers
# -----------------------------

def _clean_text(s: str) -> str:
    s = re.sub(r"\s+", " ", s).strip()
    return s

def _extract_text_from_pdf_bytes(data: bytes) -> str:
    reader = PdfReader(io.BytesIO(data))
    parts: List[str] = []
    for page in reader.pages:
        try:
            parts.append(page.extract_text() or "")
        except Exception:
            continue
    return _clean_text("\n".join(parts))

def _extract_text_from_docx_bytes(data: bytes) -> str:
    doc = Document(io.BytesIO(data))
    parts = [p.text for p in doc.paragraphs if p.text]
    return _clean_text("\n".join(parts))

def _extract_text_from_txt_bytes(data: bytes) -> str:
    try:
        return _clean_text(data.decode("utf-8", errors="ignore"))
    except Exception:
        return ""

def _guess_ext_from_url(url: str, mime: Optional[str]) -> str:
    if mime:
        if "pdf" in mime:
            return "pdf"
        if "word" in mime or "docx" in mime:
            return "docx"
        if "text" in mime:
            return "txt"
    lower = url.lower()
    if lower.endswith(".pdf"):
        return "pdf"
    if lower.endswith(".docx"):
        return "docx"
    if lower.endswith(".txt"):
        return "txt"
    return ""


async def _download_and_extract(material: Dict[str, Any], timeout_s: int = 30) -> Tuple[str, str]:
    """
    Returns: (label, extracted_text)
    label is something like "main: HW1.pdf"
    """
    url = material.get("material_url")
    name = material.get("material_name") or "unknown"
    mtype = material.get("material_type") or "main"
    mime = material.get("file_mime")

    label = f"{mtype}: {name}"

    if not url:
        return (label, "")

    ext = _guess_ext_from_url(url, mime)

    # Only try text extraction for supported types
    if ext not in {"pdf", "docx", "txt"}:
        return (label, "")

    async with httpx.AsyncClient(follow_redirects=True, timeout=timeout_s) as client:
        r = await client.get(url)
        r.raise_for_status()
        data = r.content

    try:
        if ext == "pdf":
            return (label, _extract_text_from_pdf_bytes(data))
        if ext == "docx":
            return (label, _extract_text_from_docx_bytes(data))
        if ext == "txt":
            return (label, _extract_text_from_txt_bytes(data))
    except Exception:
        return (label, "")

    return (label, "")


def _truncate_for_prompt(text: str, max_chars: int = 18000) -> str:
    """
    Keeps prompt size sane. Adjust if needed.
    """
    if not text:
        return ""
    if len(text) <= max_chars:
        return text
    return text[:max_chars] + "\n\n[TRUNCATED]"


# -----------------------------
# Main script generation
# -----------------------------

async def generate_script(lecture_id: str) -> str:
    # 1) Pull lecture info (including step-3 selection content_style)
    lecture = (
        supabase
        .table("lectures")
        .select("title, script_prompt, video_length, content_style")
        .eq("id", lecture_id)
        .single()
        .execute()
        .data
    )

    if not lecture:
        raise ValueError(f"Lecture not found: {lecture_id}")

    title = lecture.get("title") or "Untitled Lecture"
    ai_prompt = lecture.get("script_prompt") or ""
    video_length = lecture.get("video_length") or 5
    content_style = lecture.get("content_style") or []  # ex: ["video","audio","powerpoint"]

    # Normalize styles
    selected_modes = []
    for s in content_style:
        s = str(s).lower().strip()
        if s in {"video", "audio", "powerpoint"}:
            selected_modes.append(s)

    # If none selected, default to video/audio/ppt so you still get output
    if not selected_modes:
        selected_modes = ["video", "audio", "powerpoint"]

    # 2) Pull ALL lecture materials from step 1 + step 2 (course-preloaded + uploaded)
    # IMPORTANT: you MUST select material_url, file_mime (and/or infer by URL), not just names.
    materials = (
        supabase
        .table("lecture_materials")
        .select("material_name, material_type, material_url, file_mime")
        .eq("lecture_id", lecture_id)
        .execute()
        .data
    ) or []

    # 3) Download + extract text for each material
    extracted_main: List[str] = []
    extracted_bg: List[str] = []
    main_names: List[str] = []
    bg_names: List[str] = []

    for m in materials:
        mname = m.get("material_name") or "unknown"
        mtype = (m.get("material_type") or "main").lower()

        if mtype == "main":
            main_names.append(mname)
        else:
            bg_names.append(mname)

    # Extract in sequence (simple + reliable).
    # If you want faster, we can parallelize with asyncio.gather later.
    for m in materials:
        label, text = await _download_and_extract(m)
        if not text:
            continue
        if (m.get("material_type") or "main").lower() == "main":
            extracted_main.append(f"[{label}]\n{text}")
        else:
            extracted_bg.append(f"[{label}]\n{text}")

    main_text = _truncate_for_prompt("\n\n".join(extracted_main))
    background_text = _truncate_for_prompt("\n\n".join(extracted_bg))

    # 4) Build a prompt that includes extracted text + selected modes
    prompt = build_script_prompt(
        lecture_title=title,
        ai_prompt=ai_prompt,
        video_length=video_length,
        main_materials=main_names,
        background_materials=bg_names,
        selected_modes=selected_modes,          # <-- NEW
        main_material_text=main_text,           # <-- NEW
        background_material_text=background_text # <-- NEW
    )

    # 5) Generate via Azure OpenAI
    script_text = await call_azure_openai(prompt)

    # 6) Save results back to Supabase
    supabase.table("lectures").update({
        "script_text": script_text,
        "script_mode": "ai",
        "status": "draft"
    }).eq("id", lecture_id).execute()

    return script_text
