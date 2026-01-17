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
    try:
        result = await generate_content_for_lecture(lecture_id)

        if result is None:
            raise HTTPException(
                status_code=500,
                detail="generate_content_for_lecture returned None (expected dict). Check content_generator flow/early returns."
            )

        if not isinstance(result, dict):
            raise HTTPException(
                status_code=500,
                detail=f"generate_content_for_lecture returned {type(result)} (expected dict)."
            )

        return {"status": "success", **result}

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
