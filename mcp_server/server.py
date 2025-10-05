"""MCP Server for Chat PDF"""
import asyncio
import json
from typing import Any
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent
import httpx
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# API base URL (adjust as needed)
API_BASE_URL = "http://localhost:8000/api"

# Create MCP server
server = Server("chat-pdf-mcp")


@server.list_tools()
async def list_tools() -> list[Tool]:
    """List available tools"""
    return [
        Tool(
            name="list_docs",
            description="List all documents for the authenticated user. Returns document metadata including ID, filename, status, and page count.",
            inputSchema={
                "type": "object",
                "properties": {
                    "user_id": {
                        "type": "string",
                        "description": "User ID (UUID format)"
                    },
                    "status": {
                        "type": "string",
                        "description": "Filter by status: pending, processing, ready, failed, or all",
                        "enum": ["pending", "processing", "ready", "failed", "all"]
                    }
                },
                "required": ["user_id"]
            }
        ),
        Tool(
            name="add_doc",
            description="Upload a new PDF document from a file path. The document will be processed asynchronously.",
            inputSchema={
                "type": "object",
                "properties": {
                    "user_id": {
                        "type": "string",
                        "description": "User ID (UUID format)"
                    },
                    "file_path": {
                        "type": "string",
                        "description": "Path to the PDF file to upload"
                    }
                },
                "required": ["user_id", "file_path"]
            }
        ),
        Tool(
            name="chat_with_docs",
            description="Ask a question grounded in selected documents. Returns an answer with citations from the documents.",
            inputSchema={
                "type": "object",
                "properties": {
                    "user_id": {
                        "type": "string",
                        "description": "User ID (UUID format)"
                    },
                    "question": {
                        "type": "string",
                        "description": "The question to ask"
                    },
                    "doc_ids": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "List of document IDs to search (UUIDs)"
                    },
                    "conversation_id": {
                        "type": "string",
                        "description": "Optional conversation ID to continue an existing conversation"
                    }
                },
                "required": ["user_id", "question", "doc_ids"]
            }
        )
    ]


@server.call_tool()
async def call_tool(name: str, arguments: Any) -> list[TextContent]:
    """Handle tool calls"""
    try:
        if name == "list_docs":
            return await handle_list_docs(arguments)
        elif name == "add_doc":
            return await handle_add_doc(arguments)
        elif name == "chat_with_docs":
            return await handle_chat_with_docs(arguments)
        else:
            return [TextContent(
                type="text",
                text=f"Unknown tool: {name}"
            )]
    except Exception as e:
        logger.error(f"Error calling tool {name}: {str(e)}", exc_info=True)
        return [TextContent(
            type="text",
            text=f"Error: {str(e)}"
        )]


async def handle_list_docs(arguments: dict) -> list[TextContent]:
    """Handle list_docs tool call"""
    user_id = arguments.get("user_id")
    status = arguments.get("status")

    params = {"user_id": user_id}
    if status and status != "all":
        params["status"] = status

    async with httpx.AsyncClient() as client:
        response = await client.get(f"{API_BASE_URL}/documents", params=params)
        response.raise_for_status()
        data = response.json()

    # Format the response
    documents = data.get("documents", [])
    if not documents:
        return [TextContent(
            type="text",
            text="No documents found."
        )]

    result_text = f"Found {len(documents)} document(s):\n\n"
    for doc in documents:
        result_text += f"• ID: {doc['id']}\n"
        result_text += f"  Filename: {doc['filename']}\n"
        result_text += f"  Status: {doc['status']}\n"
        result_text += f"  Pages: {doc.get('page_count', 'N/A')}\n"
        result_text += f"  Created: {doc['created_at']}\n\n"

    return [TextContent(type="text", text=result_text)]


async def handle_add_doc(arguments: dict) -> list[TextContent]:
    """Handle add_doc tool call"""
    user_id = arguments.get("user_id")
    file_path = arguments.get("file_path")

    # Read the file
    try:
        with open(file_path, "rb") as f:
            file_content = f.read()
    except FileNotFoundError:
        return [TextContent(
            type="text",
            text=f"Error: File not found: {file_path}"
        )]

    # Get filename from path
    import os
    filename = os.path.basename(file_path)

    # Upload the file
    async with httpx.AsyncClient(timeout=60.0) as client:
        files = {"file": (filename, file_content, "application/pdf")}
        data = {"user_id": user_id}

        response = await client.post(
            f"{API_BASE_URL}/upload",
            files=files,
            data=data
        )
        response.raise_for_status()
        result = response.json()

    result_text = f"Document uploaded successfully!\n\n"
    result_text += f"Document ID: {result['doc_id']}\n"
    result_text += f"Filename: {result['filename']}\n"
    result_text += f"Status: {result['status']}\n"
    result_text += f"Message: {result['message']}\n"

    return [TextContent(type="text", text=result_text)]


async def handle_chat_with_docs(arguments: dict) -> list[TextContent]:
    """Handle chat_with_docs tool call"""
    user_id = arguments.get("user_id")
    question = arguments.get("question")
    doc_ids = arguments.get("doc_ids")
    conversation_id = arguments.get("conversation_id")

    payload = {
        "question": question,
        "doc_ids": doc_ids
    }
    if conversation_id:
        payload["conversation_id"] = conversation_id

    async with httpx.AsyncClient(timeout=60.0) as client:
        response = await client.post(f"{API_BASE_URL}/chat", json=payload)
        response.raise_for_status()
        data = response.json()

    # Format the response
    answer = data.get("answer", "")
    citations = data.get("citations", [])
    token_usage = data.get("token_usage", {})

    result_text = f"{answer}\n\n"

    if citations:
        result_text += "---\nSources:\n"
        for i, citation in enumerate(citations, 1):
            result_text += f"\n{i}. {citation['filename']}"
            if citation.get('page_start'):
                if citation.get('page_end') and citation['page_end'] != citation['page_start']:
                    result_text += f" (Pages {citation['page_start']}-{citation['page_end']})"
                else:
                    result_text += f" (Page {citation['page_start']})"
            result_text += f"\n   \"{citation['snippet']}\"\n"

    if token_usage:
        result_text += f"\n---\nTokens used: {token_usage.get('total_tokens', 0)} "
        result_text += f"(prompt: {token_usage.get('prompt_tokens', 0)}, "
        result_text += f"completion: {token_usage.get('completion_tokens', 0)})"

    return [TextContent(type="text", text=result_text)]


async def main():
    """Run the MCP server"""
    logger.info("Starting Chat PDF MCP server...")
    async with stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream,
            server.create_initialization_options()
        )


if __name__ == "__main__":
    asyncio.run(main())
