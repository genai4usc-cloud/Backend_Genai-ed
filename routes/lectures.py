from fastapi import APIRouter, HTTPException
from services.script_generator import generate_script
from core.azure_openai import supabase_client

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


@router.get("/debug/supabase")
def debug_supabase():
    url = os.getenv("SUPABASE_URL", "")
    # don’t expose the full key
    key_prefix = (os.getenv("SUPABASE_SERVICE_KEY", "") or "")[:8]

    test_id = "fab2523e-9b9c-47a8-b581-f7de4c232226"
    res = supabase_client.table("lectures").select("id").eq("id", test_id).execute()

    return {
        "supabase_url": url,
        "service_key_prefix": key_prefix,
        "rows_found_for_test_id": len(res.data or []),
        "data": res.data
    }