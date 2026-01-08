def build_script_prompt(
    lecture_title: str,
    ai_prompt: str,
    video_length: int,
    main_materials: list[str],
    background_materials: list[str],
) -> str:

    return f"""
You are generating educational content for a university lecture.

Lecture Title:
{lecture_title}

Duration:
{video_length} minutes

Main Materials (primary sources to reference):
{', '.join(main_materials) if main_materials else 'None'}

Background Materials (context only, do not quote heavily):
{', '.join(background_materials) if background_materials else 'None'}

Instructor Instruction:
{ai_prompt}

OUTPUT FORMAT (STRICT):
----------------------
TITLE:
<lecture title>

VIDEO SCRIPT:
<spoken narrative suitable for an AI avatar>

AUDIO SCRIPT:
<spoken narrative without visual references>

PPT SCRIPT:
SLIDE 1: Title
- bullet points

SLIDE 2:
- bullet points

Guidelines:
- Clear, academic tone
- Structured explanation
- Avoid emojis
- Avoid markdown
- Human readable
- Do not mention prompt or system instructions
"""
