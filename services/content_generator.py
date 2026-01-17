from supabase import create_client
from core.config import SUPABASE_URL, SUPABASE_SERVICE_KEY
from services.audio_generator import generate_audio_tts_and_upload
from services.ppt_generator import generate_pptx_and_upload
from services.video_generator import generate_video_avatar_and_upload

supabase = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)

def _upsert_job(lecture_id: str, job_type: str, status: str, progress: int, result: dict | None = None):
    # If your lecture_jobs has a uniqueness constraint (lecture_id, job_type) you can upsert.
    # If not, you can "select maybeSingle then update else insert".
    existing = (
        supabase.table("lecture_jobs")
        .select("id")
        .eq("lecture_id", lecture_id)
        .eq("job_type", job_type)
        .maybe_single()
        .execute()
        .data
    )
    payload = {"status": status, "progress": progress}
    if result is not None:
        payload["result"] = result

    if existing and existing.get("id"):
        supabase.table("lecture_jobs").update(payload).eq("id", existing["id"]).execute()
        return existing["id"]

    inserted = (
        supabase.table("lecture_jobs")
        .insert({"lecture_id": lecture_id, "job_type": job_type, **payload})
        .select("id")
        .single()
        .execute()
        .data
    )
    return inserted["id"]

def _upsert_artifact(lecture_id: str, artifact_type: str, file_url: str):
    existing = (
        supabase.table("lecture_artifacts")
        .select("id")
        .eq("lecture_id", lecture_id)
        .eq("artifact_type", artifact_type)
        .maybe_single()
        .execute()
        .data
    )
    if existing and existing.get("id"):
        supabase.table("lecture_artifacts").update({"file_url": file_url}).eq("id", existing["id"]).execute()
        return existing["id"]

    inserted = (
        supabase.table("lecture_artifacts")
        .insert({"lecture_id": lecture_id, "artifact_type": artifact_type, "file_url": file_url})
        .select("id")
        .single()
        .execute()
        .data
    )
    return inserted["id"]

async def generate_content_for_lecture(lecture_id: str) -> dict:
    lecture = (
        supabase.table("lectures")
        .select("id, script_text, content_style, avatar_character, avatar_style, educator_id")
        .eq("id", lecture_id)
        .single()
        .execute()
        .data
    )

    script_text = lecture.get("script_text") or ""
    if not script_text.strip():
        raise RuntimeError("No script_text found. Generate script first (Step 4).")

    styles = lecture.get("content_style") or []
    educator_id = lecture.get("educator_id")
    avatar_character = lecture.get("avatar_character")
    avatar_style = lecture.get("avatar_style")

    outputs = {}

    # AUDIO
    if "audio" in styles:
        job_id = _upsert_job(lecture_id, "audio", "running", 15)
        try:
            url = await generate_audio_tts_and_upload(
                lecture_id=lecture_id,
                educator_id=educator_id,
                script_text=script_text,
            )
            _upsert_artifact(lecture_id, "audio_mp3", url)
            _upsert_job(lecture_id, "audio", "succeeded", 100, {"file_url": url})
            outputs["audio_mp3"] = url
        except Exception as e:
            _upsert_job(lecture_id, "audio", "failed", 100, {"error": str(e)})
            raise

    # PPTX
    if "powerpoint" in styles:
        job_id = _upsert_job(lecture_id, "pptx", "running", 15)
        try:
            url = await generate_pptx_and_upload(
                lecture_id=lecture_id,
                educator_id=educator_id,
                script_text=script_text,
            )
            _upsert_artifact(lecture_id, "pptx", url)
            _upsert_job(lecture_id, "pptx", "succeeded", 100, {"file_url": url})
            outputs["pptx"] = url
        except Exception as e:
            _upsert_job(lecture_id, "pptx", "failed", 100, {"error": str(e)})
            raise

    # VIDEO (Avatar)
    if "video" in styles:
        _upsert_job(lecture_id, "video_avatar", "running", 10)
        try:
            url = await generate_video_avatar_and_upload(
                lecture_id=lecture_id,
                educator_id=educator_id,
                script_text=script_text,
                avatar_character=avatar_character,
                avatar_style=avatar_style,
            )
            _upsert_artifact(lecture_id, "video_avatar_mp4", url)
            _upsert_job(lecture_id, "video_avatar", "succeeded", 100, {"file_url": url})
            outputs["video_avatar_mp4"] = url
        except Exception as e:
            _upsert_job(lecture_id, "video_avatar", "failed", 100, {"error": str(e)})
            # ✅ DO NOT raise — let audio/ppt succeed


    return {"lecture_id": lecture_id, "artifacts": outputs}
