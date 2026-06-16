import os
import sys
import logging
from dotenv import load_dotenv

logger = logging.getLogger(__name__)

SERVER_VERSION = "2.0.1"

try:
    load_dotenv()
    logger.info("Environment variables loaded")
except Exception as e:
    logger.error(f"Error loading .env file: {str(e)}")
    sys.exit(1)

class AppConfig:
    def __init__(self):
        # Database Config
        self.db_host = os.getenv("ADBPG_HOST")
        self.db_port = os.getenv("ADBPG_PORT")
        self.db_user = os.getenv("ADBPG_USER")
        self.db_password = os.getenv("ADBPG_PASSWORD")
        self.db_name = os.getenv("ADBPG_DATABASE")

        # GraphRAG Config
        self.graphrag_llm_model = os.getenv("GRAPHRAG_LLM_MODEL")
        self.graphrag_api_key = os.getenv("GRAPHRAG_API_KEY")
        self.graphrag_base_url = os.getenv("GRAPHRAG_BASE_URL")
        self.graphrag_embedding_model = os.getenv("GRAPHRAG_EMBEDDING_MODEL")
        self.graphrag_embedding_api_key = os.getenv("GRAPHRAG_EMBEDDING_API_KEY")
        self.graphrag_embedding_base_url = os.getenv("GRAPHRAG_EMBEDDING_BASE_URL")
        self.graphrag_language = os.getenv("GRAPHRAG_LANGUAGE", "English")
        self.graphrag_entity_types = os.getenv("GRAPHRAG_ENTITY_TYPES", '["Organization", "Person", "Location", "Event", "Technology", "Equipment", "Product", "Document", "Category"]')
        self.graphrag_relationship_types = os.getenv("GRAPHRAG_RELATIONSHIP_TYPES", '["Causes", "Used For", "Helps In", "Includes", "Originated From", "Seasonal", "Coreference Of", "Synonym Of", "Conjunction", "Affects"]')

        # LLM Memory Config
        self.memory_llm_model = os.getenv("LLMEMORY_LLM_MODEL")
        self.memory_api_key = os.getenv("LLMEMORY_API_KEY")
        self.memory_base_url = os.getenv("LLMEMORY_BASE_URL")
        self.memory_embedding_model = os.getenv("LLMEMORY_EMBEDDING_MODEL")
        self.memory_embedding_dims = os.getenv("LLMEMORY_EMBEDDING_DIMS", 1024)
        self.memory_enable_graph = os.getenv("LLMEMORY_ENABLE_GRAPH", "False").lower() in ('true', '1', 't')

        self.db_env_ready = self._check_db_env()
        self.graphrag_env_ready = self._check_graphrag_env()
        self.memory_env_ready = self._check_memory_env()

    def _check_db_env(self):
        required = ["db_host", "db_port", "db_user", "db_password", "db_name"]
        missing = [var.replace('db_', 'ADBPG_').upper() for var in required if not getattr(self, var)]
        if missing:
            logger.error(f"Missing required ADBPG environment variables: {', '.join(missing)}")
            return False
        logger.info("All ADBPG required environment variables are set")
        return True
    
    def _check_graphrag_env(self):
        required = [
            "graphrag_llm_model", 
            "graphrag_api_key", 
            "graphrag_base_url",
            "graphrag_embedding_model", 
            "graphrag_embedding_api_key", 
            "graphrag_embedding_base_url"
        ]
        missing = [var.replace('graphrag_', 'GRAPHRAG_').upper() for var in required if not getattr(self, var)]
        if missing:
            logger.warning(f"Missing GraphRAG environment variables: {', '.join(missing)}. GraphRAG tools will be disabled.")
            return False
        logger.info("All GraphRAG required environment variables are set")
        return True
    
    def _check_memory_env(self):
        required = [
            "memory_llm_model", "memory_api_key", "memory_base_url", "memory_embedding_model"
        ]
        missing = [var.replace('memory_', 'LLMEMORY_').upper() for var in required if not getattr(self, var)]
        if missing:
            logger.warning(f"Missing LLM Memory environment variables: {', '.join(missing)}. LLM Memory tools will be disabled.")
            return False
        logger.info("All LLM Memory required environment variables are set")
        return True
    
    def get_db_connection_info(self):
        if not self.db_env_ready:
            raise ValueError("Database environment variables are not set.")
        return {
            "host": self.db_host,
            "port": self.db_port,
            "user": self.db_user,
            "password": self.db_password,
            "dbname": self.db_name,
            "application_name": f"adbpg-mcp-server-{SERVER_VERSION}"
        }

    def get_graphrag_init_config(self):
        if not self.graphrag_env_ready:
            return None
        return {
            "llm_model": self.graphrag_llm_model,
            "llm_api_key": self.graphrag_api_key,
            "llm_url": self.graphrag_base_url,
            "embedding_model": self.graphrag_embedding_model,
            "embedding_api_key": self.graphrag_embedding_api_key,
            "embedding_url": self.graphrag_embedding_base_url,
            "language": self.graphrag_language,
            "entity_types": self.graphrag_entity_types,
            "relationship_types": self.graphrag_relationship_types,
            "postgres_password": self.db_password
        }
    def get_memory_init_config(self, db_master_port: int):
        if not self.memory_env_ready:
            return None
        config = {
            "llm": {
                "provider": "openai", 
                "config": {
                    "model": self.memory_llm_model,
                    "openai_base_url": self.memory_base_url,
                    "api_key": self.memory_api_key
                }},
            "embedder": {
                "provider": "openai", 
                "config": {
                    "model": self.memory_embedding_model,
                    "embedding_dims": self.memory_embedding_dims,
                    "api_key": self.memory_api_key,
                    "openai_base_url": self.memory_base_url
                }},
            "vector_store": {
                "provider": "adbpg", 
                "config": {
                    "user": self.db_user,
                    "password": self.db_password,
                    "dbname": self.db_name,
                    "hnsw": "True",
                    "embedding_model_dims": self.memory_embedding_dims,
                    "port": db_master_port
                }}
        }
        if self.memory_enable_graph:
            config["graph_store"] = {
                "provider": "adbpg", 
                "config": {
                    "url": "http://localhost",
                    "username": self.db_user,
                    "password": self.db_password,
                    "database": self.db_name,
                    "port": db_master_port
                }
            }
        return config

settings = AppConfig()