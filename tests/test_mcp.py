import pytest


@pytest.mark.skip(reason="fastmcp not installed")
def test_mcp_server_imports():
    from backend.mcp_server import mcp

    assert mcp is not None


@pytest.mark.skip(reason="fastmcp not installed")
@pytest.mark.asyncio
async def test_mcp_tools_exist():
    from backend.mcp_server import mcp

    tool_names = [t.name for t in mcp._tool_manager.tools]
    assert "list_accounts" in tool_names
    assert "search_emails" in tool_names
    assert "get_email" in tool_names
    assert "get_recent_emails" in tool_names
