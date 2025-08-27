# AnalyticDB PostgreSQL MCP Server

AnalyticDB PostgreSQL MCP Server serves as a universal interface between AI Agents and AnalyticDB PostgreSQL databases. It enables seamless communication between AI Agents and AnalyticDB PostgreSQL, helping AI Agents retrieve database metadata and execute SQL operations.

## Configuration



### Mode 1: Download

Download from Github

```shell
git clone https://github.com/aliyun/alibabacloud-adbpg-mcp-server.git
```

#### MCP Integration

Add the following configuration to the MCP client configuration file:

```json
"mcpServers": {
  "adbpg-mcp-server": {
    "command": "uv",
    "args": [
      "--directory",
      "/path/to/adbpg-mcp-server",
      "run",
      "adbpg-mcp-server"
    ],
    "env": {
      "ADBPG_HOST": "host",
      "ADBPG_PORT": "port",
      "ADBPG_USER": "username",
      "ADBPG_PASSWORD": "password",
      "ADBPG_DATABASE": "database",
      "GRAPHRAG_API_KEY": "graphrag llm api key",
      "GRAPHRAG_BASE_URL": "graphrag llm base url",
      "GRAPHRAG_LLM_MODEL": "graphrag llm model name",
      "GRAPHRAG_EMBEDDING_MODEL": "graphrag embedding model name",
      "GRAPHRAG_EMBEDDING_API_KEY": "graphrag embedding api key",
      "GRAPHRAG_EMBEDDING_BASE_URL": "graphrag embedding url",
      "LLMEMORY_API_KEY": "llm memory api_key",
      "LLMEMORY_BASE_URL": "llm memory base_url",
      "LLMEMORY_LLM_MODEL": "llm memory model name",
      "LLMEMORY_EMBEDDING_MODEL": "llm memory embedding model name",
      "LLMEMORY_ENABLE_GRAPH": "enable graph engine for llm memory (Default: false)"
    }
  }
}
```

### Mode 2: Using pip

```
pip install adbpg_mcp_server
```
#### MCP Integration
```json
"mcpServers": {
  "adbpg-mcp-server": {
    "command": "uvx",
    "args": [
      "adbpg_mcp_server"
    ],
    "env": {
      "ADBPG_HOST": "host",
      "ADBPG_PORT": "port",
      "ADBPG_USER": "username",
      "ADBPG_PASSWORD": "password",
      "ADBPG_DATABASE": "database",
      "GRAPHRAG_API_KEY": "graphrag api_key",
      "GRAPHRAG_BASE_URL": "graphrag base_url",
      "GRAPHRAG_LLM_MODEL": "graphrag model name",
      "GRAPHRAG_EMBEDDING_MODEL": "graphrag embedding model name",
      "GRAPHRAG_EMBEDDING_API_KEY": "graphrag embedding api key",
      "GRAPHRAG_EMBEDDING_BASE_URL": "graphrag embedding url",
      "LLMEMORY_API_KEY": "llm memory api_key",
      "LLMEMORY_BASE_URL": "llm memory base_url",
      "LLMEMORY_LLM_MODEL": "llm memory model name",
      "LLMEMORY_EMBEDDING_MODEL": "llm memory embedding model name"
      "LLMEMORY_ENABLE_GRAPH": "enable graph engine for llm memory (Default: false)"
    }
  }
}
```

## Components

### Tools

* `execute_select_sql`: Execute SELECT SQL queries on the AnalyticDB PostgreSQL server
* `execute_dml_sql`: Execute DML (INSERT, UPDATE, DELETE) SQL queries on the AnalyticDB PostgreSQL server
* `execute_ddl_sql`: Execute DDL (CREATE, ALTER, DROP) SQL queries on the AnalyticDB PostgreSQL server
* `analyze_table`: Collect table statistics
* `explain_query`: Get query execution plan

* `adbpg_graphrag_upload`
    - **Description:** Upload a text file (with its name) and file content to graphrag to generate a knowledge graph.
    - **Parameters:**
        - `filename` (`text`): The name of the file to be uploaded.
        - `context` (`text`): The textual content of the file.

* `adbpg_graphrag_query`
    - **Description:** Query the graphrag using the specified query string and mode.
    - **Parameters:**
        - `query_str` (`text`): The query content.
        - `query_mode` (`text`): The query mode, choose from `[bypass, naive, local, global, hybrid, mix]`. If null, defaults to `mix`.

* `adbpg_graphrag_upload_decision_tree`  
    - **Description:** Upload a decision tree with the specified `root_node`. If the `root_node` does not exist, a new decision tree will be created.
    - **Parameters:**
        - `context` (`text`): The textual representation of the decision tree.
        - `root_node` (`text`): The content of the root node.

* `adbpg_graphrag_append_decision_tree`  
    - **Description:** Append a subtree to an existing decision tree at the node specified by `root_node_id`.
    - **Parameters:**
        - `context` (`text`): The textual representation of the subtree.
        - `root_node_id` (`text`): The ID of the node to which the subtree will be appended.

* `adbpg_graphrag_delete_decision_tree`  
    - **Description:** Delete a sub-decision tree under the node specified by `root_node_entity`.
    - **Parameters:**
        - `root_node_entity` (`text`): The ID of the root node of the sub-decision tree to be deleted.

* `adbpg_llm_memory_add`
    - **Description:** Add LLM long memory with a specific user, run or agent.
    - **Parameters:**
        - `messages` (`json`): The messages.
        - `user_id` (`text`): User id.
        - `run_id` (`text`): Run id.
        - `agent_id` (`text`): Agent id.
        - `metadata` (`json`): The metadata json(optional).
        - `memory_type` (`text`): The memory type(optional).
        - `prompt` (`text`): The prompt(optional).
        
        **Note:**  
        At least one of `user_id`, `run_id`, or `agent_id` should be provided.

* `adbpg_llm_memory_get_all`
    - **Description:** Retrieves all memory records associated with a specific user, run or agent.
    - **Parameters:**
        - `user_id` (`text`): User ID.
        - `run_id` (`text`): Run ID.
        - `agent_id` (`text`): Agent ID.
        
        **Note:**  
        At least one of `user_id`, `run_id`, or `agent_id` should be provided.

* `adbpg_llm_memory_search`
    - **Description:**  Retrieves memories relevant to the given query for a specific user, run, or agent.
    - **Parameters:**
        - `query` (`text`): The search query string.
        - `user_id` (`text`): User ID.
        - `run_id` (`text`): Run ID.
        - `agent_id` (`text`): Agent ID.
        - `filter` (`json`): Additional filter conditions in JSON format (optional).
        
        **Note:**  
        At least one of `user_id`, `run_id`, or `agent_id` should be provided.

* `adbpg_llm_memory_delete_all`:
    - **Description:** Delete all memory records associated with a specific user, run or agent.
    - **Parameters:**
        - `user_id` (`text`): User ID.
        - `run_id` (`text`): Run ID.
        - `agent_id` (`text`): Agent ID.
       
        **Note:**  
        At least one of `user_id`, `run_id`, or `agent_id` should be provided.

### Resources

#### Built-in Resources

* `adbpg:///schemas`: Get all schemas in the database

#### Resource Templates

* `adbpg:///{schema}/tables`: List all tables in a specific schema
* `adbpg:///{schema}/{table}/ddl`: Get table DDL
* `adbpg:///{schema}/{table}/statistics`: Show table statistics

## Environment Variables

MCP Server requires the following environment variables to connect to AnalyticDB PostgreSQL instance:

- `ADBPG_HOST`: Database host address
- `ADBPG_PORT`: Database port
- `ADBPG_USER`: Database username
- `ADBPG_PASSWORD`: Database password
- `ADBPG_DATABASE`: Database name

MCP Server requires the following environment variables to initialize graphRAG and llm memory server：

- `GRAPHRAG_API_KEY`: API key for LLM provider
- `GRAPHRAG_BASE_URL`: Base URL for LLM service endpoint
- `GRAPHRAG_LLM_MODEL`: LLM model name or identifier
- `GRAPHRAG_EMBEDDING_MODEL`: Embedding model name or identifier
- `GRAPHRAG_EMBEDDING_API_KEY`: API key for embedding model provider
- `GRAPHRAG_EMBEDDING_BASE_URL`: Base URL for embedding service endpoint
- `GRAPHRAG_LANGUAGE`: (Optional)The language used by graphrag. Defaults to English if not set.
- `GRAPHRAG_ENTITY_TYPES`: (Optional) Specifies the types of entity nodes to be extracted when parsing the document to generate the knowledge graph.
- `GRAPHRAG_RELATIONSHIP_TYPES`: (Optional) Specifies the types of relationship edges to be extracted when parsing the document to generate the knowledge graph.

- `LLMEMORY_API_KEY`: API key for LLM provider or embedding API
- `LLMEMORY_BASE_URL`: Base URL for LLM or embedding service endpoint
- `LLMEMORY_LLM_MODEL`: LLM model name or identifier
- `LLMEMORY_EMBEDDING_MODEL`: Embedding model name or identifier
- `LLMEMORY_ENABLE_GRAPH`: (Optional) Enable graph engine for llm memory (Default: false)

## Dependencies

- Python 3.10 or higher
- Required packages:
  - mcp >= 1.4.0
  - psycopg >= 3.1.0
  - python-dotenv >= 1.0.0
  - pydantic >= 2.0.0

## Running

```bash
# Create and activate virtual environment
uv venv .venv
source .venv/bin/activate  # Linux/Mac
# or
.venv\Scripts\activate     # Windows

# Install dependencies
uv pip install -e .

# Run server
uv run adbpg-mcp-server
```


