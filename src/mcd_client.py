"""麦当劳 MCP 客户端封装（streamablehttp）。

只做两件事：
1. 把 mcd-mcp 的工具调用包成Python函数；
2. 对返回做宽松字段映射，映射不到的返回 None 并由上层剔除。

不缓存、不猜测任何菜单/营养数据——所有值必须来自 MCP 实时返回。
"""
from __future__ import annotations

import json
import os
import urllib.error
import urllib.request

MCP_URL = os.environ.get("MCD_MCP_URL", "https://mcp.mcd.cn")
TOKEN = os.environ.get("MCD_MCP_TOKEN", "")

def _load_dotenv():
    """从项目根目录 .env 读取 MCD_MCP_TOKEN（仅本地开发用，.env 不入库）。"""
    if TOKEN:
        return
    p = os.path.join(os.path.dirname(__file__), "..", ".env")
    try:
        with open(p) as f:
            for line in f:
                if line.startswith("MCD_MCP_TOKEN="):
                    os.environ.setdefault("MCD_MCP_TOKEN", line.split("=", 1)[1].strip())
    except OSError:
        pass

_load_dotenv()
TOKEN = os.environ.get("MCD_MCP_TOKEN", "")

_ID = 0
_SESSION = ""


def _rpc(method: str, params: dict | None = None) -> dict | None:
    """JSON-RPC 调用麦当劳 MCP Server（带 Mcp-Session-Id 会话管理）。"""
    global _ID, _SESSION
    _ID += 1
    payload = {"jsonrpc": "2.0", "id": _ID, "method": method}
    if params is not None:
        payload["params"] = params
    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json, text/event-stream",
        "Authorization": f"Bearer {TOKEN}",
    }
    if _SESSION:
        headers["Mcp-Session-Id"] = _SESSION
    req = urllib.request.Request(MCP_URL, data=json.dumps(payload).encode(),
                                 headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            sid = resp.headers.get("Mcp-Session-Id")
            if sid:
                _SESSION = sid
            body = resp.read().decode()
    except urllib.error.HTTPError as e:
        if e.code == 403 and method != "initialize":
            _ensure_session()
            req = urllib.request.Request(MCP_URL, data=json.dumps(payload).encode(),
                                         headers={**headers,
                                                  "Mcp-Session-Id": _SESSION} if _SESSION else headers,
                                         method="POST")
            with urllib.request.urlopen(req, timeout=30) as resp:
                body = resp.read().decode()
        else:
            raise
    return _parse_body(body)


def _ensure_session():
    """发 initialize 完成握手，拿到会话 id。"""
    global _SESSION
    _SESSION = ""
    body = _rpc_raw("initialize", {"protocolVersion": "2025-03-26",
                                   "capabilities": {},
                                   "clientInfo": {"name": "calorie-wallet", "version": "1.0"}})
    if _SESSION:
        _rpc_raw("notifications/initialized", None)


def _rpc_raw(method: str, params: dict | None = None) -> dict | None:
    """不处理 403 的底层调用。"""
    global _ID, _SESSION
    _ID += 1
    payload = {"jsonrpc": "2.0", "id": _ID, "method": method}
    if params is not None:
        payload["params"] = params
    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json, text/event-stream",
        "Authorization": f"Bearer {TOKEN}",
    }
    if _SESSION:
        headers["Mcp-Session-Id"] = _SESSION
    req = urllib.request.Request(MCP_URL, data=json.dumps(payload).encode(),
                                 headers=headers, method="POST")
    with urllib.request.urlopen(req, timeout=30) as resp:
        sid = resp.headers.get("Mcp-Session-Id")
        if sid:
            _SESSION = sid
        body = resp.read().decode()
    return _parse_body(body)


def _parse_body(body: str) -> dict | None:
    # streamablehttp 可能返回 SSE 帧，取最后一行 JSON
    for line in reversed(body.splitlines()):
        line = line.strip()
        if line.startswith("data:"):
            line = line[5:].strip()
        if line.startswith("{"):
            return json.loads(line)
    return None


def list_tools() -> list[dict]:
    """发现 MCP 提供的工具列表（只读，用于运行前体检）。"""
    data = _rpc("tools/list", {})
    return (data or {}).get("result", {}).get("tools", [])


def call_tool(name: str, arguments: dict) -> dict | None:
    """调用一个 MCP 工具并返回其 content 里的 JSON（若有）。"""
    data = _rpc("tools/call", {"name": name, "arguments": arguments})
    result = (data or {}).get("result") or {}
    for block in result.get("content", []):
        if block.get("type") == "text":
            text = block.get("text", "")
            try:
                return json.loads(text)
            except json.JSONDecodeError:
                return {"raw": text}
    return result or None


def _pick(d: dict | None, *keys):
    """宽松取值：在 dict 里按候选键名依次找。"""
    if not isinstance(d, dict):
        return None
    for k in keys:
        if k in d and d[k] is not None:
            return d[k]
    return None


def get_menu(store_id: str) -> list[dict]:
    """查询门店在售菜单。工具名按 MCP 实际列表自动匹配。"""
    for name in ("menu_get", "get_menu", "menu", "store_menu"):
        data = call_tool(name, {"storeId": store_id, "store_id": store_id})
        if data:
            items = _pick(data, "items", "menu", "products", "list") or []
            if isinstance(items, list):
                return items
    raise RuntimeError("未找到菜单类 MCP 工具，请先运行 list_tools() 核对工具名")


def get_nutrition(product_id: str) -> dict | None:
    """查询单品营养数据（能量 kcal 等）。"""
    for name in ("product_nutrition", "get_nutrition", "product_detail", "product"):
        data = call_tool(name, {"productId": product_id, "product_id": product_id})
        if data:
            return data
    return None


def calc_price(items: list[dict]) -> dict | None:
    """对一组商品做价格试算。"""
    for name in ("price_calc", "calc_price", "price", "order_preview"):
        data = call_tool(name, {"items": items})
        if data:
            return data
    return None
