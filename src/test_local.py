# test_local.py
import json
import asyncio
import logging
from pathlib import Path
from src.utils import PromptLoader

# Import the core orchestrator bypassing the API layer
from src.core.orchestrator import process_cv_enhancement

# Configure logging to see the debug steps in your terminal
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("local-tester")

async def run_local_test():
    # 1. Define file paths
    input_file = Path("input_cv.json")
    output_file = Path("output_cv.json")

    # Ensure the input file exists before starting
    if not input_file.exists():
        logger.error(f"Could not find '{input_file}' in the current directory.")
        return

    # 2. Load the raw CV data
    logger.info(f"Loading raw CV data from {input_file}...")
    with open(input_file, "r") as f:
        raw_cv = json.load(f)

    # 3. Define the target parameters for the test
    # Setting the context to focus on a completion management project, 
    # as this is highly impactful for engineering company workflows.
    loader = PromptLoader()
    project_specs = loader.load("domains", "green_prompt")
    role_assignment = loader.load("roles", "role_commissioning")

    logger.info(f"Initiating Map-Reduce tailoring for role: {role_assignment}")

    try:
        # 4. Execute the AI orchestration
        # This will automatically chunk the projects, call Azure OpenAI, and reassemble
        enhanced_cv = await process_cv_enhancement(
            raw_cv=raw_cv,
            project_specs=project_specs,
            role_assignment=role_assignment,
            chunk_size=2  # Using a smaller chunk size to explicitly test the batching logic
        )

        # 5. Save the final output for manual inspection
        with open(output_file, "w") as f:
            json.dump(enhanced_cv, f, indent=2)
            
        logger.info(f"Success! The tailored CV has been written to {output_file}")

    except Exception as e:
        logger.error(f"Local test execution failed: {e}")

if __name__ == "__main__":
    # Execute the async function
    asyncio.run(run_local_test())