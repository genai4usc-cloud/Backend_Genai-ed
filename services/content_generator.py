import asyncio
from typing import Any, Dict, Optional

from supabase import create_client
from core.config import SUPABASE_URL, SUPABASE_SERVICE_KEY

from services.audio_generator import generate_audio_tts_and_upload
from services.ppt_generator import generate_pptx_and_upload
from services.video_generator import generate_video_avatar_and_upload

supabase = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)


def _first_row(resp) -> Optional[dict]:
    """
    supabase-py v2 returns an object with .data
    We always take first row if present.
    """
    data = getattr(resp, "data", None)
    if isinstance(data, list) and len(data) > 0:
        return data[0]
    return None


def _get_lecture(lecture_id: str) -> dict:
    resp = (
        supabase.table("lectures")
        .select("id, educator_id, content_style, script_text, avatar_character, avatar_style, avatar_voice")
        .eq("id", lecture_id)
        .limit(1)
        .execute()
    )
    lecture = _first_row(resp)
    if not lecture:
        raise RuntimeError(f"Lecture not found: {lecture_id}")
    return lecture


def _get_existing_job_id(lecture_id: str, job_type: str) -> Optional[str]:
    resp = (
        supabase.table("lecture_jobs")
        .select("id")
        .eq("lecture_id", lecture_id)
        .eq("job_type", job_type)
        .limit(1)
        .execute()
    )
    row = _first_row(resp)
    return row["id"] if row else None


def _get_existing_artifact_id(lecture_id: str, artifact_type: str) -> Optional[str]:
    resp = (
        supabase.table("lecture_artifacts")
        .select("id")
        .eq("lecture_id", lecture_id)
        .eq("artifact_type", artifact_type)
        .limit(1)
        .execute()
    )
    row = _first_row(resp)
    return row["id"] if row else None


def _upsert_job(lecture_id: str, job_type: str, patch: Dict[str, Any]) -> None:
    """
    Upsert lecture_jobs by (lecture_id, job_type) without relying on maybe_single().
    """
    existing_id = _get_existing_job_id(lecture_id, job_type)
    if existing_id:
        supabase.table("lecture_jobs").update(patch).eq("id", existing_id).execute()
    else:
        supabase.table("lecture_jobs").insert(
            {"lecture_id": lecture_id, "job_type": job_type, **patch}
        ).execute()


def _upsert_artifact(lecture_id: str, artifact_type: str, patch: Dict[str, Any]) -> None:
    """
    Upsert lecture_artifacts by (lecture_id, artifact_type) without relying on maybe_single().
    """
    existing_id = _get_existing_artifact_id(lecture_id, artifact_type)
    if existing_id:
        supabase.table("lecture_artifacts").update(patch).eq("id", existing_id).execute()
    else:
        supabase.table("lecture_artifacts").insert(
            {"lecture_id": lecture_id, "artifact_type": artifact_type, **patch}
        ).execute()


async def generate_content_for_lecture(lecture_id: str) -> dict:
    """
    Main pipeline:
    - reads lectures.content_style + script_text + avatar settings
    - creates/updates lecture_jobs for each required output
    - uploads artifacts and writes lecture_artifacts
    """
    lecture = _get_lecture(lecture_id)

    educator_id = lecture.get("educator_id")
    content_style = lecture.get("content_style") or []
    script_text = lecture.get("script_text") or ""

    if not educator_id:
        raise RuntimeError("Lecture educator_id missing")
    if not script_text.strip():
        raise RuntimeError("Lecture script_text missing (generate script first)")

    # Map style -> job_type + artifact_type
    required = []
    if "audio" in content_style:
        required.append(("audio", "audio_mp3"))
    if "powerpoint" in content_style:
        required.append(("pptx", "pptx"))
    if "video" in content_style:
        required.append(("video_avatar", "video_avatar_mp4"))

    # Create jobs as queued
    for job_type, _artifact_type in required:
        _upsert_job(
            lecture_id,
            job_type,
            {"status": "queued", "progress": 0, "error_message": None, "result": {}},
        )

    results: Dict[str, Any] = {"lecture_id": lecture_id, "jobs": {}}

    # AUDIO
    if ("audio", "audio_mp3") in required:
        job_type, artifact_type = "audio", "audio_mp3"
        _upsert_job(lecture_id, job_type, {"status": "running", "progress": 10})

        try:
            audio_url = await generate_audio_tts_and_upload(lecture_id, educator_id, script_text)
            _upsert_artifact(lecture_id, artifact_type, {"file_url": audio_url})

            _upsert_job(lecture_id, job_type, {"status": "succeeded", "progress": 100, "result": {}})
            results["jobs"][job_type] = {"status": "succeeded", "url": audio_url}
        except Exception as e:
            # IMPORTANT: do NOT raise — allow pptx/video to continue
            _upsert_job(
                lecture_id,
                job_type,
                {"status": "failed", "progress": 100, "result": {"error": str(e)}, "error_message": None},
            )
            results["jobs"][job_type] = {"status": "failed", "error": str(e)}

    # PPTX
    if ("pptx", "pptx") in required:
        job_type, artifact_type = "pptx", "pptx"
        _upsert_job(lecture_id, job_type, {"status": "running", "progress": 10})

        try:
            pptx_url = await generate_pptx_and_upload(lecture_id, educator_id, script_text)
            _upsert_artifact(lecture_id, artifact_type, {"file_url": pptx_url})

            _upsert_job(lecture_id, job_type, {"status": "succeeded", "progress": 100, "result": {}})
            results["jobs"][job_type] = {"status": "succeeded", "url": pptx_url}
        except Exception as e:
            _upsert_job(
                lecture_id,
                job_type,
                {"status": "failed", "progress": 100, "result": {"error": str(e)}, "error_message": None},
            )
            results["jobs"][job_type] = {"status": "failed", "error": str(e)}

    # VIDEO AVATAR
    if ("video_avatar", "video_avatar_mp4") in required:
        job_type, artifact_type = "video_avatar", "video_avatar_mp4"
        _upsert_job(lecture_id, job_type, {"status": "running", "progress": 10})

        try:
            # Your video generator currently raises "Not implemented" — this will mark job failed but not stop others.
            video_url = await generate_video_avatar_and_upload(lecture_id, educator_id, script_text)
            _upsert_artifact(lecture_id, artifact_type, {"file_url": video_url})

            _upsert_job(lecture_id, job_type, {"status": "succeeded", "progress": 100, "result": {}})
            results["jobs"][job_type] = {"status": "succeeded", "url": video_url}
        except Exception as e:
            _upsert_job(
                lecture_id,
                job_type,
                {"status": "failed", "progress": 100, "result": {"error": str(e)}, "error_message": None},
            )
            results["jobs"][job_type] = {"status": "failed", "error": str(e)}

    return {"status": "started", **results}
