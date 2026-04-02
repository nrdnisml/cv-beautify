# src/core/orchestrator.py
import asyncio
import logging
from pathlib import Path
from typing import Dict, Any, List, Tuple
from functools import lru_cache

# Assuming you have an async wrapper for the Azure OpenAI call in your services layer
from src.services.azure_openai import async_rewrite_description, async_tailor_chunk, synthesize_role_context
from src.core.model import FullCV

logger = logging.getLogger(__name__)

@lru_cache(maxsize=1)
def load_system_prompt(filename: str = "system_prompt.txt") -> str:
    """Loads the prompt from the text file."""
    prompt_path = Path(__file__).parent.parent / "prompts/core" / filename
    with open(prompt_path, "r") as file:
        return file.read()

# --- PRIVATE HELPERS ---

def _extract_and_validate_cv(raw_cv: Dict[str, Any]) -> Tuple[Dict[str, Any], List[Dict], str]:
    """Validates input and separates static fields from dynamic fields."""
    validated_cv = FullCV(**raw_cv)
    cv_dict = validated_cv.model_dump()
    
    static_keys = ["name", "skills", "employee_id", "educations", "certifications", "trainings", "languages", "memberships"]
    static_data = {key: cv_dict[key] for key in static_keys if key in cv_dict}
    
    projects = cv_dict.get("projects", [])
    description = cv_dict.get("description", "")
    return static_data, projects, description

async def _run_task_with_identity(task_type: str, index: int, coro):
    """Wraps a coroutine so we know exactly which task finished in the as_completed stream."""
    try:
        result = await coro
        return task_type, index, result, None
    except Exception as e:
        return task_type, index, None, e

# --- MAIN STREAMING ORCHESTRATOR ---

async def process_cv_enhancement_stream(raw_cv: Dict[str, Any], project_specs: str, role_assignment: str, chunk_size: int = 2):
    """
    Yields Server-Sent Event dictionaries reflecting real-time progress.
    """
    yield {"status": "processing", "progress": 5, "message": "Validating CV data and extracting history..."}

    try:
        static_data, all_projects, original_description = _extract_and_validate_cv(raw_cv)
    except Exception as e:
        logger.error(f"Input CV failed validation: {e}")
        yield {"status": "failed", "progress": 100, "message": "Invalid CV JSON format."}
        return

    if not all_projects:
        yield {
            "status": "completed", 
            "progress": 100, 
            "message": "Nothing to tailor.", 
            "data": {**static_data, "description": original_description, "projects": []}
        }
        return

    yield {"status": "processing", "progress": 10, "message": "Preparing AI context and creating task chunks..."}

    system_prompt = load_system_prompt()
    chunks = [all_projects[i:i + chunk_size] for i in range(0, len(all_projects), chunk_size)]
    tasks = []

    # Prepare project chunk tasks (Notice: description removed to save tokens)
    for i, chunk in enumerate(chunks):
        coro = async_tailor_chunk(
            chunk_data={"projects": chunk},
            project_specs=project_specs,
            role_assignment=role_assignment,
            system_prompt=system_prompt
        )
        tasks.append(_run_task_with_identity("chunk", i, coro))

    # Prepare description task
    desc_coro = async_rewrite_description(
        original_description=original_description,
        project_specs=project_specs,
        role_assignment=role_assignment,
        system_prompt=system_prompt
    )
    tasks.append(_run_task_with_identity("description", 0, desc_coro))

    total_tasks = len(tasks)
    completed_tasks = 0
    yield {"status": "processing", "progress": 15, "message": f"Executing {total_tasks} AI generation tasks in parallel..."}

    # Tracking outputs
    chunk_results = [None] * len(chunks)
    final_description = original_description
    total_prompt_tokens = 0
    total_completion_tokens = 0
    total_tokens = 0

    # Execute and stream results as they finish
    for future in asyncio.as_completed(tasks):
        task_type, index, result, error = await future
        completed_tasks += 1
        
        # Calculate dynamic progress percentage (15% to 90%)
        progress = 15 + int((completed_tasks / total_tasks) * 75)

        if error:
            logger.error(f"AI Task {task_type} failed: {error}")
            msg = f"Task failed, relying on original data ({completed_tasks}/{total_tasks})"
            if task_type == "chunk":
                chunk_results[index] = chunks[index] # Fallback
        else:
            # Aggregate tokens
            total_prompt_tokens += result["usage"].prompt_tokens
            total_completion_tokens += result["usage"].completion_tokens
            total_tokens = total_prompt_tokens + total_completion_tokens
            
            # Save data
            if task_type == "chunk":
                ai_projects = result["data"].get("projects", [])
                
                # --- NEW: CHUNK-LEVEL INTEGRITY CHECK ---
                if len(ai_projects) != len(chunks[index]):
                    logger.warning(f"Chunk {index} length mismatch: Expected {len(chunks[index])}, got {len(ai_projects)}. Falling back to original chunk.")
                    chunk_results[index] = chunks[index] # Fallback to original
                    msg = f"Chunk {index + 1} size mismatch, using original data ({completed_tasks}/{total_tasks})"
                else:
                    chunk_results[index] = ai_projects
                    msg = f"Tailored project chunk {index + 1} successfully ({completed_tasks}/{total_tasks})"
                    
            else: # description task
                final_description = result["data"].get("description", original_description)
                msg = f"Rewrote professional summary successfully ({completed_tasks}/{total_tasks})"

        yield {"status": "processing", "progress": progress, "message": msg}
    # REDUCE phase
    yield {"status": "processing", "progress": 95, "message": "Reassembling optimized CV..."}

    tailored_projects = []
    for res in chunk_results:
        tailored_projects.extend(res)

    logger.info(f"""
    === TOKEN USAGE REPORT ===
    Prompt Tokens:     {total_prompt_tokens}
    Completion Tokens: {total_completion_tokens}
    Total Tokens:      {total_tokens}
    ==========================
    """)

    # Integrity Check
    if len(tailored_projects) != len(all_projects):
        yield {"status": "failed", "progress": 100, 
               "message": f"Fatal Error: AI hallucination resulted in missing projects. Expected {len(all_projects)}, got {len(tailored_projects)}"}
        return

    final_cv = {
        **static_data,
        "description": final_description,
        "projects": tailored_projects
    }

    # Final completion yield containing the data payload
    yield {"status": "completed", "tokens": total_tokens, "progress": 100, "message": "CV Enhancement Complete!", "data": final_cv}

# async def get_role_prompt(role_title: str, sector: str, user_intent: str) -> str:
#     role = await synthesize_role_context(role_title, sector, user_intent)
#     return role
#     """Ensures no data loss occurred during the AI transformation."""
#     if expected_count != actual_count:
#         logger.error(f"Integrity Mismatch: Input {expected_count} projects, Output {actual_count}.")
#         raise RuntimeError("AI processing resulted in missing or extra projects.")