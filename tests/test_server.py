import server


def test_mcp_initialize_and_tool_discovery():
    initialized = server.handle_request({"jsonrpc": "2.0", "id": 1, "method": "initialize"})
    assert initialized["result"]["serverInfo"]["version"] == "2.0.0"

    listed = server.handle_request({"jsonrpc": "2.0", "id": 2, "method": "tools/list"})
    names = {tool["name"] for tool in listed["result"]["tools"]}
    assert "moa_orchestrate" in names


def test_initialized_notification_has_no_response():
    assert server.handle_request({"jsonrpc": "2.0", "method": "notifications/initialized"}) is None
