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

# --- MAIN ORCHESTRATOR ---

async def process_cv_enhancement(raw_cv: Dict[str, Any], project_specs: str, role_assignment: str, chunk_size: int = 4) -> Dict[str, Any]:
    """
    The main Map-Reduce orchestrator for tailoring long CVs.
    """
    # 1. Parse & Segregate Data
    static_data, all_projects, original_description = _extract_and_validate_cv(raw_cv)
    
    if not all_projects:
        return {**static_data, "description": original_description, "projects": []}

    system_prompt = load_system_prompt()

    # 2. MAP: Prepare Tasks
    project_chunks, project_tasks = _prepare_project_tasks(
        all_projects, project_specs, role_assignment, system_prompt, chunk_size
    )
    desc_task = async_rewrite_description(
        original_description, project_specs, role_assignment, system_prompt
    )

    # 3. EXECUTE: Run parallel AI generation
    logger.info(f"Sending {len(project_tasks)} chunk(s) and 1 description task to Azure OpenAI...")
    results = await asyncio.gather(*project_tasks, desc_task, return_exceptions=True)

    # 4. REDUCE: Process results and calculate tokens
    tailored_projects, chunk_tokens = _reduce_projects(results[:-1], project_chunks)
    final_description, desc_tokens = _reduce_description(results[-1], original_description)

    # 5. Log Performance & Validate
    _log_token_usage(chunk_tokens, desc_tokens)
    _validate_integrity(len(all_projects), len(tailored_projects))

    # 6. Reassemble Final CV
    return {
        **static_data,
        "description": final_description,
        "projects": tailored_projects
    }

# async def get_role_prompt(role_title: str, sector: str, user_intent: str) -> str:
#     role = await synthesize_role_context(role_title, sector, user_intent)
#     return role

# --- PRIVATE HELPER FUNCTIONS ---

def _extract_and_validate_cv(raw_cv: Dict[str, Any]) -> Tuple[Dict[str, Any], List[Dict], str]:
    """Validates input and separates static fields from dynamic fields."""
    try:
        validated_cv = FullCV(**raw_cv)
    except Exception as e:
        logger.error(f"Input CV failed validation: {e}")
        raise ValueError("Invalid CV JSON format")

    cv_dict = validated_cv.model_dump()
    
    static_keys = ["name", "skills", "employee_id", "educations", "certifications", "trainings", "languages", "memberships"]
    static_data = {key: cv_dict[key] for key in static_keys if key in cv_dict}
    
    projects = cv_dict.get("projects", [])
    description = cv_dict.get("description", "")
    
    return static_data, projects, description

def _prepare_project_tasks(projects: List[Dict], specs: str, role: str, prompt: str, chunk_size: int) -> Tuple[List[List[Dict]], List[asyncio.Task]]:
    """Chunks projects and builds the async tasks. Removes description to save tokens."""
    chunks = [projects[i:i + chunk_size] for i in range(0, len(projects), chunk_size)]
    
    tasks = []
    for chunk in chunks:
        # Note: Description removed from payload to minimize prompt tokens
        payload = {"projects": chunk} 
        tasks.append(
            async_tailor_chunk(chunk_data=payload, project_specs=specs, role_assignment=role, system_prompt=prompt)
        )
        
    return chunks, tasks

def _reduce_projects(chunk_results: List[Any], original_chunks: List[List[Dict]]) -> Tuple[List[Dict], Dict[str, int]]:
    """Reassembles project chunks and aggregates tokens, handling fallbacks."""
    tailored_projects = []
    tokens = {"prompt": 0, "completion": 0}

    for i, result in enumerate(chunk_results):
        if isinstance(result, Exception):
            logger.error(f"Chunk {i} failed: {result}. Using original chunk.")
            tailored_projects.extend(original_chunks[i])
        else:
            tokens["prompt"] += result["usage"].prompt_tokens
            tokens["completion"] += result["usage"].completion_tokens
            tailored_projects.extend(result["data"].get("projects", []))
            
    return tailored_projects, tokens

def _reduce_description(desc_result: Any, original_desc: str) -> Tuple[str, Dict[str, int]]:
    """Extracts the final description and its tokens, handling fallbacks."""
    tokens = {"prompt": 0, "completion": 0}
    
    if isinstance(desc_result, Exception):
        logger.error(f"Description rewrite failed: {desc_result}. Using original.")
        return original_desc, tokens
        
    tokens["prompt"] += desc_result["usage"].prompt_tokens
    tokens["completion"] += desc_result["usage"].completion_tokens
    
    return desc_result["data"].get("description", original_desc), tokens

def _log_token_usage(chunk_tokens: Dict[str, int], desc_tokens: Dict[str, int]):
    """Aggregates and formats the final token report."""
    total_prompt = chunk_tokens["prompt"] + desc_tokens["prompt"]
    total_completion = chunk_tokens["completion"] + desc_tokens["completion"]
    
    logger.info(f"""
    === TOKEN USAGE REPORT ===
    Prompt Tokens:     {total_prompt}
    Completion Tokens: {total_completion}
    Total Tokens:      {total_prompt + total_completion}
    ==========================
    """)

def _validate_integrity(expected_count: int, actual_count: int):
    """Ensures no data loss occurred during the AI transformation."""
    if expected_count != actual_count:
        logger.error(f"Integrity Mismatch: Input {expected_count} projects, Output {actual_count}.")
        raise RuntimeError("AI processing resulted in missing or extra projects.")