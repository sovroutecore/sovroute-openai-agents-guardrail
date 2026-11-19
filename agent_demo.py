"""
SovRoute x OpenAI Agents SDK — Bitcoin & EVM Pre-Flight Security Guardrail

Connects an OpenAI Agents SDK Agent directly to SovRoute's Remote Streamable HTTP MCP
server (https://node.sovroute.com/mcp) using MCPServerStreamableHttp.
"""

import argparse
import asyncio
import json
import os
import sys

from dotenv import load_dotenv
import httpx

load_dotenv()

SOVROUTE_MCP_URL = os.getenv("SOVROUTE_MCP_URL", "https://node.sovroute.com/mcp")
SYSTEM_INSTRUCTIONS = (
    "You are the SovRoute Pre-Flight Bitcoin & EVM Security Guardrail. "
    "Always verify live blockchain conditions using the connected SovRoute MCP tools; "
    "never guess or invent numbers. Call get_bitcoin_smart_fees, get_mempool_entropy, "
    "verify_block_header, get_next_block_xray (with txid if provided), and "
    "check_rbf_fraud_shield (with txid if provided). If delegate_address is provided, "
    "call inspect_eip7702_authorization with executionChainId=1 and "
    'authorizationList=[{"chainId": 1, "address": delegate_address, "nonce": 0}]. '
    "Output a concise structured Markdown Pre-Flight Security Report covering Network Fees, "
    "Mempool State, Candidate Block X-Ray, 0-Conf RBF Risk, EIP-7702 Check (if run), "
    "and end with FINAL VERDICT: APPROVE, HOLD, or REJECT."
)


def _mcp_headers(include_json_accept: bool = False) -> dict[str, str]:
    headers: dict[str, str] = {}
    if include_json_accept:
        headers["Content-Type"] = "application/json"
        headers["Accept"] = "application/json, text/event-stream"
    if sig := os.getenv("SOVROUTE_PAYMENT_SIGNATURE", "").strip():
        headers["Payment-Signature"] = sig
    if l402 := os.getenv("SOVROUTE_L402_TOKEN", "").strip():
        headers["Authorization"] = f"L402 {l402}"
    if demo := os.getenv("MCP_DEMO_BYPASS_KEY", "").strip():
        headers["X-SovRoute-Demo-Key"] = demo
    return headers


def _parse_mcp_response(text: str) -> dict:
    for line in text.splitlines():
        if line.startswith("data:"):
            return json.loads(line[5:].strip())
    return json.loads(text)


async def _mcp_rpc(client: httpx.AsyncClient, headers: dict[str, str], req_id: int, method: str, params: dict) -> dict:
    res = await client.post(
        SOVROUTE_MCP_URL,
        headers=headers,
        json={"jsonrpc": "2.0", "id": req_id, "method": method, "params": params},
    )
    res.raise_for_status()
    return _parse_mcp_response(res.text)


async def verify_mcp_connection(txid: str | None = None) -> None:
    """Smoke-test the SovRoute Remote MCP endpoint without needing an LLM key."""
    print(f"[SovRoute MCP] Connecting to {SOVROUTE_MCP_URL} ...")
    headers = _mcp_headers(include_json_accept=True)
    async with httpx.AsyncClient(timeout=15.0) as client:
        await _mcp_rpc(client, headers, 1, "initialize", {
            "protocolVersion": "2025-03-26",
            "capabilities": {},
            "clientInfo": {"name": "sovroute-openai-agents-verifier", "version": "1.0.0"},
        })
        print("[SovRoute MCP] Handshake OK")

        tools = (await _mcp_rpc(client, headers, 2, "tools/list", {}))["result"]["tools"]
        print(f"[SovRoute MCP] Discovered {len(tools)} tools: {[t['name'] for t in tools]}")

        fee_res = await _mcp_rpc(client, headers, 3, "tools/call", {"name": "get_bitcoin_smart_fees", "arguments": {}})
        print("[SovRoute MCP] get_bitcoin_smart_fees output:")
        print(fee_res["result"]["content"][0]["text"])

        if txid:
            rbf_res = await _mcp_rpc(client, headers, 4, "tools/call", {"name": "check_rbf_fraud_shield", "arguments": {"txid": txid}})
            print(f"[SovRoute MCP] check_rbf_fraud_shield({txid}) output:")
            print(rbf_res["result"]["content"][0]["text"])


def _fetch_live_mempool_txid() -> str:
    urls = (
        "https://mempool.emzy.de/api/mempool/recent",
        "https://blockstream.info/api/mempool/recent",
        "https://mempool.space/api/mempool/recent",
    )
    for url in urls:
        try:
            res = httpx.get(url, timeout=5.0)
            res.raise_for_status()
            txs = res.json()
            if isinstance(txs, list) and txs and "txid" in txs[0]:
                return str(txs[0]["txid"])
        except Exception:
            continue
    raise RuntimeError("No recent unconfirmed transactions returned by mempool explorers")


async def run_openai_agents_audit(txid: str | None, delegate_address: str | None) -> None:
    api_key = os.getenv("OPENAI_API_KEY", "").strip()
    if not api_key:
        print("Error: OPENAI_API_KEY is required. Use --verify-mcp for key-free smoke testing.")
        sys.exit(1)

    from agents import Agent, OpenAIChatCompletionsModel, Runner, set_tracing_disabled
    from agents.mcp import MCPServerStreamableHttp
    from openai import AsyncOpenAI

    set_tracing_disabled(True)

    api_base = os.getenv("OPENAI_API_BASE", "").strip() or None
    model_name = os.getenv("LLM_MODEL", "nvidia/nemotron-3.5-lightning:free")

    client = AsyncOpenAI(api_key=api_key, base_url=api_base)
    model = OpenAIChatCompletionsModel(model=model_name, openai_client=client)

    headers = _mcp_headers(include_json_accept=False)
    mcp_params: dict = {"url": SOVROUTE_MCP_URL}
    if headers:
        mcp_params["headers"] = headers

    targets = [f"Bitcoin Transaction ID (txid): {txid}" if txid else "Audit live Bitcoin mainnet fee & mempool state."]
    if delegate_address:
        targets.append(f"EIP-7702 Delegate Address (chainId 1): {delegate_address}")

    async with MCPServerStreamableHttp(name="SovRoute MCP", params=mcp_params) as mcp_server:
        agent = Agent(
            name="SovRoute Pre-Flight Security Guardrail",
            instructions=SYSTEM_INSTRUCTIONS,
            model=model,
            mcp_servers=[mcp_server],
        )
        result = await Runner.run(
            agent,
            input="Run a SovRoute Pre-Flight Security Audit for:\n" + "\n".join(targets),
        )
        print("\n=== SOVROUTE x OPENAI AGENTS SDK PRE-FLIGHT SECURITY REPORT ===\n")
        print(result.final_output)


def main() -> None:
    parser = argparse.ArgumentParser(description="SovRoute x OpenAI Agents SDK Guardrail")
    parser.add_argument("--verify-mcp", action="store_true", help="Smoke-test SovRoute MCP endpoint without LLM")
    parser.add_argument("--txid", type=str, default=None, help="64-char hex Bitcoin transaction ID to audit")
    parser.add_argument("--live-sample", action="store_true", help="Fetch freshest unconfirmed TXID from mempool")
    parser.add_argument("--delegate-address", type=str, default=None, help="Optional EVM delegate address for EIP-7702")
    args = parser.parse_args()

    txid = args.txid
    if args.live_sample and not txid:
        txid = _fetch_live_mempool_txid()
        print(f"[Mainnet Sample] Selected unconfirmed TXID: {txid}")

    if args.verify_mcp:
        asyncio.run(verify_mcp_connection(txid))
        return

    asyncio.run(run_openai_agents_audit(txid, args.delegate_address))


if __name__ == "__main__":
    main()
