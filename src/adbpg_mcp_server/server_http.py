import requests
import logging
import json
import hmac
import click
import contextlib
import uvicorn
import sys
import os
import mcp.types as types
from pydantic import AnyUrl
from collections.abc import AsyncIterator
from mcp.server.lowlevel import Server
from mcp.server.streamable_http_manager import StreamableHTTPSessionManager
from mcp.types import Resource, Tool, TextContent, ResourceTemplate
from starlette.applications import Starlette
from starlette.routing import Mount
from starlette.responses import JSONResponse
from starlette.middleware import Middleware
from starlette.middleware.base import BaseHTTPMiddleware
from .adbpg import DatabaseManager
from . import adbpg_basic_operation, adbpg_graphrag, adbpg_memory
from .adbpg_config import settings


class BearerAuthMiddleware(BaseHTTPMiddleware):
    """Validates Bearer token on all requests when MCP_AUTH_TOKEN is set."""

    def __init__(self, app, token: str):
        super().__init__(app)
        self.token = token

    async def dispatch(self, request, call_next):
        auth_header = request.headers.get("Authorization", "")
        if not auth_header.startswith("Bearer ") or not hmac.compare_digest(auth_header[7:], self.token):
            return JSONResponse({"error": "Unauthorized"}, status_code=401)
        return await call_next(request)


db_manager: DatabaseManager | None = None
graphrag_is_available = False
llm_memory_is_available = False

logging.basicConfig(
        level=logging.DEBUG,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )
logger = logging.getLogger("ADBPG MCP Server")

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



def run_http_server(host, port, auth_token=None):

    auth_token = auth_token or os.getenv("MCP_AUTH_TOKEN")
    if not auth_token:
        logger.warning(
            "No authentication token configured. Set MCP_AUTH_TOKEN or use --auth-token "
            "to protect the HTTP endpoint."
        )

    # 创建MCP服务端
    app = Server("adbpg-mcp-server")
    initialize_services()
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

    # 工具调用
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

    # 工具列表
    @app.list_tools()
    async def list_tools() -> list[Tool]:
        """
        列出可用的工具
        """
        tools = adbpg_basic_operation.get_basic_tools()

        if graphrag_is_available:
            tools.extend(adbpg_graphrag.get_graphrag_tools())
        if llm_memory_is_available:
            tools.extend(adbpg_memory.get_memory_tools())
        return tools
        
    #----------管理请求会话--------------
    session_manager = StreamableHTTPSessionManager(
        app=app,
        event_store=None, #无状态，不保存历史事件
        stateless=True
    )
    async def handle_streamable_http(scope, receive, send):
        await session_manager.handle_request(scope, receive, send)

    @contextlib.asynccontextmanager
    async def lifespan(app):
        async with session_manager.run():
            logger.info("ADBPG MCP Server Started! ")
            try:
                yield
            finally:
                logger.info("ADBPG MCP Server shutting down…")
    
    # 将MCP服务挂载到/mcp路径上，用户访问整个路径时，就会进入刚才创建的MCP HTTP会话管理器
    middleware = []
    if auth_token:
        middleware.append(Middleware(BearerAuthMiddleware, token=auth_token))

    starlette_app = Starlette(
        debug=False,
        routes=[Mount("/mcp", app=handle_streamable_http)],
        lifespan=lifespan,
        middleware=middleware,
    )

    # 利用uvicorn启动ASGI服务器并监听指定端口
    uvicorn.run(starlette_app, host=host, port=port)

    return 0
