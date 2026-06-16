import argparse
import sys

from .server_http import run_http_server
from .server_stdio import run_stdio_server

def main():
    """
    通过参数选择使用 stdio 或 http 服务器
    """
    parser = argparse.ArgumentParser(
        description="ADBPG Management & Control Plane MCP Server"
    )
    parser.add_argument(
        "--transport",
        choices = ["stdio", "http"],
        default = "stdio",
        help = "Transport protocol to use (stdio or streamable-http)"
    )
    http_group = parser.add_argument_group("HTTP Server Options")
    http_group.add_argument(
        "--host",
        default="127.0.0.1",
        help = "Host to bind the HTTP server to (default: 127.0.0.1)."
    )
    http_group.add_argument(
        "--port",
        type = int,
        default = 3000,
        help = "Port to bind the HTTP server to (default: 3000)."
    )
    http_group.add_argument(
        "--auth-token",
        default = None,
        help = "Bearer token for HTTP endpoint authentication. Can also be set via MCP_AUTH_TOKEN env var."
    )

    args = parser.parse_args()
    print(f"Starting ADBPG MCP Server with transport {args.transport}")

    if args.transport == "http":
        run_http_server(host=args.host, port=args.port, auth_token=args.auth_token)
    elif args.transport == "stdio":
        run_stdio_server()
    else:
        raise ValueError(f"Invalid transport: {args.transport}")

if __name__ == "__main__":
    main()

