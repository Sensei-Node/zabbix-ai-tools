import os
import logging
from mem0 import Memory

logger = logging.getLogger(__name__)

# Configuration for Mem0
# We store data in /app/data/mem0 to persist in Docker
DATA_DIR = os.environ.get("MEM0_DIR", "/app/data/mem0")

# Mem0 needs an LLM to extract facts. 
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")
GOOGLE_API_KEY = os.environ.get("GOOGLE_API_KEY")
DEEPSEEK_API_KEY = os.environ.get("DEEPSEEK_API_KEY")

_memory_instance = None

def get_memory_instance():
    global _memory_instance
    if _memory_instance is None:
        try:
            # Base config with local vector store
            config = {
                "vector_store": {
                    "provider": "chroma",
                    "config": {
                        "collection_name": "zabbix_ai_memories",
                        "path": os.path.join(DATA_DIR, "chroma"),
                    }
                },
                "version": "v1.1" # Explicitly use local-first version if applicable
            }
            
            # 1. Configure LLM and Embedder based on available keys
            # Mem0 requires an LLM for fact extraction and an embedder for vector search.
            if OPENAI_API_KEY:
                logger.info("Configuring Mem0 with OpenAI provider.")
                config["llm"] = {
                    "provider": "openai",
                    "config": {"model": os.environ.get("OPENAI_MODEL", "gpt-4o-mini"), "api_key": OPENAI_API_KEY}
                }
                config["embedder"] = {
                    "provider": "openai",
                    "config": {"model": "text-embedding-3-small", "api_key": OPENAI_API_KEY}
                }
            elif DEEPSEEK_API_KEY:
                logger.info("Configuring Mem0 with DeepSeek provider.")
                # DeepSeek is OpenAI-compatible
                config["llm"] = {
                    "provider": "openai",
                    "config": {
                        "model": os.environ.get("DEEPSEEK_MODEL", "deepseek-chat"), 
                        "api_key": DEEPSEEK_API_KEY,
                        "base_url": "https://api.deepseek.com"
                    }
                }
                # For embedding, DeepSeek doesn't provide one via API usually, 
                # but if we are here we might need to fallback or use a local one.
                # Mem0 might need a real embedder. We'll try to use OpenAI embedder if key exists, 
                # or hope mem0 handles a default.
                if OPENAI_API_KEY:
                     config["embedder"] = {"provider": "openai", "config": {"api_key": OPENAI_API_KEY}}
                else:
                     logger.warning("DeepSeek selected but no OpenAI/Google key for embeddings. Fact extraction might fail.")

            elif GOOGLE_API_KEY:
                logger.info("Configuring Mem0 with Google Gemini provider.")
                config["llm"] = {
                    "provider": "google",
                    "config": {"model": os.environ.get("GENAI_MODEL", "gemini-1.5-flash"), "api_key": GOOGLE_API_KEY}
                }
                config["embedder"] = {
                    "provider": "google",
                    "config": {"model": "models/embedding-001", "api_key": GOOGLE_API_KEY}
                }
            
            # 2. Set Metadata store path to ensure it stays in DATA_DIR
            # In newer Mem0 versions, this preserves the SQLite db in the specified location.
            # We use an environment variable trick that mem0 respects or explicit config if supported.
            os.environ["MEM0_HOME"] = DATA_DIR 
            
            _memory_instance = Memory.from_config(config)
            logger.info(f"Mem0 initialized successfully. Storage path: {DATA_DIR}")
                
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
