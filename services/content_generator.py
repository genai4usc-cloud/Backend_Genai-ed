from supabase import create_client
from core.config import SUPABASE_URL, SUPABASE_SERVICE_KEY
from services.audio_generator import generate_audio_tts_and_upload
from services.ppt_generator import generate_pptx_and_upload
from services.video_generator import generate_video_avatar_and_upload

supabase = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)


def _create_job(lecture_id: str, job_type: str):
    res = (
        supabase.table("lecture_jobs")
        .insert(
            {
                "lecture_id": lecture_id,
                "job_type": job_type,
                "status": "queued",
                "progress": 0,
                "result": {},
                "error_message": None,
            }
        )
        .execute()
    )
    return res.data[0]


def _update_job(job_id: str, **fields):
    supabase.table("lecture_jobs").update(fields).eq("id", job_id).execute()


def _upsert_artifact(lecture_id: str, artifact_type: str, file_url: str, storage_path: str | None = None):
    payload = {
        "lecture_id": lecture_id,
        "artifact_type": artifact_type,
        "file_url": file_url,
        "artifact_url": file_url,
    }
    if storage_path is not None:
        payload["storage_path"] = storage_path

    supabase.table("lecture_artifacts").upsert(payload, on_conflict="lecture_id,artifact_type").execute()


async def generate_content_for_lecture(lecture_id: str):
    lecture = (
        supabase.table("lectures")
        .select("educator_id, content_style, script_text, avatar_character, avatar_style")
        .eq("id", lecture_id)
        .single()
        .execute()
        .data
    )

    educator_id = lecture["educator_id"]
    content_style = lecture.get("content_style") or []
    script_text = lecture.get("script_text") or ""
    avatar_character = lecture.get("avatar_character")
    avatar_style = lecture.get("avatar_style")

    if not script_text.strip():
        raise RuntimeError("Lecture has no script_text. Generate script first.")

    jobs_to_run = []

    # ✅ artifact_type must match frontend expectations:
    # JOB_TO_ARTIFACT: audio -> "audio", pptx -> "pptx", video_avatar -> "video_avatar"
    if "audio" in content_style:
        jobs_to_run.append(("audio", "audio"))  # ✅ was "audio_mp3"

    if "powerpoint" in content_style:
        jobs_to_run.append(("pptx", "pptx"))

    if "video" in content_style:
        if not avatar_character or not avatar_style:
            raise RuntimeError("Lecture missing avatar_character/avatar_style (Step 5).")
        jobs_to_run.append(("video_avatar", "video_avatar"))  # ✅ was "video_avatar_mp4"

    # ✅ recommended: fail fast if user selected nothing
    if not jobs_to_run:
        raise RuntimeError("No content_style selected. Choose at least one of: audio, powerpoint, video.")

    created_jobs = {}
    for job_type, _artifact_type in jobs_to_run:
        created_jobs[job_type] = _create_job(lecture_id, job_type)

    for job_type, artifact_type in jobs_to_run:
        job = created_jobs[job_type]
        job_id = job["id"]

        try:
            _update_job(job_id, status="running", progress=10, result={}, error_message=None)

            if job_type == "audio":
                url, path = await generate_audio_tts_and_upload(lecture_id, educator_id, script_text)
                _upsert_artifact(lecture_id, artifact_type, url, path)

            elif job_type == "pptx":
                url, path = await generate_pptx_and_upload(lecture_id, educator_id, script_text)
                _upsert_artifact(lecture_id, artifact_type, url, path)

            elif job_type == "video_avatar":
                url, path = await generate_video_avatar_and_upload(
                    lecture_id=lecture_id,
                    educator_id=educator_id,
                    script_text=script_text,
                    avatar_character=avatar_character,
                    avatar_style=avatar_style,
                    job_id=job_id,
                )
                _upsert_artifact(lecture_id, artifact_type, url, path)

            _update_job(job_id, status="succeeded", progress=100)

        except Exception as e:
            _update_job(job_id, status="failed", progress=100, result={"error": str(e)}, error_message=str(e))

    artifacts = (
        supabase.table("lecture_artifacts")
        .select("id, artifact_type, file_url")
        .eq("lecture_id", lecture_id)
        .execute()
        .data
    )

    has_any = any(a.get("file_url") for a in artifacts)
    if has_any:
        supabase.table("lectures").update({"status": "generated"}).eq("id", lecture_id).execute()

    return {
        "lecture_id": lecture_id,
        "jobs_created": list(created_jobs.keys()),
        "has_any_artifact": has_any,
        "artifacts": artifacts,
    }
