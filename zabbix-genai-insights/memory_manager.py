import os
import logging
from mem0 import Memory

logger = logging.getLogger(__name__)

# Configuration for Mem0
# We store data in /app/data/mem0 to persist in Docker
DATA_DIR = os.environ.get("MEM0_DIR", "/app/data/mem0")

# Mem0 needs an LLM to extract facts. 
# We prefer OpenAI if available, or Gemini as fallback if supported by mem0 version.
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")
GOOGLE_API_KEY = os.environ.get("GOOGLE_API_KEY")

_memory_instance = None

def get_memory_instance():
    global _memory_instance
    if _memory_instance is None:
        try:
            config = {
                "vector_store": {
                    "provider": "chroma",
                    "config": {
                        "path": DATA_DIR,
                    }
                }
            }
            
            # If OpenAI is available, use it (Mem0 default)
            if OPENAI_API_KEY:
                os.environ["OPENAI_API_KEY"] = OPENAI_API_KEY
                _memory_instance = Memory.from_config(config)
            elif GOOGLE_API_KEY:
                # Fallback or specific config for Gemini if needed
                # For now, we assume simple config or that Mem0 is used with a provider
                # If mem0 version is recent, it supports multiple providers.
                _memory_instance = Memory.from_config(config)
            else:
                logger.warning("No API keys found for Mem0 extraction. Memory might fail.")
                _memory_instance = Memory.from_config(config)
                
        except Exception as e:
            logger.error(f"Failed to initialize Mem0: {e}")
            return None
    return _memory_instance

def get_perennial_context(host_id: str) -> str:
    """Retrieves extracted facts for a specific host."""
    mem = get_memory_instance()
    if not mem or not host_id:
        return ""
    
    try:
        # We use host_id as the user_id in mem0 to isolate memories per host
        results = mem.search(query=f"Technical status of {host_id}", user_id=host_id)
        if not results:
            return ""
        
        # Format the results into a clean string for the prompt
        facts = [r['memory'] for r in results]
        return "\n".join([f"- {fact}" for fact in facts])
    except Exception as e:
        logger.error(f"Error searching memories for {host_id}: {e}")
        return ""

def add_perennial_insight(host_id: str, insight: str):
    """Extracts and stores facts from an agent's technical insight."""
    mem = get_memory_instance()
    if not mem or not host_id or not insight:
        return
    
    try:
        logger.info(f"Adding new perennial insight to memory for host: {host_id}")
        # Mem0 will automatically extract key facts from the text
        mem.add(insight, user_id=host_id)
    except Exception as e:
        logger.error(f"Error adding memory for {host_id}: {e}")
