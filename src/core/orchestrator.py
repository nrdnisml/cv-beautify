import asyncio
import logging
from pathlib import Path
from typing import Dict, Any, List, Tuple, Optional
from functools import lru_cache

from src.utils.prompt_loader import PromptLoader
from src.services.azure_openai import async_rewrite_description, async_tailor_chunk, async_synthesize_domain_prompt
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
    
    static_keys = ["name", "employee_id"]
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

async def _resolve_domain_specs(project_sector: str) -> Tuple[str, Optional[Any]]:
    """
    Handles loading or synthesizing the domain prompt.
    Keeps the main orchestrator clean.
    """
    loader = PromptLoader()
    response = await async_synthesize_domain_prompt(project_sector)
    # standard_key = response['standardized_sector_key']
    standard_key = loader.normalize_to_key(project_sector)
    generated_content = response['prompt_content']
    usage = response['usage']
    print(usage.completion_tokens)
    existing_prompt = loader.load_domain_prompt(standard_key)
    if existing_prompt:
        return existing_prompt, usage
    
    # Simpan sebagai file baru dan kembalikan kontennya
    loader.save_sector_prompt(standard_key, response['prompt_content'])
    return generated_content, usage


# --- MAIN STREAMING ORCHESTRATOR ---

async def process_cv_enhancement_stream(
    raw_cv: Dict[str, Any], 
    project_sector: str, 
    role_assignment: str, 
    user_intent: str, 
    chunk_size: int = 2
):
    """
    Yields Server-Sent Event dictionaries reflecting real-time progress.
    """
    yield {"status": "processing", "progress": 2, "message": "Initializing enhancement engine..."}

    # ==========================================
    # 1. DOMAIN RESOLUTION & SYNTHESIS
    # ==========================================
    try:
        # Pengecekan cepat untuk UX: Jika tidak ada file lokal, beri tahu user bahwa AI sedang menganalisis industri
        loader = PromptLoader()
        if not loader.load_domain_prompt(loader.normalize_to_key(project_sector)):
            yield {"status": "processing", "progress": 5, "message": f"Synthesizing domain context: '{project_sector}'..."}
        
        domain_prompt, domain_usage = await _resolve_domain_specs(project_sector)
    except Exception as e:
        logger.error(f"Domain synthesis failed: {e}")
        yield {"status": "failed", "progress": 100, "message": f"Failed to synthesize industry domain: {str(e)}"}
        return

    # Siapkan kombinasi instruksi
    combined_role_context = (
        f"Target Role: {role_assignment}\n"
        f"Specific User Intent/Instructions: {user_intent or 'No specific additional instructions provided.'}"
    )

    # ==========================================
    # 2. CV VALIDATION
    # ==========================================
    yield {"status": "processing", "progress": 10, "message": "Validating CV data and extracting history..."}

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

    # ==========================================
    # 3. TASK PREPARATION & CHUNKING
    # ==========================================
    yield {"status": "processing", "progress": 15, "message": "Preparing AI context and creating task chunks..."}

    system_prompt = load_system_prompt()
    chunks = [all_projects[i:i + chunk_size] for i in range(0, len(all_projects), chunk_size)]
    tasks = []
    
    # Prepare project chunk tasks
    for i, chunk in enumerate(chunks):
        coro = async_tailor_chunk(
            chunk_data={"projects": chunk},
            project_specs=domain_prompt,
            role_assignment=combined_role_context,
            system_prompt=system_prompt
        )
        tasks.append(_run_task_with_identity("chunk", i, coro))

    # Prepare description task
    desc_coro = async_rewrite_description(
        original_description=original_description,
        project_specs=domain_prompt,
        role_assignment=combined_role_context,
        system_prompt=system_prompt
    )
    tasks.append(_run_task_with_identity("description", 0, desc_coro))

    total_tasks = len(tasks)
    completed_tasks = 0
    yield {"status": "processing", "progress": 20, "message": f"Executing {total_tasks} AI generation tasks in parallel..."}

    # Tracking outputs
    chunk_results = [None] * len(chunks)
    final_description = original_description
    total_prompt_tokens = domain_usage.prompt_tokens
    total_completion_tokens = domain_usage.completion_tokens
    total_tokens = domain_usage.total_tokens

    # ==========================================
    # 4. PARALLEL EXECUTION & STREAMING
    # ==========================================
    for future in asyncio.as_completed(tasks):
        task_type, index, result, error = await future
        completed_tasks += 1
        
        # Calculate dynamic progress percentage (20% to 90%)
        progress = 20 + int((completed_tasks / total_tasks) * 70)

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
                
                # CHUNK-LEVEL INTEGRITY CHECK
                if len(ai_projects) != len(chunks[index]):
                    logger.warning(f"Chunk {index} length mismatch: Expected {len(chunks[index])}, got {len(ai_projects)}. Falling back to original.")
                    chunk_results[index] = chunks[index] # Fallback to original
                    msg = f"Chunk {index + 1} size mismatch, using original data ({completed_tasks}/{total_tasks})"
                else:
                    chunk_results[index] = ai_projects
                    msg = f"Tailored project chunk {index + 1} successfully ({completed_tasks}/{total_tasks})"
                    
            else: # description task
                final_description = result["data"].get("description", original_description)
                msg = f"Rewrote professional summary successfully ({completed_tasks}/{total_tasks})"

        yield {"status": "processing", "progress": progress, "message": msg}

    # ==========================================
    # 5. REDUCE & ASSEMBLE
    # ==========================================
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

    # Final Integrity Check
    if len(tailored_projects) != len(all_projects):
        yield {
            "status": "failed", 
            "progress": 100, 
            "message": f"Fatal Error: AI hallucination resulted in missing projects. Expected {len(all_projects)}, got {len(tailored_projects)}"
        }
        return

    final_cv = {
        **static_data,
        "description": final_description,
        "projects": tailored_projects
    }

    # Final completion yield containing the data payload
    yield {"status": "completed", "tokens": total_tokens, "progress": 100, "message": "CV Enhancement Complete!", "data": final_cv}