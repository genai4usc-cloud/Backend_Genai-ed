from io import BytesIO
from pptx import Presentation
from supabase import create_client
from core.config import SUPABASE_URL, SUPABASE_SERVICE_KEY

supabase = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)


def _extract_ppt_script(script_text: str) -> str:
    marker = "PPT SCRIPT:"
    if marker in script_text:
        return script_text.split(marker, 1)[1].strip()
    return script_text.strip()


def _build_simple_ppt(ppt_script: str) -> bytes:
    prs = Presentation()

    # Super simple parsing: split by "- Slide"
    # If your script already uses "Slide X:" format, it will still work reasonably.
    chunks = [c.strip() for c in ppt_script.split("- Slide") if c.strip()]

    if not chunks:
        # fallback: one slide with all text
        slide = prs.slides.add_slide(prs.slide_layouts[1])
        slide.shapes.title.text = "Lecture Slides"
        slide.placeholders[1].text = ppt_script[:3000]
    else:
        for chunk in chunks[:25]:  # keep sane slide cap
            slide = prs.slides.add_slide(prs.slide_layouts[1])
            lines = [ln.strip() for ln in chunk.split("\n") if ln.strip()]
            title = lines[0].replace(":", "").strip() if lines else "Slide"
            body = "\n".join(lines[1:]) if len(lines) > 1 else ""

            slide.shapes.title.text = title[:120]
            slide.placeholders[1].text = body[:4000]

    bio = BytesIO()
    prs.save(bio)
    return bio.getvalue()


async def generate_pptx_and_upload(lecture_id: str, educator_id: str, script_text: str) -> tuple[str, str]:
    """
    Returns:
        (public_url, storage_path)
    """
    ppt_script = _extract_ppt_script(script_text)
    if not ppt_script:
        raise RuntimeError("No text found for PPT generation")

    pptx_bytes = _build_simple_ppt(ppt_script)

    storage_path = f"{educator_id}/{lecture_id}/artifacts/lecture.pptx"

    supabase.storage.from_("lecture-assets").upload(
        storage_path,
        pptx_bytes,
        file_options={
            "content-type": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
            "x-upsert": "true",
        },
    )

    public_url = supabase.storage.from_("lecture-assets").get_public_url(storage_path)
    return public_url, storage_path
