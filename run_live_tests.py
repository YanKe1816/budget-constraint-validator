import json
import os
import subprocess
import sys
import time
from urllib.error import HTTPError
from urllib.request import Request, urlopen


PORT = 8765
BASE_URL = f"http://127.0.0.1:{PORT}"


def http_get(path):
    request = Request(f"{BASE_URL}{path}", method="GET")
    with urlopen(request, timeout=5) as response:
        return response.status, response.read().decode("utf-8"), dict(response.headers)


def http_post_json(path, payload):
    body = json.dumps(payload).encode("utf-8")
    request = Request(
        f"{BASE_URL}{path}",
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urlopen(request, timeout=5) as response:
        return response.status, json.loads(response.read().decode("utf-8"))


def get_jsonrpc_result(method, params, request_id):
    status, payload = http_post_json(
        "/mcp",
        {
            "jsonrpc": "2.0",
            "id": request_id,
            "method": method,
            "params": params,
        },
    )
    assert status == 200
    return payload


def assert_output_matches_schema(output):
    assert isinstance(output, dict)
    assert set(output.keys()) == {
        "is_valid",
        "total_budget",
        "total_allocated",
        "remaining",
        "overflow",
        "status",
        "error",
    }
    assert isinstance(output["is_valid"], bool)
    assert isinstance(output["total_budget"], (int, float)) and not isinstance(
        output["total_budget"], bool
    )
    assert isinstance(output["total_allocated"], (int, float)) and not isinstance(
        output["total_allocated"], bool
    )
    assert isinstance(output["remaining"], (int, float)) and not isinstance(
        output["remaining"], bool
    )
    assert isinstance(output["overflow"], (int, float)) and not isinstance(
        output["overflow"], bool
    )
    assert output["status"] in {"valid", "over_budget", "error"}
    if output["error"] is None:
        return
    assert isinstance(output["error"], dict)
    assert set(output["error"].keys()) == {"code", "message"}
    assert output["error"]["code"] in {
        "missing_field",
        "invalid_value",
        "out_of_scope",
        "internal_error",
    }
    assert isinstance(output["error"]["message"], str)


def extract_structured_content(tool_response):
    result = tool_response["result"]
    assert result["isError"] == (result["structuredContent"]["status"] == "error")
    assert len(result["content"]) == 1
    assert json.loads(result["content"][0]["text"]) == result["structuredContent"]
    return result["structuredContent"]


def main():
    env = os.environ.copy()
    env["PORT"] = str(PORT)
    env["OPENAI_APPS_CHALLENGE"] = "test-challenge-token"
    server_process = subprocess.Popen(
        [sys.executable, "server.py"],
        cwd=os.path.dirname(os.path.abspath(__file__)),
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )

    try:
        time.sleep(1.0)
        if server_process.poll() is not None:
            stdout, stderr = server_process.communicate(timeout=2)
            raise AssertionError(
                f"Server exited early.\nSTDOUT:\n{stdout}\nSTDERR:\n{stderr}"
            )

        root_status, root_body, root_headers = http_get("/")
        assert root_status == 200
        assert "Budget Constraint Validator" in root_body
        assert (
            "Validates explicitly provided budget allocations against a total budget."
            in root_body
        )
        assert "POST /mcp" in root_body
        assert "/privacy" in root_body
        assert "/terms" in root_body
        assert "/support" in root_body
        assert "/health" in root_body
        assert "text/html" in root_headers.get("Content-Type", "")

        privacy_status, privacy_body, privacy_headers = http_get("/privacy")
        assert privacy_status == 200
        assert "text/html" in privacy_headers.get("Content-Type", "")
        assert "does not require login" in privacy_body
        assert "does not access external APIs" in privacy_body
        assert "sidcraigau@gmail.com" in privacy_body

        terms_status, terms_body, terms_headers = http_get("/terms")
        assert terms_status == 200
        assert "text/html" in terms_headers.get("Content-Type", "")
        assert "is not a financial advisor" in terms_body
        assert "budget optimization" in terms_body
        assert "sidcraigau@gmail.com" in terms_body

        support_status, support_body, support_headers = http_get("/support")
        assert support_status == 200
        assert "text/html" in support_headers.get("Content-Type", "")
        assert "Problems connecting to the MCP endpoint" in support_body
        assert "sidcraigau@gmail.com" in support_body

        health_status, health_body, health_headers = http_get("/health")
        assert health_status == 200
        assert "text/html" in health_headers.get("Content-Type", "")
        assert "Service status: OK" in health_body
        assert "POST /mcp" in health_body

        health_json_status, health_json_body, _ = http_get("/health.json")
        assert health_json_status == 200
        assert json.loads(health_json_body) == {
            "status": "ok",
            "app": "Budget Constraint Validator",
        }

        challenge_status, challenge_body, challenge_headers = http_get(
            "/.well-known/openai-apps-challenge"
        )
        assert challenge_status == 200
        assert "text/plain" in challenge_headers.get("Content-Type", "")
        assert challenge_body == "test-challenge-token"

        initialize_response = get_jsonrpc_result("initialize", {}, 1)
        assert initialize_response == {
            "jsonrpc": "2.0",
            "id": 1,
            "result": {
                "protocolVersion": "2024-11-05",
                "serverInfo": {
                    "name": "budget-constraint-validator-mcp",
                    "version": "0.1.0",
                },
                "capabilities": {"tools": {}},
            },
        }

        tools_list_response = get_jsonrpc_result("tools/list", {}, 2)
        tools = tools_list_response["result"]["tools"]
        assert len(tools) == 1
        tool = tools[0]
        assert tool["name"] == "validate_budget_constraint"
        assert tool["title"] == "Validate Budget Constraint"
        assert (
            tool["description"]
            == "Use this tool only to validate whether explicitly provided budget allocation amounts exceed an explicitly provided total budget. The user must provide a total_budget and specific allocation items with numeric amounts. Do not call this tool if the user asks for budget advice, recommendations, optimization, whether they should spend money, how to split a budget, whether one option is better than another, or if allocation amounts are missing. Do not infer, estimate, recommend, or invent allocation amounts. This tool only performs deterministic math validation on provided numbers."
        )
        assert "inputSchema" in tool
        assert "outputSchema" in tool
        assert tool["annotations"] == {
            "readOnlyHint": True,
            "destructiveHint": False,
            "idempotentHint": True,
            "openWorldHint": False,
        }

        case_1 = extract_structured_content(
            get_jsonrpc_result(
                "tools/call",
                {
                    "name": "validate_budget_constraint",
                    "arguments": {
                        "total_budget": 10000,
                        "allocations": [
                            {"name": "A", "amount": 3000},
                            {"name": "B", "amount": 7000},
                        ],
                    },
                },
                3,
            )
        )
        assert case_1 == {
            "is_valid": True,
            "total_budget": 10000,
            "total_allocated": 10000,
            "remaining": 0,
            "overflow": 0,
            "status": "valid",
            "error": None,
        }

        case_2 = extract_structured_content(
            get_jsonrpc_result(
                "tools/call",
                {
                    "name": "validate_budget_constraint",
                    "arguments": {
                        "total_budget": 10000,
                        "allocations": [
                            {"name": "Marketing", "amount": 2500},
                            {"name": "Operations", "amount": 4000},
                        ],
                    },
                },
                4,
            )
        )
        assert case_2 == {
            "is_valid": True,
            "total_budget": 10000,
            "total_allocated": 6500,
            "remaining": 3500,
            "overflow": 0,
            "status": "valid",
            "error": None,
        }

        case_3 = extract_structured_content(
            get_jsonrpc_result(
                "tools/call",
                {
                    "name": "validate_budget_constraint",
                    "arguments": {
                        "total_budget": 10000,
                        "allocations": [
                            {"name": "A", "amount": 6000},
                            {"name": "B", "amount": 7000},
                        ],
                    },
                },
                5,
            )
        )
        assert case_3 == {
            "is_valid": False,
            "total_budget": 10000,
            "total_allocated": 13000,
            "remaining": 0,
            "overflow": 3000,
            "status": "over_budget",
            "error": None,
        }

        case_4 = extract_structured_content(
            get_jsonrpc_result(
                "tools/call",
                {
                    "name": "validate_budget_constraint",
                    "arguments": {
                        "allocations": [{"name": "A", "amount": 1000}],
                    },
                },
                6,
            )
        )
        assert case_4["status"] == "error"
        assert case_4["error"]["code"] == "missing_field"

        case_5 = extract_structured_content(
            get_jsonrpc_result(
                "tools/call",
                {
                    "name": "validate_budget_constraint",
                    "arguments": {
                        "total_budget": 10000,
                        "allocations": [{"name": "A", "amount": -1}],
                    },
                },
                7,
            )
        )
        assert case_5["status"] == "error"
        assert case_5["error"]["code"] == "invalid_value"

        repeated_request = {
            "name": "validate_budget_constraint",
            "arguments": {
                "total_budget": 10000,
                "allocations": [
                    {"name": "A", "amount": 6000},
                    {"name": "B", "amount": 7000},
                ],
            },
        }
        repeated_outputs = [
            get_jsonrpc_result("tools/call", repeated_request, 8 + index)
            for index in range(3)
        ]
        normalized = []
        for item in repeated_outputs:
            structured = extract_structured_content(item)
            assert_output_matches_schema(structured)
            normalized.append(json.dumps(structured, sort_keys=True, separators=(",", ":")))
        assert normalized[0] == normalized[1] == normalized[2]

        for output in (case_1, case_2, case_3, case_4, case_5):
            assert_output_matches_schema(output)

        negative_advice_case = extract_structured_content(
            get_jsonrpc_result(
                "tools/call",
                {
                    "name": "validate_budget_constraint",
                    "arguments": {
                        "total_budget": 10000,
                        "allocations": [],
                        "question": "Should I spend this 10000 budget on marketing or product development?",
                    },
                },
                11,
            )
        )
        assert negative_advice_case["status"] == "error"
        assert negative_advice_case["error"]["code"] == "out_of_scope"
        assert_output_matches_schema(negative_advice_case)

        try:
            urlopen(Request(f"{BASE_URL}/mcp", method="GET"), timeout=5)
            raise AssertionError("GET /mcp should not succeed.")
        except HTTPError as error:
            assert error.code == 405

        print(
            json.dumps(
                {
                    "server_started": True,
                    "get_root": True,
                    "get_privacy": True,
                    "get_terms": True,
                    "get_support": True,
                    "get_health": True,
                    "get_health_json": True,
                    "get_challenge": True,
                    "initialize": True,
                    "tools_list": True,
                    "case_1": True,
                    "case_2": True,
                    "case_3": True,
                    "case_4": True,
                    "case_5": True,
                    "repeat_stability": True,
                    "negative_advice_guard": True,
                    "output_schema_match": True,
                    "get_mcp_post_only": True,
                },
                indent=2,
            )
        )
    finally:
        server_process.terminate()
        try:
            server_process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            server_process.kill()
            server_process.wait(timeout=5)


if __name__ == "__main__":
    main()
