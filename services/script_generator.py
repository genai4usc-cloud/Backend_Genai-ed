from supabase import create_client
from core.config import SUPABASE_URL, SUPABASE_SERVICE_KEY
from core.azure_openai import call_azure_openai
from services.prompt_builder import build_script_prompt

supabase = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)

async def generate_script(lecture_id: str):
    lecture = (
        supabase
        .table("lectures")
        .select("title, script_prompt, video_length")
        .eq("id", lecture_id)
        .single()
        .execute()
        .data
    )

    materials = (
        supabase
        .table("lecture_materials")
        .select("material_name, material_type")
        .eq("lecture_id", lecture_id)
        .execute()
        .data
    )

    main_materials = [m["material_name"] for m in materials if m["material_type"] == "main"]
    background_materials = [m["material_name"] for m in materials if m["material_type"] == "background"]

    prompt = build_script_prompt(
        lecture_title=lecture["title"] or "Untitled Lecture",
        ai_prompt=lecture["script_prompt"],
        video_length=lecture["video_length"],
        main_materials=main_materials,
        background_materials=background_materials,
    )

    script_text = await call_azure_openai(prompt)

    supabase.table("lectures").update({
        "script_text": script_text,
        "script_mode": "ai"
    }).eq("id", lecture_id).execute()

    return script_text
