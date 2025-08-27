import asyncio
import logging
import os
import sys
import json
import psycopg
import re
import ast
from psycopg import OperationalError as Error
from psycopg import Connection
from mcp.server import Server
from mcp.types import Resource, Tool, TextContent, ResourceTemplate
from pydantic import AnyUrl
from dotenv import load_dotenv
from mcp.server.stdio import stdio_server

# 配置日志，输出到标准错误
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    stream=sys.stderr
)
logger = logging.getLogger("adbpg-mcp-server")

# 检查环境变量Flag
GRAPHRAG_ENV_IS_READY = True
LLMEMORY_ENV_IS_READY = True
# 加载环境变量
try:
    load_dotenv()
    logger.info("Environment variables loaded")
    
    # 检查必要的环境变量
    required_vars = ["ADBPG_HOST", "ADBPG_PORT", "ADBPG_USER", "ADBPG_PASSWORD", "ADBPG_DATABASE"]
    missing_vars = [var for var in required_vars if not os.getenv(var)]
    if missing_vars:
        error_msg = f"Missing required environment variables: {', '.join(missing_vars)}"
        logger.error(error_msg)
        raise ValueError(error_msg)
    logger.info("All ADBPG required environment variables are set")

    # 检查graphrag/llmemory 环境变量
    required_graphrag_vars = [
        "GRAPHRAG_LLM_MODEL", 
        "GRAPHRAG_API_KEY", 
        "GRAPHRAG_BASE_URL", 
        "GRAPHRAG_EMBEDDING_MODEL",
        "GRAPHRAG_EMBEDDING_BASE_URL",
        "GRAPHRAG_EMBEDDING_API_KEY"
        ]
    missing_graphrag_vars = [var for var in required_graphrag_vars if not os.getenv(var)]
    if missing_graphrag_vars:
        GRAPHRAG_ENV_IS_READY = False
        error_msg = f"Missing required graphrag environment variables:{', '.join(missing_graphrag_vars)}"
        logger.error(error_msg)
    else:
        logger.info("All graphRAG required environment variables are set")

    required_llmemory_vars = ["LLMEMORY_LLM_MODEL", "LLMEMORY_API_KEY", "LLMEMORY_BASE_URL", "LLMEMORY_EMBEDDING_MODEL"]
    missing_llmemory_vars = [var for var in required_llmemory_vars if not os.getenv(var)]
    if missing_llmemory_vars:
        LLMEMORY_ENV_IS_READY = False
        error_msg = f"Missing required llm memory environment variables:{', '.join(missing_llmemory_vars)}"
        logger.error(error_msg)
    else:
        logger.info("All llm memory required environment variables are set")
    

except Exception as e:
    logger.error(f"Error loading environment variables: {e}")
    sys.exit(1)

SERVER_VERSION = "0.2.0"


# 获得 graphrag 初始化配置
def get_graphrag_config():
    graphrag_config = {
        "llm_model": os.getenv("GRAPHRAG_LLM_MODEL"),
        "llm_api_key": os.getenv("GRAPHRAG_API_KEY"),
        "llm_url": os.getenv("GRAPHRAG_BASE_URL"),
        "embedding_model": os.getenv("GRAPHRAG_EMBEDDING_MODEL"),
        "embedding_api_key": os.getenv("GRAPHRAG_EMBEDDING_API_KEY"),
        "embedding_url": os.getenv("GRAPHRAG_EMBEDDING_BASE_URL"),
        "language": os.getenv("GRAPHRAG_LANGUAGE", "English"),
        "entity_types": os.getenv("GRAPHRAG_ENTITY_TYPES"),
        "relationship_types": os.getenv("GRAPHRAG_RELATIONSHIP_TYPES"),
        "postgres_password": os.getenv("ADBPG_PASSWORD")
    }
    return graphrag_config
    
# 获得llmemory 初始化配置
def get_llmemory_config():
    config = get_db_config()
    port = 3000
    sql = """
        select port from gp_segment_configuration where content = -1 and role = 'p';
    """
    try:
        with psycopg.connect(**config) as conn:
            conn.autocommit = True
            with conn.cursor() as cursor:
                cursor.execute(sql)
                port = cursor.fetchone()[0]
    except Error as e:
        raise RuntimeError(f"Database error: {str(e)}")
    llmemory_enable_graph = os.getenv("LLMEMORY_ENABLE_GRAPH", "False") 
    

    llm_memory_config = {
        "llm": {
            "provider": "openai",
            "config": {
                "model": os.getenv("LLMEMORY_LLM_MODEL"),
                "openai_base_url": os.getenv("LLMEMORY_BASE_URL"),
                "api_key": os.getenv("LLMEMORY_API_KEY")
            }
        },
        "embedder": {
            "provider": "openai",
            "config": {
                "model": os.getenv("LLMEMORY_EMBEDDING_MODEL"),
                "embedding_dims": os.getenv("LLMEMORY_EMBEDDING_DIMS", 1024),
                "api_key": os.getenv("LLMEMORY_API_KEY"),
                "openai_base_url": os.getenv("LLMEMORY_BASE_URL")
            }
        },
        "vector_store": {
            "provider": "adbpg",
            "config": {
                "user": os.getenv("ADBPG_USER"),
                "password": os.getenv("ADBPG_PASSWORD"),
                "dbname": os.getenv("ADBPG_DATABASE"),
                "hnsw": "True",
                "embedding_model_dims": os.getenv("LLMEMORY_EMBEDDING_DIMS", 1024),
                "port": port
            }
        }
    }
    if llmemory_enable_graph == "True" or llmemory_enable_graph == "true":
        llm_memory_config["graph_store"] = {
            "provider": "adbpg",
            "config": {
                "url": "http://localhost",
                "username": os.getenv("ADBPG_USER"),
                "password": os.getenv("ADBPG_PASSWORD"),
                "database": os.getenv("ADBPG_DATABASE"),
                "port": port
            }
        }
    return llm_memory_config

def get_db_config():
    """从环境变量获取数据库配置信息"""
    try:
        config = {
            "host": os.getenv("ADBPG_HOST", "localhost"),
            "port": os.getenv("ADBPG_PORT"),
            "user": os.getenv("ADBPG_USER"),
            "password": os.getenv("ADBPG_PASSWORD"),
            "dbname": os.getenv("ADBPG_DATABASE"),
            "application_name": f"adbpg-mcp-server-{SERVER_VERSION}"
        }
        
        # 记录配置信息（不包含密码）
        logger.info(f"Database config: host={config['host']}, port={config['port']}, user={config['user']}, dbname={config['dbname']}")
        return config
    except Exception as e:
        logger.error(f"Error getting database config: {str(e)}")
        raise

# 全局graphrag长连接 并 初始化
GRAPHRAG_CONN: Connection | None = None
def get_graphrag_tool_connection() -> Connection:
    global GRAPHRAG_CONN
    global GRAPHRAG_ENV_IS_READY
    config = get_db_config()
    # 如果未连接，或者连接失效 重新连接
    if GRAPHRAG_CONN is None or GRAPHRAG_CONN.closed:
        GRAPHRAG_CONN = psycopg.connect(**config)
        GRAPHRAG_CONN.autocommit = True
        try:
            graphrag_conn = GRAPHRAG_CONN
            with graphrag_conn.cursor() as cursor:
                cursor.execute("SELECT adbpg_graphrag.initialize(%s::json);", (graphrag_config_str,))    
                logger.info(f"[GraphRAG] Use the connection {id(graphrag_conn)} when executing the graphrag init")
            logger.info("Successfully initialize the graphrag server\n")
        except Exception as e:
            GRAPHRAG_ENV_IS_READY = False
            logger.error(f"Failed to initialize the graphrag server: {e}")
        # 重新执行初始化
    else:
        # 发送一个轻量级查询 检测 连接是否健康
        try:
            with GRAPHRAG_CONN.cursor() as cur:
                cur.execute("SELECT 1;")
                _ = cur.fetchone()
        except Exception:
            # 重连
            GRAPHRAG_CONN.close()
            GRAPHRAG_CONN = psycopg.connect(**config)
            GRAPHRAG_CONN.autocommit = True
            # 重新执行初始化
            try:
                graphrag_conn = GRAPHRAG_CONN
                with graphrag_conn.cursor() as cursor:
                    cursor.execute("SELECT adbpg_graphrag.initialize(%s::json);", (graphrag_config_str,))
                    logger.info(f"[GraphRAG] Use the connection {id(graphrag_conn)} when executing the graphrag init")
                logger.info("Successfully initialize the graphrag server\n")
            except Exception as e:
                GRAPHRAG_ENV_IS_READY = False
                logger.error(f"Failed to initialize the graphrag server: {e}")
    
    return GRAPHRAG_CONN

LLM_MEMORY_CONN: Connection | None = None
def get_llm_memory_tool_connection() -> Connection:
    global LLMEMORY_ENV_IS_READY
    global LLM_MEMORY_CONN
    config = get_db_config()
    # 如果未连接，或者连接失效 重新连接
    if LLM_MEMORY_CONN is None or LLM_MEMORY_CONN.closed:
        LLM_MEMORY_CONN = psycopg.connect(**config)
        LLM_MEMORY_CONN.autocommit = True
        try:
            llm_memory_conn = LLM_MEMORY_CONN
            with llm_memory_conn.cursor() as cursor:
                cursor.execute("SELECT adbpg_llm_memory.config(%s::json)", (llm_memory_config_str,))
                logger.info(f"[LLM Memory] Use the connection {id(llm_memory_conn)} when executing the llm_memory init")
            logger.info("Successfully initialize the llm server\n")
        except Exception as e:
            LLMEMORY_ENV_IS_READY = False
            logger.error(f"Failed to initialize the llm_memory server: {e}")
    else:
        # 发送一个轻量级查询 检测 连接是否健康
        try:
            with LLM_MEMORY_CONN.cursor() as cur:
                cur.execute("SELECT 1;")
                _ = cur.fetchone()
        except Exception:
            # 重连
            LLM_MEMORY_CONN.close()
            LLM_MEMORY_CONN = psycopg.connect(**config)
            LLM_MEMORY_CONN.autocommit = True
            try:
                llm_memory_conn = LLM_MEMORY_CONN
                with llm_memory_conn.cursor() as cursor:
                    cursor.execute("SELECT adbpg_llm_memory.config(%s::json)", (llm_memory_config_str,))
                    logger.info(f"[LLM Memory] Use the connection {id(llm_memory_conn)} when executing the llm_memory init")
                logger.info("Successfully initialize the llm server\n")
            except Exception as e:
                LLMEMORY_ENV_IS_READY = False
                logger.error(f"Failed to initialize the llm_memory server: {e}")

    return LLM_MEMORY_CONN

#### 初始化 
if GRAPHRAG_ENV_IS_READY == True:
    # 初始化 graphrag
    logger.info("Starting graphRAG server...")
    graphrag_config = get_graphrag_config()
    graphrag_config_str = json.dumps(graphrag_config)
    # 建立长连接 并 初始化
    get_graphrag_tool_connection()
if LLMEMORY_ENV_IS_READY == True:
    # 初始化 llmemory
    logger.info("Starting llmemory server...")
    llm_memory_config = get_llmemory_config()
    llm_memory_config_str = json.dumps(llm_memory_config)
    # 建立长连接 并 初始化
    get_llm_memory_tool_connection()

# 初始化服务器
try:
    app = Server("adbpg-mcp-server")
    logger.info("MCP server initialized")
except Exception as e:
    logger.error(f"Error initializing MCP server: {e}")
    sys.exit(1)

@app.list_resources()
async def list_resources() -> list[Resource]:
    """列出可用的基本资源"""
    try:
        return [
            Resource(
                uri="adbpg:///schemas",
                name="All Schemas",
                description="AnalyticDB PostgreSQL schemas. List all schemas in the database",
                mimeType="text/plain"
            )
        ]
    except Exception as e:
        logger.error(f"Error listing resources: {str(e)}")
        raise

@app.list_resource_templates()
async def list_resource_templates() -> list[ResourceTemplate]:
    """
    定义动态资源模板
    
    返回:
        list[ResourceTemplate]: 资源模板列表
        包含以下模板：
        - 列出schema中的表
        - 获取表DDL
        - 获取表统计信息
    """
    return [
        ResourceTemplate(
            uriTemplate="adbpg:///{schema}/tables",  # 表列表模板
            name="Schema Tables",
            description="List all tables in a specific schema",
            mimeType="text/plain"
        ),
        ResourceTemplate(
            uriTemplate="adbpg:///{schema}/{table}/ddl",  # 表DDL模板
            name="Table DDL",
            description="Get the DDL script of a table in a specific schema",
            mimeType="text/plain"
        ),
        ResourceTemplate(
            uriTemplate="adbpg:///{schema}/{table}/statistics",  # 表统计信息模板
            name="Table Statistics",
            description="Get statistics information of a table",
            mimeType="text/plain"
        )
    ]

@app.read_resource()
async def read_resource(uri: AnyUrl) -> str:
    """
    读取资源内容
    
    参数:
        uri (AnyUrl): 资源URI
        
    返回:
        str: 资源内容
        
    支持的URI格式：
    - adbpg:///schemas: 列出所有schema
    - adbpg:///{schema}/tables: 列出指定schema中的表
    - adbpg:///{schema}/{table}/ddl: 获取表的DDL
    - adbpg:///{schema}/{table}/statistics: 获取表的统计信息
    """
    config = get_db_config()
    uri_str = str(uri)
    
    if not uri_str.startswith("adbpg:///"):
        raise ValueError(f"Invalid URI scheme: {uri_str}")
    
    try:
        with psycopg.connect(**config) as conn:  # 建立数据库连接
            conn.autocommit = True  # 设置自动提交
            with conn.cursor() as cursor:  # 创建游标
                path_parts = uri_str[9:].split('/')  # 解析URI路径
                
                if path_parts[0] == "schemas":
                    # 列出所有schema
                    query = """
                        SELECT schema_name 
                        FROM information_schema.schemata 
                        WHERE schema_name NOT IN ('pg_catalog', 'information_schema')
                        ORDER BY schema_name;
                    """
                    cursor.execute(query)
                    schemas = cursor.fetchall()
                    return "\n".join([schema[0] for schema in schemas])
                    
                elif len(path_parts) == 2 and path_parts[1] == "tables":
                    # 列出指定schema中的表
                    schema = path_parts[0]
                    query = f"""
                        SELECT table_name, table_type
                        FROM information_schema.tables
                        WHERE table_schema = %s
                        ORDER BY table_name;
                    """
                    cursor.execute(query, (schema,))
                    tables = cursor.fetchall()
                    return "\n".join([f"{table[0]} ({table[1]})" for table in tables])
                    
                elif len(path_parts) == 3 and path_parts[2] == "ddl":
                    # 获取表的DDL
                    schema = path_parts[0]
                    table = path_parts[1]
                    query = f"""
                        SELECT pg_get_ddl('{schema}.{table}'::regclass);
                    """
                    cursor.execute(query)
                    ddl = cursor.fetchone()
                    return ddl[0] if ddl else f"No DDL found for {schema}.{table}"
                    
                elif len(path_parts) == 3 and path_parts[2] == "statistics":
                    # 获取表的统计信息
                    schema = path_parts[0]
                    table = path_parts[1]
                    query = """
                        SELECT 
                            schemaname,
                            tablename,
                            attname,
                            null_frac,
                            avg_width,
                            n_distinct,
                            most_common_vals,
                            most_common_freqs
                        FROM pg_stats
                        WHERE schemaname = %s AND tablename = %s
                        ORDER BY attname;
                    """
                    cursor.execute(query, (schema, table))
                    rows = cursor.fetchall()
                    if not rows:
                        return f"No statistics found for {schema}.{table}"
                    
                    result = []
                    for row in rows:
                        result.append(f"Column: {row[2]}")
                        result.append(f"  Null fraction: {row[3]}")
                        result.append(f"  Average width: {row[4]}")
                        result.append(f"  Distinct values: {row[5]}")
                        if row[6]:
                            result.append(f"  Most common values: {row[6]}")
                            result.append(f"  Most common frequencies: {row[7]}")
                        result.append("")
                    return "\n".join(result)
                
                raise ValueError(f"Invalid resource URI format: {uri_str}")
      
    except Error as e:
        raise RuntimeError(f"Database error: {str(e)}")

@app.list_tools()
async def list_tools() -> list[Tool]:
    """
    列出可用的工具
    
    返回:
        list[Tool]: 工具列表
        包含以下工具：
        - execute_select_sql: 执行SELECT查询
        - execute_dml_sql: 执行DML操作
        - execute_ddl_sql: 执行DDL操作
        - analyze_table: 分析表统计信息
        - explain_query: 获取查询执行计划

        - adbpg_graphrag_upload: 执行 graphRAG upload 操作，上传文本
        - adbpg_graphrag_query: 执行 graphRAG query 操作 
        - adbpg_graphrag_upload_decision_tree: 上传一个决策树
        - adbpg_graphrag_append_decision_tree: 在某个节点上新增子树
        - adbpg_graphrag_delete_decision_tree: 根据节点id删除起下层子树

        - adbpg_llm_memory_add: 执行新增记忆操作
        - adbpg_llm_memory_get_all: 获取所有记忆
        - adbpg_llm_memory_search: 根据查询检索记忆
        - adbpg_llm_memory_delete_all: 删除所有记忆
    """
    return [
        Tool(
            name="execute_select_sql",
            description="Execute SELECT SQL to query data from ADBPG database.",
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "The (SELECT) SQL query to execute"
                    }
                },
                "required": ["query"]
            }
        ),
        Tool(
            name="execute_dml_sql",
            description="Execute (INSERT, UPDATE, DELETE) SQL to modify data in ADBPG database.",
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "The DML SQL query to execute"
                    }
                },
                "required": ["query"]
            }
        ),
        Tool(
            name="execute_ddl_sql",
            description="Execute (CREATE, ALTER, DROP) SQL statements to manage database objects.",
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "The DDL SQL query to execute"
                    }
                },
                "required": ["query"]
            }
        ),
        Tool(
            name="analyze_table",
            description="Execute ANALYZE command to collect table statistics.",
            inputSchema={
                "type": "object",
                "properties": {
                    "schema": {
                        "type": "string",
                        "description": "Schema name"
                    },
                    "table": {
                        "type": "string",
                        "description": "Table name"
                    }
                },
                "required": ["schema", "table"]
            }
        ),
        Tool(
            name="explain_query",
            description="Get query execution plan.",
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "The SQL query to analyze"
                    }
                },
                "required": ["query"]
            }
        ),

        #### graphrag & llm_memory tool list
        Tool(
            name = "adbpg_graphrag_upload",
            description = "Execute graphrag upload operation",
            # 参数：filename text， context text
            # filename 表示文件名称， context 表示文件内容
            inputSchema = {
                "type": "object",
                "properties": {
                    "filename": {
                        "type": "string",
                        "description": "The file name need to upload"
                    },
                    "context": {
                        "type": "string",
                        "description": "the context of your file"
                    }
                },
                "required": ["filename", "context"]
            }
        ),
        Tool(
            name = "adbpg_graphrag_query",
            description = "Execute graphrag query operation",
            # 参数：query_str text, [query_mode text]
            # query_str 是询问的问题，query_mode 选择查询模式
            inputSchema = {
                "type": "object",
                "properties": {
                    "query_str": {
                        "type": "string",
                        "description": "The query you want to ask"
                    },
                    "query_mode": {
                        "type": "string",
                        "description": "The query mode you need to choose [ bypass,naive, local, global, hybrid, mix[default], tree ]."
                    },
                    "start_search_node_id": {
                        "type": "string",
                        "description": "If using 'tree' query mode, set the start node ID of tree."
                    }
                },
                "required": ["query_str"]
            }
        ),
        Tool(
            name = "adbpg_graphrag_upload_decision_tree",
            description = " Upload a decision tree with the specified root_node. If the root_node does not exist, a new decision tree will be created. ",
            # context text, root_node text
            inputSchema = {
                "type": "object",
                "properties": {
                    "root_node": {
                        "type": "string",
                        "description": "the root_noot (optional)"
                    },
                    "context": {
                        "type": "string",
                        "description": "the context of decision"
                    }
                },
                "required": ["context"]
            }
        ),
        Tool(
            name = "adbpg_graphrag_append_decision_tree",
            description = "Append a subtree to an existing decision tree at the node specified by root_node_id. ",
            # para: context text, root_node_id text
            inputSchema = {
                "type": "object",
                "properties": {
                    "root_node_id": {
                        "type": "string",
                        "description": "the root_noot_id"
                    },
                    "context": {
                        "type": "string",
                        "description": "the context of decision"
                    }
                },
                "required": ["context", "root_node_id"]
            }
        ),
        Tool(
            name = "adbpg_graphrag_delete_decision_tree",
            description = " Delete a sub-decision tree under the node specified by root_node_entity. ",
            # para: root_node_entity text
            inputSchema = {
                "type": "object",
                "properties": {
                    "root_node_entity": {
                        "type": "string",
                        "description": "the root_noot_entity"
                        
                    }
                },
                "required": ["root_node_entity"]
            }
        ),
        Tool(
            name = "adbpg_graphrag_reset_tree_query",
            description = " Reset the decision tree in the tree query mode",
            # para: 
            inputSchema = {
                "type": "object",
                "required": []
            }
        ),
        Tool(
            name = "adbpg_llm_memory_add",
            description = "Execute llm_memory add operation",
            # 参数：messages json, user_id text, run_id text, agent_id text, metadata json
            # 增加新的记忆
            inputSchema={
                "type": "object",
                "properties": {
                    "messages": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "role": {"type": "string"},
                                "content": {"type": "string"}
                            },
                            "required": ["role", "content"]
                        },
                        "description": "List of messages objects (e.g., conversation history)"
                    },
                    "user_id": {
                        "type": "string",
                        "description": "the user_id"
                    },
                    "run_id": {
                        "type": "string",
                        "description": "the run_id"
                    },
                    "agent_id": {
                        "type": "string",
                        "description": "the agent_id"
                    },
                    "metadata": {
                        "type": "object",
                        "description": "the metatdata json"
                    },
                    "memory_type": {
                        "type": "string",
                        "description": "the memory_type text"
                    },
                    "prompt": {
                        "type": "string",
                        "description": "the prompt"
                    }
                },
                "required": ["messages"]
            }
        ),
        Tool(
            name = "adbpg_llm_memory_get_all",
            description = "Execute llm_memory get_all operation",
            # 参数：user_id text, run_id text, agent_id text
            # 获取某个用户或者某个agent的所有记忆
            inputSchema={
                "type": "object",
                "properties": {
                    "user_id": {
                        "type": "string",
                        "description": "The user_id"
                    },
                    "run_id": {
                        "type": "string",
                        "description": "The run_id"
                    },
                    "agent_id": {
                        "type": "string",
                        "description": "The agent_id"
                    }
                },
                "required": []
            }
        ),
        Tool(
            name = "adbpg_llm_memory_search",
            description = "Execute llm_memory search operation",
            # 参数：query text, user_id text, run_id text, agent_id text, filter json
            # 获取与给定 query 相关的记忆
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "llm_memory relevant query"
                    },
                    "user_id": {
                        "type": "string",
                        "description": "The search of user_id"
                    },
                    "run_id": {
                        "type": "string",
                        "description": "The search of run_id"
                    },
                    "agent_id": {
                        "type": "string",
                        "description": "The search of agent_id"
                    },
                    "filter": {
                        "type": "object",
                        "description": "The search of filter"
                    }
                },
                "required": ["query"]
            }
        )
        ,
        Tool(
            name = "adbpg_llm_memory_delete_all",
            description = "Execute llm_memory delete_all operation",
            # 参数：user_id text, run_id text, agent_id text
            # 删除某个用户或者agent的所有记忆
            inputSchema={
                "type": "object",
                "properties": {
                    "user_id": {
                        "type": "string",
                        "description": "The user_id"
                    },
                    "run_id": {
                        "type": "string",
                        "description": "The run_id"
                    },
                    "agent_id": {
                        "type": "string",
                        "description": "The agent_id"
                    }
                },
                "required": []
            }
        )
        
    ]

def get_graphrag_tool_result(wrapped_sql, params) -> list[TextContent]:
    try:
        conn = get_graphrag_tool_connection()
        with conn.cursor() as cursor:
            cursor.execute(wrapped_sql, params)
            if cursor.description:
                json_result = cursor.fetchone()[0]
                return [TextContent(type="text", text=json_result)]
            else:
                return [TextContent(type="text", text="graphrag command executed successfully")]
    except Exception as e:
        return [TextContent(type="text", text=f"Error executing graphrag command: {str(e)}")]

def get_llm_memory_tool_result(wrapped_sql, params) -> list[TextContent]:
    try:
        conn = get_llm_memory_tool_connection()
        with conn.cursor() as cursor:

            cursor.execute(wrapped_sql, params)
            
            if cursor.description:
                json_result = cursor.fetchone()[0]
                return [TextContent(type="text", text=json_result)]
            else:
                return [TextContent(type="text", text="llm_memory command executed successfully")]
    except Exception as e:
        return [TextContent(type="text", text=f"Error executing llm_memory command: {str(e)}")]
            

@app.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:
    """
    执行工具操作
    
    参数:
        name (str): 工具名称
        arguments (dict): 工具参数
        
    返回:
        list[TextContent]: 执行结果
        
    支持的工具：
    - execute_select_sql: 执行SELECT查询
    - execute_dml_sql: 执行DML操作
    - execute_ddl_sql: 执行DDL操作
    - analyze_table: 分析表统计信息
    - explain_query: 获取查询执行计划
    
    - adbpg_graphrag_upload: 执行 graphRAG upload 操作，上传文本
    - adbpg_graphrag_query: 执行 graphRAG query 操作 

    - adbpg_llm_memory_add: 执行新增记忆操作
    - adbpg_llm_memory_get_all: 获取所有记忆
    - adbpg_llm_memory_search: 根据查询检索记忆
    - adbpg_llm_memory_delete_all: 删除所有记忆
    """
    config = get_db_config()
    global GRAPHRAG_ENV_IS_READY
    # 根据工具名称处理不同的操作
    if name == "execute_select_sql":
        query = arguments.get("query")
        if not query:
            raise ValueError("Query is required")
        if not query.strip().upper().startswith("SELECT"):
            raise ValueError("Query must be a SELECT statement")
        query = query.rstrip().rstrip(';')
        query = f"""
            SELECT json_agg(row_to_json(t))
            FROM ({query}) AS t
        """
    elif name == "execute_dml_sql":
        query = arguments.get("query")
        if not query:
            raise ValueError("Query is required")
        if not any(query.strip().upper().startswith(keyword) for keyword in ["INSERT", "UPDATE", "DELETE"]):
            raise ValueError("Query must be a DML statement (INSERT, UPDATE, DELETE)")
    elif name == "execute_ddl_sql":
        query = arguments.get("query")
        if not query:
            raise ValueError("Query is required")
        if not any(query.strip().upper().startswith(keyword) for keyword in ["CREATE", "ALTER", "DROP", "TRUNCATE"]):
            raise ValueError("Query must be a DDL statement (CREATE, ALTER, DROP)")
    elif name == "analyze_table":
        schema = arguments.get("schema")
        table = arguments.get("table")
        if not all([schema, table]):
            raise ValueError("Schema and table are required")
        query = f"ANALYZE {schema}.{table}"
    elif name == "explain_query":
        query = arguments.get("query")
        if not query:
            raise ValueError("Query is required")
        query = f"EXPLAIN {query}"

    # adbpg_graphrag tool
    elif name == "adbpg_graphrag_upload":
        # GraphRAG 服务初始化失败，工具不可用
        if GRAPHRAG_ENV_IS_READY == False:
            raise ValueError("GraphRAG Server initialization failed. This tool cannot be used.") 
        filename = arguments.get("filename")
        context = arguments.get("context")
        if not filename:
            raise ValueError("Filename is required")
        if not context:
            raise ValueError("Context if required")
        # 命令拼接
        wrapped_sql = f"""
                SELECT adbpg_graphrag.upload(%s::text, %s::text)
            """
        params = [filename, context]
        return get_graphrag_tool_result(wrapped_sql, params)

    elif name == "adbpg_graphrag_query":
        # GraphRAG 服务初始化失败，工具不可用
        if GRAPHRAG_ENV_IS_READY == False:
            raise ValueError("GraphRAG Server initialization failed. This tool cannot be used.") 
        query_str = arguments.get("query_str")
        query_mode = arguments.get("query_mode")
        start_search_node_id = arguments.get("start_search_node_id")

        if not query_str:
            raise ValueError("Query is required")
        if not query_mode:
            # default mode
            query_mode = "mix"
            
        wrapped_sql = f"""
            SELECT adbpg_graphrag.query(%s::text, %s::text)
        """
        params = [query_str, query_mode]

        if start_search_node_id:
            wrapped_sql = f"""
                    SELECT adbpg_graphrag.query(%s::text, %s::text, %s::text)
                """
            params = [query_str, query_mode, start_search_node_id]
        
        return get_graphrag_tool_result(wrapped_sql, params)
    
    elif name == "adbpg_graphrag_reset_tree_query":
        if GRAPHRAG_ENV_IS_READY == False:
            raise ValueError("GraphRAG Server initialization failed. This tool cannot be used.")
        wrapped_sql = f"""
            SELECT adbpg_graphrag.reset_tree_query()
        """
        params = []
        return get_graphrag_tool_result(wrapped_sql, params)
    
    elif name == "adbpg_graphrag_upload_decision_tree":
        if GRAPHRAG_ENV_IS_READY == False:
            raise ValueError("GraphRAG Server initialization failed. This tool cannot be used.")
        root_node = arguments.get("root_node")
        context = arguments.get("context")
        if not context:
            raise ValueError("Decision Tree Context is required")
        if not root_node:
            root_node = None
        wrapped_sql = f"""
            SELECT adbpg_graphrag.upload_decision_tree(%s::text, %s::text)
        """
        params = [context, root_node]
        return get_graphrag_tool_result(wrapped_sql, params)

    elif name == "adbpg_graphrag_append_decision_tree":
        if GRAPHRAG_ENV_IS_READY == False:
            raise ValueError("GraphRAG Server initialization failed. This tool cannot be used.") 
        root_node = arguments.get("root_node_id")
        context = arguments.get("context")
        if not context:
            raise ValueError("Decision Tree Context is required")
        if not root_node:
            raise ValueError("Root node id is required")
        wrapped_sql = f"""
            SELECT adbpg_graphrag.append_decision_tree(%s::text, %s::text)
        """
        params = [context, root_node]
        return get_graphrag_tool_result(wrapped_sql, params)

    elif name == "adbpg_graphrag_delete_decision_tree":
        if GRAPHRAG_ENV_IS_READY == False:
            raise ValueError("GraphRAG Server initialization failed. This tool cannot be used.") 
        root_node = arguments.get("root_node_entity")
        if not root_node:
            raise ValueError("Root node entity is required")
        wrapped_sql = f"""
            SELECT adbpg_graphrag.delete_decision_tree(%s::text, %s::text)
        """
        params = [root_node]
        return get_graphrag_tool_result(wrapped_sql, params)

    # adbpg_llm_memory tool
    elif name == "adbpg_llm_memory_add":
        # LLMEMORY 服务初始化失败，工具不可用
        if LLMEMORY_ENV_IS_READY == False:
            raise ValueError("LLMEMORY Server initialization failed. This tool cannot be used.") 

        messages = arguments.get("messages")
        if not messages:
            raise ValueError("messages is required")
        messages_str = json.dumps(messages, ensure_ascii = False)

        user_id = arguments.get("user_id")
        if not user_id:
            user_id = None
        run_id = arguments.get("run_id")
        if not run_id:
            run_id = None
        agent_id = arguments.get("agent_id")
        if not agent_id:
            agent_id = None
        if user_id == None and run_id == None and agent_id == None:
            raise ValueError("At least one of user_id, run_id, or agent_id must be provided.")
        
        metadata = arguments.get("metadata")
        metadata_str = None
        if metadata:
            metadata_str = json.dumps(metadata, ensure_ascii = False)
        
        memory_type = arguments.get("memory_type")
        memory_prompt = arguments.get("prompt")
        if not memory_type:
            memory_type = None
        if not memory_prompt:
            memory_prompt = None


        wrapped_sql = """
        SELECT adbpg_llm_memory.add(
            %s::json,
            %s::text,
            %s::text,
            %s::text,
            %s::json,
            %s::text,
            %s::text
        )
        """
        params = [messages_str, user_id, run_id, agent_id, metadata_str, memory_type, memory_prompt]
        return get_llm_memory_tool_result(wrapped_sql, params)
        
    elif name == "adbpg_llm_memory_get_all":
        # LLMEMORY 服务初始化失败，工具不可用
        if LLMEMORY_ENV_IS_READY == False:
            raise ValueError("LLMEMORY Server initialization failed. This tool cannot be used.") 
        
        user_id = arguments.get("user_id")
        if not user_id:
            user_id = None
        run_id = arguments.get("run_id")
        if not run_id:
            run_id = None
        agent_id = arguments.get("agent_id")
        if not agent_id:
            agent_id = None
        if user_id == None and run_id == None and agent_id == None:
            raise ValueError("At least one of user_id, run_id, or agent_id must be provided.")
        wrapped_sql = f"""
                SELECT adbpg_llm_memory.get_all(
                    %s::text,
                    %s::text,
                    %s::text
                )
            """
        params = [user_id, run_id, agent_id]
        return get_llm_memory_tool_result(wrapped_sql, params)
        

    elif name == "adbpg_llm_memory_search":
        # LLMEMORY 服务初始化失败，工具不可用
        if LLMEMORY_ENV_IS_READY == False:
            raise ValueError("LLMEMORY Server initialization failed. This tool cannot be used.") 
        query = arguments.get("query")
        if not query:
            raise ValueError("Query is required")
        
        user_id = arguments.get("user_id")
        if not user_id:
            user_id = None
        run_id = arguments.get("run_id")
        if not run_id:
            run_id = None
        agent_id = arguments.get("agent_id")
        if not agent_id:
            agent_id = None
        if user_id == None and run_id == None and agent_id == None:
            raise ValueError("At least one of user_id, run_id, or agent_id must be provided.")
        
        filter_json = arguments.get("filter")
        filter_json_str = None
        # json格式载入
        if filter_json:
            filter_json_str = json.dumps(filter_json, ensure_ascii = False)
        # 拼接命令
        wrapped_sql = f"""
                SELECT adbpg_llm_memory.search(
                    %s::text,
                    %s::text,
                    %s::text,
                    %s::text,
                    %s::json
                )
            """
        params = [query, user_id, run_id, agent_id, filter_json_str]
        return get_llm_memory_tool_result(wrapped_sql, params)

    elif name == "adbpg_llm_memory_delete_all":
        # LLMEMORY 服务初始化失败，工具不可用
        if LLMEMORY_ENV_IS_READY == False:
            raise ValueError("LLMEMORY Server initialization failed. This tool cannot be used.") 
        
        user_id = arguments.get("user_id")
        if not user_id:
            user_id = None
        run_id = arguments.get("run_id")
        if not run_id:
            run_id = None
        agent_id = arguments.get("agent_id")
        if not agent_id:
            agent_id = None
        if user_id == None and run_id == None and agent_id == None:
            raise ValueError("At least one of user_id, run_id, or agent_id must be provided.")

        wrapped_sql = f"""
                SELECT adbpg_llm_memory.delete_all(
                    %s::text,
                    %s::text,
                    %s::text
                )
            """
        params = [user_id, run_id, agent_id]
        return get_llm_memory_tool_result(wrapped_sql, params)

    else:
        raise ValueError(f"Unknown tool: {name}")
    
    try:
        with psycopg.connect(**config) as conn:
            conn.autocommit = True
            with conn.cursor() as cursor:
                
                cursor.execute(query)
                
                if name == "analyze_table":
                    return [TextContent(type="text", text=f"Successfully analyzed table {schema}.{table}")]

                if cursor.description:
                    # 将返回结果存储为json格式
                    json_result = cursor.fetchone()[0]
                    json_str = json.dumps(json_result, ensure_ascii = False, indent = 2)
                    result = [TextContent(type="text", text=json_str)]
                    try:
                        json.loads(result[0].text)
                    except json.JSONDecodeError as e:
                        raise Exception(f"JSON decode error: {e}\nRaw text: {result[0].text}") from e
                    return result

                else:
                    return [TextContent(type="text", text="Query executed successfully")]
    except Exception as e:
        return [TextContent(type="text", text=f"Error executing query: {str(e)}")]

async def main():
    """服务器主入口点"""
    try:
        config = get_db_config()
        logger.info("Starting ADBPG MCP server...")
        
        # 测试数据库连接
        try:
            with psycopg.connect(**config) as conn:
                logger.info("Successfully connected to database")
        except Exception as e:
            logger.error(f"Failed to connect to database: {e}")
            sys.exit(1)     
        # 使用 stdio 传输
        async with stdio_server() as (read_stream, write_stream):
            try:
                logger.info("Running MCP server with stdio transport...")
                await app.run(
                    read_stream=read_stream,
                    write_stream=write_stream,
                    initialization_options=app.create_initialization_options()
                )
            except Exception as e:
                logger.error(f"Error running server: {str(e)}")
                raise
    except Exception as e:
        logger.error(f"Server initialization error: {str(e)}")
        raise

def run():
    """同步运行入口点"""
    try:
        asyncio.run(main())
    except Exception as e:
        logger.error(f"Fatal error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    run() 