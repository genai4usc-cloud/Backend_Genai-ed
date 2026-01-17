import io
import json
from pptx import Presentation
from supabase import create_client
from core.config import SUPABASE_URL, SUPABASE_SERVICE_KEY
from core.azure_openai import call_azure_openai

supabase = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)

def _extract_ppt_script(script_text: str) -> str:
    marker = "PPT SCRIPT:"
    if marker in script_text:
        return script_text.split(marker, 1)[1].strip()
    return script_text.strip()

def _build_ppt_prompt(script_text: str) -> str:
    ppt_text = _extract_ppt_script(script_text)
    return f"""
Convert the following lecture into a PowerPoint outline JSON.

Return ONLY valid JSON with this schema:
{{
  "title": "string",
  "slides": [
    {{
      "title": "string",
      "bullets": ["string", "string", "string"]
    }}
  ]
}}

Rules:
- 6 to 10 slides.
- Bullet points short and concrete.
- No markdown, no extra text.

Content:
{ppt_text}
""".strip()

def _make_pptx(outline: dict) -> bytes:
    prs = Presentation()
    title_slide_layout = prs.slide_layouts[0]
    bullet_slide_layout = prs.slide_layouts[1]

    # Title slide
    s0 = prs.slides.add_slide(title_slide_layout)
    s0.shapes.title.text = outline.get("title", "Lecture")
    if len(s0.placeholders) > 1:
        s0.placeholders[1].text = ""

    # Bullet slides
    for s in outline.get("slides", []):
        slide = prs.slides.add_slide(bullet_slide_layout)
        slide.shapes.title.text = s.get("title", "Slide")
        tf = slide.shapes.placeholders[1].text_frame
        tf.clear()
        for i, b in enumerate(s.get("bullets", [])):
            p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
            p.text = b

    buf = io.BytesIO()
    prs.save(buf)
    return buf.getvalue()

async def generate_pptx_and_upload(lecture_id: str, educator_id: str, script_text: str) -> str:
    prompt = _build_ppt_prompt(script_text)
    raw = await call_azure_openai(prompt)

    try:
        outline = json.loads(raw)
    except Exception:
        # If model returns stray text, force a “repair” pass
        repair = await call_azure_openai(f"Fix this into valid JSON only:\n{raw}")
        outline = json.loads(repair)

    pptx_bytes = _make_pptx(outline)

    storage_path = f"{educator_id}/{lecture_id}/artifacts/slides.pptx"
    supabase.storage.from_("lecture-assets").upload(
        storage_path,
        pptx_bytes,
        {"content-type": "application/vnd.openxmlformats-officedocument.presentationml.presentation", "upsert": True},
    )

    public = supabase.storage.from_("lecture-assets").get_public_url(storage_path)
    return public
