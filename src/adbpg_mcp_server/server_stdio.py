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

SERVER_VERSION = "0.2.0"

from .adbpg_config import settings
from .adbpg import DatabaseManager
from . import adbpg_basic_operation, adbpg_graphrag, adbpg_memory


# 初始化服务器
try:
    app = Server("adbpg-mcp-server")
    logger.info("MCP server initialized")
except Exception as e:
    logger.error(f"Error initializing MCP server: {e}")
    sys.exit(1)
db_manager: DatabaseManager | None = None
graphrag_is_available = False
llm_memory_is_available = False

@app.list_resources()
async def list_resources() -> list[Resource]:
    """列出可用的基本资源"""
    return await adbpg_basic_operation.list_resources()

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
    return await adbpg_basic_operation.list_resource_templates()


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
    if not db_manager:
        raise Exception("Database connection not established")
    return await adbpg_basic_operation.read_resource(uri, db_manager)

@app.list_tools()
async def list_tools() -> list[Tool]:
    """
    列出可用的工具
    """
    tools = adbpg_basic_operation.get_basic_tools()
    #tools.extend(adbpg_graphrag.get_graphrag_tools())
    #tools.extend(adbpg_memory.get_memory_tools())

    if graphrag_is_available:
        tools.extend(adbpg_graphrag.get_graphrag_tools())
    if llm_memory_is_available:
        tools.extend(adbpg_memory.get_memory_tools())
    return tools
@app.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:
    """
    执行工具操作

    参数:
        name (str): 工具名称
        arguments (dict): 工具参数

    返回:
        list[TextContent]: 执行结果
    """
    if not db_manager:
        raise Exception("Database manager not initialized")
    
    try:
        # 分发到 Basic Operation
        if name in [t.name for t in adbpg_basic_operation.get_basic_tools()]:
            query, params, fetch_mode = await adbpg_basic_operation.call_basic_tool(name, arguments, db_manager)
            conn = db_manager.get_basic_connection()
            with conn.cursor() as cursor:
                cursor.execute(query, params)
                if fetch_mode == "select":
                    columns = [desc[0] for desc in cursor.description]
                    rows = cursor.fetchall()
                    json_result = [dict(zip(columns, row)) for row in rows]
                    return [TextContent(type="text", text=json.dumps(json_result, ensure_ascii=False, indent=2, default=str))]
                elif fetch_mode == "json":
                    json_result = cursor.fetchone()[0]
                    return [TextContent(type="text", text=json.dumps(json_result, ensure_ascii=False, indent=2, default=str))]
                else:
                    return [TextContent(type="text", text="Tool executed successfully.")]

        # 分发到 GraphRAG
        elif name in [t.name for t in adbpg_graphrag.get_graphrag_tools()]:
            if not graphrag_is_available:
                raise ValueError("GraphRAG tool is not available due to configuration or initialization errors.")
            return await adbpg_graphrag.call_graphrag_tool(name, arguments, db_manager)

        # 分发到 LLM Memory
        elif name in [t.name for t in adbpg_memory.get_memory_tools()]:
            if not llm_memory_is_available:
                raise ValueError("LLM Memory tool is not available due to configuration or initialization errors.")
            return await adbpg_memory.call_memory_tool(name, arguments, db_manager)

        else:
            raise ValueError(f"Unknown tool: {name}")

    except Exception as e:
        logger.error(f"Error calling tool '{name}': {e}", exc_info=True)
        return [TextContent(type="text", text=f"Error executing tool '{name}': {str(e)}")]

# --- 服务器生命周期 ---
def initialize_services():
    """初始化数据库、GraphRAG 和 LLM Memory"""
    global db_manager, graphrag_is_available, llm_memory_is_available

    if not settings.db_env_ready:
        logger.error("Cannot start server: Database environment is not configured.")
        sys.exit(1)

    db_manager = DatabaseManager(settings)

    # 测试主连接
    try:
        db_manager.get_basic_connection()
        logger.info("Successfully connected to database.")
    except Exception as e:
        logger.error(f"Failed to connect to database: {e}")
        sys.exit(1)

    # 初始化 GraphRAG
    if settings.graphrag_env_ready:
        try:
            db_manager.get_graphrag_connection()
            graphrag_is_available = True
            logger.info("GraphRAG initialized successfully.")
        except Exception as e:
            logger.error(f"Failed to initialize GraphRAG: {e}")
            graphrag_is_available = False
            
    # 初始化 LLM Memory
    if settings.memory_env_ready:
        try:
            db_manager.get_llm_memory_connection()
            llm_memory_is_available = True
            logger.info("LLM Memory initialized successfully.")
        except Exception as e:
            logger.error(f"Failed to initialize LLM Memory: {e}")
            llm_memory_is_available = False

async def main():
    """服务器主入口点"""
    try:
        initialize_services()
        logger.info("Starting ADBPG MCP server...")
        
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

    finally:
        if db_manager:
            db_manager.close_all()

def run_stdio_server():
    """同步运行入口点"""
    try:
        asyncio.run(main())
    except Exception as e:
        logger.error(f"Fatal error: {e}")
        sys.exit(1)
