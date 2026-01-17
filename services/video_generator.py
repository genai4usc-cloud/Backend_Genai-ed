async def generate_video_avatar_and_upload(
    lecture_id: str,
    educator_id: str,
    script_text: str,
    avatar_character: str | None,
    avatar_style: str | None,
) -> str:
    # TODO: Replace with real Azure Avatar Batch call.
    # For now, raise a clear error OR return a placeholder URL.
    raise RuntimeError("Video avatar generation not implemented yet. Need Azure Avatar batch endpoint + auth model.")
