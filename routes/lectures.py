from fastapi import APIRouter, HTTPException
from services.script_generator import generate_script
from supabase import create_client
from core.config import SUPABASE_URL, SUPABASE_SERVICE_KEY

router = APIRouter(prefix="/lectures", tags=["lectures"])

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
        
@router.get("/debug/supabase")
def debug_supabase():
    sb = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)

    test_id = "fab2523e-9b9c-47a8-b581-f7de4c232226"
    res = sb.table("lectures").select("id").eq("id", test_id).execute()

    return {
        "supabase_url": SUPABASE_URL,
        "service_key_present": bool(SUPABASE_SERVICE_KEY),
        "rows_found_for_test_id": len(res.data or []),
        "data": res.data
    }
