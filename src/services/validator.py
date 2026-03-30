import logging
from typing import Dict, Any, Tuple, List

logger = logging.getLogger(__name__)

class CVValidationError(Exception):
    """Custom exception raised when the tailored CV fails strict integrity checks."""
    pass

def validate_cv_integrity(original_cv: Dict[str, Any], tailored_cv: Dict[str, Any]) -> Tuple[bool, List[str]]:
    """
    Performs a strict deterministic comparison between the original JSON and the 
    AI-tailored JSON to ensure zero hallucination of factual data.
    
    Returns:
        (is_valid: bool, errors: List[str])
    """
    errors = []

    # 1. Project Count Check (Did the chunking drop or invent a project?)
    orig_projects = original_cv.get("projects", [])
    tail_projects = tailored_cv.get("projects", [])

    if len(orig_projects) != len(tail_projects):
        errors.append(
            f"Project count mismatch: Original had {len(orig_projects)}, "
            f"Tailored returned {len(tail_projects)}."
        )

    # 2. Project Identity Check (Order and Core Fact Verification)
    # The Map-Reduce orchestrator maintains array order, so index-to-index comparison is safe.
    if len(orig_projects) == len(tail_projects):
        for i, (orig, tail) in enumerate(zip(orig_projects, tail_projects)):
            
            # Check ID preservation (if your system uses DB IDs)
            if orig.get("id") is not None and orig.get("id") != tail.get("id"):
                errors.append(f"Index {i}: Project ID altered from {orig.get('id')} to {tail.get('id')}.")
            
            # Check Company preservation
            if orig.get("company") != tail.get("company"):
                errors.append(f"Index {i}: Company name altered from '{orig.get('company')}' to '{tail.get('company')}'.")
            
            # Check Date preservation (Critical for EPC experience tracking)
            if orig.get("date_start") != tail.get("date_start"):
                errors.append(f"Index {i}: Start date altered from '{orig.get('date_start')}' to '{tail.get('date_start')}'.")

    # 3. Static Data Retention Check
    # Ensures the orchestrator successfully merged the non-tailored arrays back into the final JSON.
    static_arrays = ["educations", "certifications", "trainings", "languages", "memberships"]
    for arr_key in static_arrays:
        orig_len = len(original_cv.get(arr_key, []))
        tail_len = len(tailored_cv.get(arr_key, []))
        if orig_len != tail_len:
            errors.append(f"Static array '{arr_key}' lost data: Original size {orig_len}, Tailored size {tail_len}.")

    # Log all errors if validation fails
    is_valid = len(errors) == 0
    if not is_valid:
        for error in errors:
            logger.error(f"Integrity Validation Failed: {error}")

    return is_valid, errors

def enforce_strict_validation(original_cv: Dict[str, Any], tailored_cv: Dict[str, Any]) -> None:
    """
    Wrapper function to be called directly by the orchestrator.
    Raises a CVValidationError if integrity is compromised, forcing a fallback.
    """
    is_valid, errors = validate_cv_integrity(original_cv, tailored_cv)
    
    if not is_valid:
        error_msg = " | ".join(errors)
        raise CVValidationError(f"CV Tailoring failed strict compliance checks: {error_msg}")