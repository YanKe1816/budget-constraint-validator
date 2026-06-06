import json
import os
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer


JSONRPC_VERSION = "2.0"
PROTOCOL_VERSION = "2024-11-05"
APP_NAME = "Budget Constraint Validator"
SUPPORT_EMAIL = "sidcraigau@gmail.com"
EFFECTIVE_DATE = "2026-06-06"
SERVER_INFO = {
    "name": "budget-constraint-validator-mcp",
    "version": "0.1.0",
}
TOOL_NAME = "validate_budget_constraint"
TOOL_TITLE = "Validate Budget Constraint"
APP_DESCRIPTION = (
    "Validates explicitly provided budget allocations against a total budget. "
    "It does not recommend how to spend, split, optimize, or judge a budget."
)
TOOL_DESCRIPTION = (
    "Use this tool only to validate whether explicitly provided budget allocation "
    "amounts exceed an explicitly provided total budget. The user must provide a "
    "total_budget and specific allocation items with numeric amounts. Do not call "
    "this tool if the user asks for budget advice, recommendations, optimization, "
    "whether they should spend money, how to split a budget, whether one option is "
    "better than another, or if allocation amounts are missing. Do not infer, "
    "estimate, recommend, or invent allocation amounts. This tool only performs "
    "deterministic math validation on provided numbers."
)
TOOL_INPUT_SCHEMA = {
    "type": "object",
    "properties": {
        "total_budget": {
            "type": "number",
            "minimum": 0,
        },
        "allocations": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "amount": {"type": "number", "minimum": 0},
                },
                "required": ["name", "amount"],
                "additionalProperties": False,
            },
        },
    },
    "required": ["total_budget", "allocations"],
    "additionalProperties": False,
}
TOOL_OUTPUT_SCHEMA = {
    "type": "object",
    "properties": {
        "is_valid": {"type": "boolean"},
        "total_budget": {"type": "number"},
        "total_allocated": {"type": "number"},
        "remaining": {"type": "number"},
        "overflow": {"type": "number"},
        "status": {"type": "string", "enum": ["valid", "over_budget", "error"]},
        "error": {
            "anyOf": [
                {"type": "null"},
                {
                    "type": "object",
                    "properties": {
                        "code": {
                            "type": "string",
                            "enum": [
                                "missing_field",
                                "invalid_value",
                                "out_of_scope",
                                "internal_error",
                            ],
                        },
                        "message": {"type": "string"},
                    },
                    "required": ["code", "message"],
                    "additionalProperties": False,
                },
            ]
        },
    },
    "required": [
        "is_valid",
        "total_budget",
        "total_allocated",
        "remaining",
        "overflow",
        "status",
        "error",
    ],
    "additionalProperties": False,
}
TOOL_ANNOTATIONS = {
    "readOnlyHint": True,
    "destructiveHint": False,
    "idempotentHint": True,
    "openWorldHint": False,
}


def html_page(title, body_html):
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{title}</title>
  <style>
    :root {{
      --bg: #f3efe7;
      --panel: #fffdf8;
      --text: #1f2933;
      --muted: #52606d;
      --accent: #2d6a4f;
      --border: #d7d2c8;
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      background:
        radial-gradient(circle at top right, #e4f6ec 0%, transparent 25%),
        linear-gradient(180deg, #f8f4ed 0%, var(--bg) 100%);
      color: var(--text);
      font-family: Georgia, "Times New Roman", serif;
    }}
    main {{
      max-width: 860px;
      margin: 0 auto;
      padding: 40px 20px 72px;
    }}
    .panel {{
      background: var(--panel);
      border: 1px solid var(--border);
      border-radius: 18px;
      padding: 32px;
      box-shadow: 0 12px 28px rgba(31, 41, 51, 0.08);
    }}
    h1, h2 {{ margin-top: 0; line-height: 1.2; }}
    p, li {{ color: var(--muted); line-height: 1.6; }}
    ul {{ padding-left: 1.2rem; }}
    code {{
      background: #edf6f1;
      border-radius: 4px;
      padding: 0.1rem 0.35rem;
    }}
    .eyebrow {{
      color: var(--accent);
      text-transform: uppercase;
      letter-spacing: 0.08em;
      font-size: 0.8rem;
      margin-bottom: 12px;
    }}
    .status {{
      display: inline-block;
      margin: 10px 0 18px;
      padding: 8px 12px;
      border-radius: 999px;
      background: #e6f4ea;
      color: #24543d;
      font-weight: 700;
    }}
    nav {{
      display: flex;
      flex-wrap: wrap;
      gap: 16px;
      margin-top: 28px;
      padding-top: 20px;
      border-top: 1px solid var(--border);
    }}
    a {{ color: var(--accent); }}
  </style>
</head>
<body>
  <main>
    <section class="panel">
      {body_html}
    </section>
  </main>
</body>
</html>"""


def nav_html(include_health_json=False):
    links = [
        '<a href="/">Home</a>',
        '<a href="/privacy">Privacy</a>',
        '<a href="/terms">Terms</a>',
        '<a href="/support">Support</a>',
        '<a href="/health">Health</a>',
    ]
    if include_health_json:
        links.append('<a href="/health.json">Health JSON</a>')
    return "<nav>" + "".join(links) + "</nav>"


def homepage_html():
    return html_page(
        APP_NAME,
        f"""
        <div class="eyebrow">{APP_NAME}</div>
        <h1>{APP_NAME}</h1>
        <p>{APP_DESCRIPTION}</p>
        <h2>What this app does</h2>
        <p>It performs deterministic budget math validation. Given a total budget and allocation amounts, it returns whether the allocations are within the budget, the total allocated amount, the remaining budget, and the overflow amount.</p>
        <h2>What this app does not do</h2>
        <p>This app does not provide financial advice, budget recommendations, investment advice, spending decisions, real money transfers, or budget optimization. It only validates numeric budget constraints.</p>
        <h2>How to use</h2>
        <p>Connect ChatGPT Developer Mode to the MCP endpoint at <code>POST /mcp</code>, scan the available tool, and call <code>{TOOL_NAME}</code> with a total budget and allocation list.</p>
        <h2>MCP endpoint</h2>
        <p><code>POST /mcp</code></p>
        <h2>Support</h2>
        <p><a href="mailto:{SUPPORT_EMAIL}">{SUPPORT_EMAIL}</a></p>
        {nav_html()}
        """,
    )


def privacy_html():
    return html_page(
        f"{APP_NAME} Privacy",
        f"""
        <div class="eyebrow">Privacy Policy</div>
        <h1>Privacy Policy for {APP_NAME}</h1>
        <p>Effective date / last updated: {EFFECTIVE_DATE}</p>
        <h2>1. Data Collected</h2>
        <p>{APP_NAME} processes only the data submitted by the user in the current request.</p>
        <p>The expected tool inputs are:</p>
        <ul>
          <li><code>total_budget</code>: a non-negative number representing the total available budget.</li>
          <li><code>allocations</code>: an array of allocation items.</li>
          <li><code>allocations[].name</code>: the name of an allocation item.</li>
          <li><code>allocations[].amount</code>: a non-negative number representing the allocation amount.</li>
        </ul>
        <p>The app does not collect data from external sources, does not scrape websites, and does not fetch additional data.</p>
        <p>The app does not access user accounts, files, databases, browsing history, contacts, calendars, emails, payment systems, bank accounts, or third-party services.</p>

        <h2>2. Tool Outputs</h2>
        <p>{APP_NAME} may return the following structured fields:</p>
        <ul>
          <li><code>is_valid</code>: whether the allocation is within the total budget.</li>
          <li><code>total_budget</code>: the total budget submitted by the user.</li>
          <li><code>total_allocated</code>: the sum of all allocation amounts.</li>
          <li><code>remaining</code>: the remaining budget amount when allocations are within the budget.</li>
          <li><code>overflow</code>: the amount by which allocations exceed the budget.</li>
          <li><code>status</code>: a status value such as valid, over_budget, or error.</li>
          <li><code>error</code>: an error object or null.</li>
        </ul>
        <p>These outputs are generated only from the user-provided input.</p>

        <h2>3. Purpose of Processing</h2>
        <p>The submitted data is used only to validate whether the provided allocation amounts exceed the provided total budget.</p>
        <p>The app performs deterministic arithmetic validation only.</p>
        <p>The app does not use submitted data for marketing, advertising, profiling, analytics-based targeting, model training by the app provider, budget recommendations, financial advice, investment advice, or unrelated purposes.</p>

        <h2>4. Recipients and Sharing</h2>
        <p>The app does not sell user data.</p>
        <p>The app does not intentionally share submitted inputs or generated outputs with third-party recipients.</p>
        <p>The app does not call external APIs.</p>
        <p>The app does not send data to downstream systems.</p>
        <p>The app does not contact banks, payment providers, customers, vendors, financial institutions, or other external parties.</p>
        <p>The app does not update tickets, orders, invoices, databases, calendars, email systems, payment systems, budgeting systems, accounting systems, or other external systems.</p>

        <h2>5. Retention</h2>
        <p>The app is designed to be stateless.</p>
        <p>The app does not store submitted inputs or generated outputs after request processing is complete, aside from transient platform-level request handling and logs needed to operate and debug the service.</p>
        <p>The app does not maintain persistent records of user budget inputs, allocation names, allocation amounts, validation results, or errors.</p>

        <h2>6. User Controls</h2>
        <p>Users control what they submit to the app.</p>
        <p>Users should avoid submitting sensitive, confidential, or unnecessary personal data.</p>
        <p>Users may remove or replace sensitive allocation names before submitting a request.</p>
        <p>Users may submit generic labels such as A, B, Marketing, Operations, or Tools instead of real internal budget labels.</p>
        <p>Privacy questions or deletion requests can be sent to the support email listed on the Support page: <a href="mailto:{SUPPORT_EMAIL}">{SUPPORT_EMAIL}</a>.</p>

        <h2>7. Login and Accounts</h2>
        <p>The app does not require user accounts, authentication, login credentials, or user registration.</p>

        <h2>8. Read-Only Operation and No Side Effects</h2>
        <p>The app is read-only.</p>
        <p>The app does not modify records, send messages, make decisions on behalf of users, contact external parties, trigger workflows, submit forms, transfer money, create financial transactions, or update any external system.</p>
        <p>The app only returns a validation result based on the numbers provided in the current request.</p>
        {nav_html()}
        """,
    )


def terms_html():
    return html_page(
        f"{APP_NAME} Terms",
        f"""
        <div class="eyebrow">Terms of Use</div>
        <h1>{APP_NAME}</h1>
        <p>Effective date / last updated: {EFFECTIVE_DATE}</p>
        <h2>Service description</h2>
        <p>{APP_NAME} is a numeric validation tool. It only checks whether provided allocation amounts exceed a provided total budget.</p>
        <h2>Usage scope</h2>
        <p>The service is limited to deterministic validation of explicitly provided numbers through the MCP endpoint.</p>
        <h2>What the tool does not do</h2>
        <p>It is not a financial advisor. It does not provide financial advice, investment advice, spending recommendations, budget optimization, or real money movement.</p>
        <h2>User responsibility</h2>
        <p>Users are responsible for checking important results before relying on them and for deciding whether the tool is suitable for their workflow.</p>
        <h2>Prohibited uses</h2>
        <p>The tool should not be used for illegal, harmful, or high-risk financial decisions, or for requesting recommendations about how to spend or split money.</p>
        <h2>Disclaimer and service changes</h2>
        <p>The service is provided as-is without guarantees of uninterrupted availability or suitability for a particular purpose. Service details may change over time.</p>
        <h2>Contact</h2>
        <p><a href="mailto:{SUPPORT_EMAIL}">{SUPPORT_EMAIL}</a></p>
        {nav_html()}
        """,
    )


def support_html():
    return html_page(
        f"{APP_NAME} Support",
        f"""
        <div class="eyebrow">Support</div>
        <h1>{APP_NAME}</h1>
        <p>Support email: <a href="mailto:{SUPPORT_EMAIL}">{SUPPORT_EMAIL}</a></p>
        <h2>What users can contact support about</h2>
        <ul>
          <li>Problems connecting to the MCP endpoint</li>
          <li>Unexpected validation results</li>
          <li>Questions about app scope</li>
          <li>Privacy or data requests</li>
          <li>Reporting broken pages or service issues</li>
        </ul>
        <h2>Response expectations</h2>
        <p>Support responses are provided on a reasonable-effort basis. Include the route used, request shape, expected behavior, and actual behavior when reporting an issue.</p>
        {nav_html()}
        """,
    )


def health_html():
    return html_page(
        f"{APP_NAME} Health",
        f"""
        <div class="eyebrow">Health</div>
        <h1>{APP_NAME} Health</h1>
        <div class="status">Service status: OK</div>
        <p>This page indicates that the {APP_NAME} review shell is reachable.</p>
        <p>The MCP endpoint is available at <code>POST /mcp</code>.</p>
        <p>Last updated / page purpose: review shell status and route availability as of {EFFECTIVE_DATE}.</p>
        {nav_html(include_health_json=True)}
        """,
    )


def build_tool_definition():
    return {
        "name": TOOL_NAME,
        "title": TOOL_TITLE,
        "description": TOOL_DESCRIPTION,
        "inputSchema": TOOL_INPUT_SCHEMA,
        "outputSchema": TOOL_OUTPUT_SCHEMA,
        "annotations": TOOL_ANNOTATIONS,
    }


def build_initialize_result():
    return {
        "protocolVersion": PROTOCOL_VERSION,
        "serverInfo": SERVER_INFO,
        "capabilities": {"tools": {}},
    }


def jsonrpc_result(request_id, result):
    return {"jsonrpc": JSONRPC_VERSION, "id": request_id, "result": result}


def jsonrpc_error(request_id, code, message):
    return {
        "jsonrpc": JSONRPC_VERSION,
        "id": request_id,
        "error": {"code": code, "message": message},
    }


def tool_result(structured_content):
    compact = json.dumps(structured_content, ensure_ascii=True, separators=(",", ":"))
    return {
        "content": [{"type": "text", "text": compact}],
        "structuredContent": structured_content,
        "isError": structured_content["status"] == "error",
    }


def error_output(code, message):
    return {
        "is_valid": False,
        "total_budget": 0,
        "total_allocated": 0,
        "remaining": 0,
        "overflow": 0,
        "status": "error",
        "error": {"code": code, "message": message},
    }


def is_number(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def detect_out_of_scope(arguments):
    if not isinstance(arguments, dict):
        return False

    banned_terms = [
        "should i",
        "should we",
        "should spend",
        "should allocate",
        "budget advice",
        "financial advice",
        "investment advice",
        "worthwhile",
        "better than",
        "how to split",
        "split a budget",
        "decision",
        "decision-making",
        "recommendation",
        "recommend",
        "optimize",
        "optimization",
        "transfer money",
        "move money",
        "wire money",
        "external system",
        "bank",
        "investment",
    ]
    marker_keys = {
        "advice",
        "recommendation",
        "optimization",
        "should_spend",
        "should_allocate",
        "decision",
        "decision_making",
    }
    if any(key in arguments for key in marker_keys):
        return True

    for key in ("request", "question", "prompt", "advice", "action"):
        value = arguments.get(key)
        if isinstance(value, str):
            lowered = value.lower()
            if any(term in lowered for term in banned_terms):
                return True
    return False


def validate_arguments(arguments):
    if detect_out_of_scope(arguments):
        return error_output(
            "out_of_scope",
            "Request is out of scope for this deterministic budget validation tool.",
        )

    if not isinstance(arguments, dict):
        return error_output(
            "invalid_value",
            "Arguments must be an object with total_budget and allocations.",
        )

    expected_keys = {"total_budget", "allocations"}
    actual_keys = set(arguments.keys())

    if "total_budget" not in arguments or "allocations" not in arguments:
        return error_output(
            "missing_field",
            "Both total_budget and allocations are required.",
        )

    if actual_keys != expected_keys:
        return error_output(
            "invalid_value",
            "Only total_budget and allocations are allowed.",
        )

    total_budget = arguments["total_budget"]
    allocations = arguments["allocations"]

    if not is_number(total_budget) or total_budget < 0:
        return error_output(
            "invalid_value",
            "total_budget must be a non-negative number.",
        )

    if not isinstance(allocations, list):
        return error_output(
            "invalid_value",
            "allocations must be an array of allocation objects.",
        )

    for item in allocations:
        if not isinstance(item, dict):
            return error_output(
                "invalid_value",
                "Each allocation must be an object with name and amount.",
            )
        if set(item.keys()) != {"name", "amount"}:
            return error_output(
                "invalid_value",
                "Each allocation must contain only name and amount.",
            )
        if not isinstance(item.get("name"), str):
            return error_output(
                "invalid_value",
                "Each allocation name must be a string.",
            )
        if not item["name"].strip():
            return error_output(
                "invalid_value",
                "Each allocation name must be a non-empty string.",
            )
        amount = item.get("amount")
        if not is_number(amount) or amount < 0:
            return error_output(
                "invalid_value",
                "Each allocation amount must be a non-negative number.",
            )

    return None


def validate_budget_constraint(arguments):
    validation_error = validate_arguments(arguments)
    if validation_error is not None:
        return validation_error

    total_budget = arguments["total_budget"]
    total_allocated = sum(item["amount"] for item in arguments["allocations"])

    if total_allocated <= total_budget:
        return {
            "is_valid": True,
            "total_budget": total_budget,
            "total_allocated": total_allocated,
            "remaining": total_budget - total_allocated,
            "overflow": 0,
            "status": "valid",
            "error": None,
        }

    return {
        "is_valid": False,
        "total_budget": total_budget,
        "total_allocated": total_allocated,
        "remaining": 0,
        "overflow": total_allocated - total_budget,
        "status": "over_budget",
        "error": None,
    }


def handle_initialize(request_id):
    return jsonrpc_result(request_id, build_initialize_result())


def handle_tools_list(request_id):
    return jsonrpc_result(request_id, {"tools": [build_tool_definition()]})


def handle_tools_call(request_id, params):
    if not isinstance(params, dict):
        return jsonrpc_error(request_id, -32602, "Invalid params")

    if params.get("name") != TOOL_NAME:
        return jsonrpc_error(request_id, -32602, f"Unknown tool: {params.get('name')}")

    try:
        structured_content = validate_budget_constraint(params.get("arguments"))
    except Exception:
        structured_content = error_output(
            "internal_error",
            "An internal error occurred while validating the budget constraint.",
        )

    return jsonrpc_result(request_id, tool_result(structured_content))


def handle_mcp_request(payload):
    if not isinstance(payload, dict):
        return jsonrpc_error(None, -32600, "Invalid Request")

    request_id = payload.get("id")
    method = payload.get("method")
    params = payload.get("params", {})

    if method == "initialize":
        return handle_initialize(request_id)
    if method == "tools/list":
        return handle_tools_list(request_id)
    if method == "tools/call":
        return handle_tools_call(request_id, params)

    return jsonrpc_error(request_id, -32601, "Method not found")


class MCPRequestHandler(BaseHTTPRequestHandler):
    server_version = "BudgetConstraintValidatorMCP/0.1.0"

    def _write_json(self, status_code, payload):
        body = json.dumps(payload, ensure_ascii=True).encode("utf-8")
        self.send_response(status_code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _write_html(self, status_code, html_text):
        body = html_text.encode("utf-8")
        self.send_response(status_code)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if self.path == "/":
            self._write_html(200, homepage_html())
            return

        if self.path == "/privacy":
            self._write_html(200, privacy_html())
            return

        if self.path == "/terms":
            self._write_html(200, terms_html())
            return

        if self.path == "/support":
            self._write_html(200, support_html())
            return

        if self.path == "/health":
            self._write_html(200, health_html())
            return

        if self.path == "/health.json":
            self._write_json(200, {"status": "ok", "app": APP_NAME})
            return

        if self.path == "/.well-known/openai-apps-challenge":
            self._write_text(200, os.environ.get("OPENAI_APPS_CHALLENGE", ""))
            return

        if self.path == "/mcp":
            self._write_json(405, {"error": "Method Not Allowed"})
            return

        self._write_json(404, {"error": "Not found"})

    def do_POST(self):
        if self.path != "/mcp":
            self._write_json(404, {"error": "Not found"})
            return

        try:
            content_length = int(self.headers.get("Content-Length", "0"))
            raw_body = self.rfile.read(content_length)
            payload = json.loads(raw_body.decode("utf-8"))
        except (ValueError, UnicodeDecodeError, json.JSONDecodeError):
            self._write_json(400, jsonrpc_error(None, -32700, "Parse error"))
            return

        response = handle_mcp_request(payload)
        self._write_json(200, response)

    def log_message(self, format_string, *args):
        return

    def _write_text(self, status_code, text_value):
        body = text_value.encode("utf-8")
        self.send_response(status_code)
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def run():
    port = int(os.environ.get("PORT", "8000"))
    server = ThreadingHTTPServer(("0.0.0.0", port), MCPRequestHandler)
    try:
        print(
            f"Budget Constraint Validator MCP server listening on http://127.0.0.1:{port}",
            flush=True,
        )
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    run()
