# AnalyticDB PostgreSQL MCP Server

AnalyticDB PostgreSQL MCP Server serves as a universal interface between AI Agents and AnalyticDB PostgreSQL databases. It enables seamless communication between AI Agents and AnalyticDB PostgreSQL, helping AI Agents retrieve database metadata and execute SQL operations.

## Installation

You can set up the server either from the source code for development or by installing it from PyPI for direct use.

### Option 1: From Source (for Development)

This method is recommended if you want to modify or contribute to the server.

```shell
# 1. Clone the repository
git clone https://github.com/aliyun/alibabacloud-adbpg-mcp-server.git
cd alibabacloud-adbpg-mcp-server

# 2. Create and activate a virtual environment using uv
uv venv .venv
source .venv/bin/activate  # On Linux/macOS
# .\.venv\Scripts\activate  # On Windows

# 3. Install the project in editable mode
uv pip install -e .
```

### Option 2: From PyPI (for Production/Usage)

This is the simplest way to install the server for direct use within your projects.

```shell
pip install adbpg-mcp-server
```

## Running the Server

The server can be run in two transport modes: `stdio` (default) for integration with MCP clients, and `http` for direct API access or debugging.

Make sure you have set up the required [Environment Variables](#environment-variables) before running the server.

### Stdio Mode (Default)

This is the standard mode for communication with an MCP client.

```bash
# Run using the default transport (stdio)
uv run adbpg-mcp-server

# Or explicitly specify the transport
uv run adbpg-mcp-server --transport stdio
```

### Streamable-HTTP Mode

This mode exposes an HTTP server, which is useful for testing, debugging, or direct integration via REST APIs.

```bash
# Run the server in HTTP mode on the default host and port (127.0.0.1:3000)
uv run adbpg-mcp-server --transport http

# Specify a custom host and port with authentication
uv run adbpg-mcp-server --transport http --host 0.0.0.0 --port 3000 --auth-token your-secret-token
```

> **Security:** When binding to `0.0.0.0` or any network-accessible address, always set an authentication token via `--auth-token` or the `MCP_AUTH_TOKEN` environment variable. Without a token, the `/mcp` endpoint is open to unauthenticated access. Clients must include the `Authorization: Bearer <token>` header in all requests.

## MCP Integration

To integrate this server with a parent MCP client, add the following configuration to the client's configuration file. The arguments in the `args` array will depend on the transport protocol you choose.

### Example for Stdio Transport 

```json
"mcpServers": {
  "adbpg-mcp-server": {
    "command": "uv",
    "args": [
      "run",
      "adbpg-mcp-server",
      "--transport",
      "stdio"
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
> **Note:** Since `stdio` is the default, you can optionally omit `"--transport", "stdio"` from the `args` array.

### Example for Streamable-HTTP Transport

```json
"mcpServers": {
  "adbpg-mcp-server": {
    "command": "uv",
    "args": [
      "run",
      "adbpg-mcp-server",
      "--transport",
      "http",
      "--port",
      "3000"
    ],
    "env": {
      "ADBPG_HOST": "host",
      "ADBPG_PORT": "port",
      "ADBPG_USER": "username",
      "ADBPG_PASSWORD": "password",
      "ADBPG_DATABASE": "database",
      "MCP_AUTH_TOKEN": "your-secret-token",
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
    - **Description:** Query the graphrag using the specified query string and mode。
    - **Parameters:**
        - `query_str` (`text`): the query content.
        - `query_mode` (`text`): The query mode, choose from `[bypass, naive, local, global, hybrid, mix]`. If null, defaults to `mix`.

* `adbpg_graphrag.upload_decision_tree(context text, root_node text)`  
    - **Description:** Upload a decision tree with the specified `root_node`. If the `root_node` does not exist, a new decision tree will be created.
    - **Parameters:**
        - `context` (`text`): The textual representation of the decision tree.
        - `root_node` (`text`): The content of the root node.

* `adbpg_graphrag.append_decision_tree(context text, root_node_id text)`  
    - **Description:** Append a subtree to an existing decision tree at the node specified by `root_node_id`.
    - **Parameters:**
        - `context` (`text`): The textual representation of the subtree.
        - `root_node_id` (`text`): The ID of the node to which the subtree will be appended.

* `adbpg_graphrag.delete_decision_tree(root_node_entity text)`  
    - **Description:** Delete a sub-decision tree under the node specified by `root_node_entity`.
    - **Parameters:**
        - `root_node_entity` (`text`): The ID of the root node of the sub-decision tree to be deleted.




* `adbpg_llm_memory_add`
    - **Description:** Add LLM long memory.
    - **Parameters:**
        - `messages` (`json`): The name of the file to be uploaded.
        - `user_id` (`text`): The user id.
        - `run_id` (`text`): The run id.
        - `agent_id` (`text`): The agent id.
        - `metadata` (`json`): The metadata json(optional).
        - `memory_type` (`text`): The memory type(optional).
        - `prompt` (`text`): The prompt(optional).
        **Note:**  
        At least one of `user_id`, `run_id`, or `agent_id` should be provided.

* `adbpg_llm_memory_get_all`
    - **Description:** Retrieves all memory records associated with a specific user, run or agent.
    - **Parameters:**
        - `user_id` (`text`): User ID (optional). If provided, fetch all memories for this user.
        - `run_id` (`text`): Run ID (optional).
        - `agent_id` (`text`): Agent ID (optional). If provided, fetch all memories for this agent.
        **Note:**  
        At least one of `user_id`, `run_id`, or `agent_id` should be provided.

* `adbpg_llm_memory_search`
    - **Description:**  Retrieves memories relevant to the given query for a specific user, run, or agent.
    - **Parameters:**
        - `query` (`text`): The search query string.
        - `user_id` (`text`): User ID (optional). If provided, fetch all memories for this user.
        - `run_id` (`text`): Run ID (optional).
        - `agent_id` (`text`): Agent ID (optional). If provided, fetch all memories for this agent.
        - `filter` (`json`): Additional filter conditions in JSON format (optional).
        **Note:**  
        At least one of `user_id`, `run_id`, or `agent_id` should be provided.

* `adbpg_llm_memory_delete_all`:
    - **Description:** Delete all memory records associated with a specific user, run or agent.
    - **Parameters:**
        - `user_id` (`text`): User ID (optional). If provided, fetch all memories for this user.
        - `run_id` (`text`): Run ID (optional).
        - `agent_id` (`text`): Agent ID (optional). If provided, fetch all memories for this agent.
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

For HTTP transport mode, the following optional variable enables endpoint authentication:

- `MCP_AUTH_TOKEN`: Bearer token for HTTP endpoint authentication (can also be set via `--auth-token` CLI argument). **Strongly recommended** when binding to non-loopback addresses.

MCP Server requires the following environment variables to initialize graphRAG and llm memory server：

- `API_KEY`: API key for LLM provider or embedding API
- `BASE_URL`: Base URL for LLM or embedding service endpoint
- `LLM_MODEL`: LLM model name or identifier
- `EMBEDDING_MODEL`: Embedding model name or identifier


## Dependencies

*   Python 3.11 or higher
*   `uv` (for environment and package management)