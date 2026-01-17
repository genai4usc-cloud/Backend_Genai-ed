from fastapi import APIRouter, HTTPException
from services.script_generator import generate_script
from services.content_generator import generate_content_for_lecture

router = APIRouter(prefix="/lectures", tags=["lectures"])

@router.post("/{lecture_id}/generate-script")
async def generate_lecture_script(lecture_id: str):
    try:
        script = await generate_script(lecture_id)
        return {"status": "success", "script": script}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/{lecture_id}/generate-content")
async def generate_lecture_content(lecture_id: str):
    """
    Stage 6:
    - Reads script_text (generated in step 4)
    - Reads avatar_character/avatar_style (step 5)
    - Reads content_style array (step 3)
    - Generates artifacts and writes to lecture_artifacts
    - Updates lecture_jobs per type
    """
    try:
        result = await generate_content_for_lecture(lecture_id)
        return {"status": "success", **result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
