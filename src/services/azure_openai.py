import os
import json
import logging
from typing import Any, Dict
from openai import AsyncAzureOpenAI
from azure.identity import ManagedIdentityCredential, get_bearer_token_provider
from src.api.schemas import DomainSynthesisResponse
from src.core.model import CVChunkResponse, Description
from dotenv import load_dotenv

from src.utils.prompt_loader import PromptLoader
load_dotenv()

logger = logging.getLogger(__name__)

# ==========================================
# 1. Secure Async Client Initialization
# ==========================================
# Instantiate the client once at the module level to reuse the connection pool.

endpoint = os.getenv("AZURE_OPENAI_ENDPOINT")
deployment = os.getenv("OPENAI_CHAT_DEPLOYMENT")
deployment_mini = os.getenv("OPENAI_CHAT_DEPLOYMENT_MINI")
api_version = os.getenv("AZURE_OPENAI_VERSION")
api_key = os.getenv("AZURE_OPENAI_KEY")

if not endpoint:
    raise ValueError("AZURE_OPENAI_ENDPOINT environment variable is missing.")

if api_key:
    # ---------------------------------------------------------
    # LOCAL DEVELOPMENT MODE: Uses API Key
    # ---------------------------------------------------------
    print("[INFO] AZURE_OPENAI_API_KEY found. Authenticating via API Key (Local Mode).")
    client = AsyncAzureOpenAI(
        azure_endpoint=endpoint,
        api_key=api_key,
        api_version=api_version
    )
else:
    # PRODUCTION MODE
    print("[INFO] No API Key found. Authenticating via Managed Identity (Production Mode).")
    
    # Directly target Managed Identity, skipping the DefaultAzureCredential chain
    credential = ManagedIdentityCredential()
    
    token_provider = get_bearer_token_provider(
        credential, 
        "https://cognitiveservices.azure.com/.default"
    )
    client = AsyncAzureOpenAI(
        azure_endpoint=endpoint,
        azure_ad_token_provider=token_provider,
        api_version=api_version
    )
# ==========================================
# 2. The Core Async Integration Function
# ==========================================

async def async_tailor_chunk(chunk_data: dict, project_specs: str, role_assignment: str, system_prompt: str) -> dict:
    """
    Asynchronously sends a chunk of CV data to Azure OpenAI for tailoring.
    Strictly enforces the CVChunkResponse Pydantic schema to prevent hallucinated keys.
    """
    # {project_specs}
    # Construct the user message, isolating the context from the payload
    user_message = f"""
    TARGET ROLE ASSIGNMENT:
    {role_assignment}
    
    PROJECT REQUIREMENTS:
    {project_specs}

    CV CHUNK TO TAILOR (Strictly follow JSON schema):
    {json.dumps(chunk_data, indent=2)}
    """

    try:
        # Use the async beta parse method to enforce the Pydantic schema
        response = await client.beta.chat.completions.parse(
            model=deployment_mini,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message}
            ],
            response_format=CVChunkResponse, # Binds the output to your Pydantic model
            temperature=0.2,                 # Low temperature for analytical, grounded rewriting
            max_tokens=1200                  # Ensure enough runway for large text blocks
        )

        message = response.choices[0].message

        # Azure OpenAI Content Filtering check
        if getattr(message, "refusal", None):
            logger.error(f"Azure OpenAI refused the request (Content Filter): {message.refusal}")
            raise RuntimeError(f"Model refusal: {message.refusal}")

        if not message.parsed:
             raise ValueError("Model failed to return parsed JSON.")

        # message.parsed is already a validated CVChunkResponse Pydantic object
        # Convert it back to a dictionary for the orchestrator to merge
        # return message.parsed.model_dump()
        return {
            "data": message.parsed.model_dump(),
            "usage": response.usage
        }

    except Exception as e:
        logger.error(f"Async Azure OpenAI API call failed for chunk: {str(e)}")
        # The orchestrator.py is designed to catch this and apply the fallback logic 
        # (returning the unmodified chunk) so the whole CV doesn't fail.
        raise e

async def async_rewrite_description(original_description: str, project_specs: str, role_assignment: str, system_prompt: str) -> dict:
    """
    Asynchronously sends the CV professional summary (description) to Azure OpenAI for tailoring.
    Strictly enforces the CVDescriptionResponse Pydantic schema.
    """
    
    # Construct the user message with explicit rewriting instructions
    user_message = f"""
    TARGET ROLE ASSIGNMENT:
    {role_assignment}
    
    PROJECT REQUIREMENTS:
    {project_specs}

    ORIGINAL DESCRIPTION TO TAILOR:
    {original_description}

    INSTRUCTIONS:
    Rewrite the original description to highlight the candidate's skills and experiences that are most relevant to the Target Role and Project Requirements. 
    - Maintain a professional, executive tone.
    - Keep it concise and impactful.
    - DO NOT invent new skills or experiences that are not supported by the original description.
    - Max 40 words. Focus on tailoring the content, not expanding it.
    """

    try:
        # Use the async beta parse method to enforce the Pydantic schema
        response = await client.beta.chat.completions.parse(
            model=deployment_mini,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message}
            ],
            response_format=Description, # Binds the output to your Pydantic model
            temperature=0.3,                       # Slightly higher than 0.2 to allow smoother sentence restructuring
            max_tokens=200                         # Descriptions are usually short, 400 is plenty of runway
        )

        message = response.choices[0].message

        # Azure OpenAI Content Filtering check
        if getattr(message, "refusal", None):
            logger.error(f"Azure OpenAI refused the description request (Content Filter): {message.refusal}")
            raise RuntimeError(f"Model refusal: {message.refusal}")

        if not message.parsed:
             raise ValueError("Model failed to return parsed JSON for description.")

        # message.parsed is the validated CVDescriptionResponse Pydantic object
        return {
            "data": message.parsed.model_dump(),
            "usage": response.usage
        }


    except Exception as e:
        logger.error(f"Async Azure OpenAI API call failed for description rewrite: {str(e)}")
        # The orchestrator will catch this and fallback to the original string
        raise e

async def synthesize_role_context(
    role_title: str, 
    sector: str, 
    user_intent: str
) -> str:
    """
    Uses AI to synthesize the role, sector, and user intent into a single, 
    cohesive directive for the main CV enhancement prompt.
    """
    system_prompt = (
        "You are an expert technical recruiter and prompt engineer. "
        "Your job is to combine a target job role, an industry sector context, "
        "and specific user instructions into a single, highly cohesive 'Target Role Context' paragraph. "
        "This paragraph will be used to guide another AI in rewriting a candidate's CV."
    )
    loader = PromptLoader()
    role_template_content = loader.load("roles", "synthesize_role_template")
    user_prompt = f"""
    1. TARGET ROLE: {role_title}
    2. ROLE BASE TEMPLATE: {role_template_content}
    3. TARGET SECTOR: {sector}
    4. SPECIFIC USER INTENT: {user_intent}

    INSTRUCTIONS:
    Synthesize the above information into a single set of clear, actionable guidelines. 
    Ensure the user's specific intent is prioritized, but grounded in the reality of the role and sector.
    Do not output pleasantries. Output only the synthesized context.
    """

    try:
        # Note: Replace this with your actual Azure OpenAI client call format
        response = await client.beta.chat.completions.parse(
            model=deployment_mini, 
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            temperature=0.3, 
            max_tokens=500
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        logger.error(f"Failed to synthesize role context: {str(e)}")
        return f"Role: {role_title}\nSector: {sector}\nIntent: {user_intent}"
    
async def async_synthesize_domain_prompt(user_sector_input: str) -> Dict[str, Any]:
    """
    Generates a domain prompt AND extracts the standardized sector key.
    Returns: (standardized_sector_key, prompt_content)
    """
    loader = PromptLoader()
    base_template = loader.load_domain_prompt("synthesize_domain")
    
    system_message = (
        "You are an expert Prompt Engineer and Domain Specialist. "
        "Your task is to identify the exact industry sector from the user's input, "
        "create a short snake_case key for it, and populate the domain framework template."
    )
    
    user_message = (
        f"User Input Context: '{user_sector_input}'\n\n"
        f"1. Identify the core industry sector from the input.\n"
        f"2. Generate the exact domain framework using this template:\n\n{base_template}"
    )

    try:
        response = await client.beta.chat.completions.parse(
            model=deployment_mini,
            messages=[
                {"role": "system", "content": system_message},
                {"role": "user", "content": user_message}
            ],
            response_format=DomainSynthesisResponse,
            temperature=0.2
        )
        
        result = response.choices[0].message.parsed
        
        return {
            "standardized_sector_key": result.standardized_sector_key,
            "prompt_content": result.prompt_content,
            "usage": response.usage
        }
        
    except Exception as e:
        logger.error(f"Failed to synthesize domain prompt for input '{user_sector_input}': {str(e)}")
        raise e