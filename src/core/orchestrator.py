# src/core/orchestrator.py
import asyncio
import logging
from pathlib import Path
from typing import Dict, Any, List

# Assuming you have an async wrapper for the Azure OpenAI call in your services layer
from src.services.azure_openai import async_tailor_chunk
from src.core.model import FullCV

logger = logging.getLogger(__name__)

def load_system_prompt(filename: str = "system_prompt.txt") -> str:
    """Loads the prompt from the text file."""
    prompt_path = Path(__file__).parent.parent / "prompts/core" / filename
    with open(prompt_path, "r") as file:
        return file.read()

async def process_cv_enhancement(raw_cv: Dict[str, Any], project_specs: str, role_assignment: str, chunk_size: int = 3) -> Dict[str, Any]:
    """
    The main Map-Reduce orchestrator for tailoring long CVs.
    """
    # 1. Input Validation
    try:
        validated_cv = FullCV(**raw_cv)
    except Exception as e:
        logger.error(f"Input CV failed validation: {e}")
        raise ValueError("Invalid CV JSON format")

    cv_dict = validated_cv.model_dump()
    
    # 2. Segregate Static Data vs. Chunkable Data (Projects)
    static_keys = ["name", "skills", "employee_id", "educations", "certifications", "trainings", "languages", "memberships"]
    static_data = {key: cv_dict[key] for key in static_keys if key in cv_dict}
    
    all_projects = cv_dict.get("projects", [])
    original_description = cv_dict.get("description", "")
    
    if not all_projects:
        return cv_dict # Nothing to tailor if no projects exist

    # 3. Create Chunks
    project_chunks = [all_projects[i:i + chunk_size] for i in range(0, len(all_projects), chunk_size)]
    logger.info(f"Split {len(all_projects)} projects into {len(project_chunks)} chunks.")

    system_prompt = load_system_prompt()

    # 4. MAP: Prepare asynchronous tasks
    tasks = []
    for chunk in project_chunks:
        # We pass the original description to every chunk so the AI has context of the person's overall summary
        chunk_payload = {
            "description": original_description,
            "projects": chunk
        }
        
        # async_tailor_chunk is your function that calls client.beta.chat.completions.parse()
        task = async_tailor_chunk(
            chunk_data=chunk_payload,
            project_specs=project_specs,
            role_assignment=role_assignment,
            system_prompt=system_prompt
        )
        tasks.append(task)

    # 5. Execute all chunks in parallel
    logger.info("Sending chunks to Azure OpenAI in parallel...")
    results = await asyncio.gather(*tasks, return_exceptions=True)

    # 6. REDUCE: Reassemble the results
    tailored_projects = []
    final_description = original_description # Fallback

    for i, result in enumerate(results):
        if isinstance(result, Exception):
            logger.error(f"Chunk {i} failed: {result}. Using un-tailored original chunk.")
            tailored_projects.extend(project_chunks[i]) # Fallback to original data if AI fails
        else:
            # result is expected to be a dict matching CVChunkResponse
            tailored_projects.extend(result.get("projects", []))
            # We take the tailored description from the first successful chunk
            if i == 0 and "description" in result:
                final_description = result["description"]

    # 7. Integrity Validation (Anti-Hallucination/Data Loss Check)
    if len(tailored_projects) != len(all_projects):
        logger.error(f"Integrity Mismatch: Input had {len(all_projects)} projects, Output has {len(tailored_projects)}.")
        # Depending on business rules, you might want to raise an error here or return the un-tailored CV.
        raise RuntimeError("AI processing resulted in missing or extra projects.")

    # 8. Construct Final CV
    final_cv = {
        **static_data,
        "description": final_description,
        "projects": tailored_projects
    }

    return final_cv