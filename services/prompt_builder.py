from typing import List, Optional

def build_script_prompt(
    lecture_title: str,
    ai_prompt: str,
    video_length: int,
    main_materials: List[str],
    background_materials: List[str],
    selected_modes: List[str],
    main_material_text: str,
    background_material_text: str
) -> str:
    modes_line = ", ".join(selected_modes)

    return f"""
You are an expert educator and instructional designer.

TASK:
Create a lecture script grounded ONLY in the provided course materials content below.

Lecture Title: {lecture_title}
Desired Duration: {video_length} minutes
Educator Prompt / Instruction: {ai_prompt or "Create an engaging educational script based on the materials."}

OUTPUT RULES:
- Output ONLY the sections for the selected modes: {modes_line}
- Format MUST match exactly:
TITLE:
<...>

Then for each selected mode:
VIDEO SCRIPT:
<...>   (only if "video" selected)
AUDIO SCRIPT:
<...>   (only if "audio" selected)
PPT SCRIPT:
<...>    (only if "powerpoint" selected; include slides as bullet points)

CONSTRAINTS:
- Use the materials content below as the source of truth.
- If the materials are insufficient for a detail, say so briefly and move on.
- Be concise and structured. Make it teachable.

MATERIAL NAMES:
Main Materials: {", ".join(main_materials) or "None"}
Background Materials: {", ".join(background_materials) or "None"}

MATERIAL CONTENT (MAIN):
{main_material_text or "[No extractable main text found]"}

MATERIAL CONTENT (BACKGROUND):
{background_material_text or "[No extractable background text found]"}
""".strip()
