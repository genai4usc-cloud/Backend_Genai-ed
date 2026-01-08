from fastapi import APIRouter, HTTPException
from services.script_generator import generate_script

router = APIRouter(prefix="/lectures", tags=["Lectures"])

@router.post("/{lecture_id}/generate-script")
async def generate_lecture_script(lecture_id: str):
    try:
        script = await generate_script(lecture_id)
        return {
            "status": "success",
            "script": script
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
