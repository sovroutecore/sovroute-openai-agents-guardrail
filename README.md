# SovRoute × OpenAI Agents SDK — Bitcoin & EVM Pre-Flight Security Guardrail

Production integration connecting **OpenAI Agents SDK** agents to **SovRoute**'s sovereign Bitcoin Core v31.1 & EVM forensics MCP server (`https://node.sovroute.com/mcp`) over **Streamable HTTP** via `MCPServerStreamableHttp`.

## Why This Matters
Autonomous payment and treasury agents shouldn't guess Bitcoin fee rates, mempool congestion, 0-conf Replace-By-Fee (RBF) fraud risks, or malicious EVM EIP-7702 delegations. SovRoute acts as a **deterministic pre-flight guardrail** exposing **7 read-only & zero-broadcast tools**:

1. **Live Fee & Mempool Oracle** (`get_bitcoin_smart_fees`, `get_mempool_entropy`, `verify_block_header`)
2. **Next-Block Miner Template X-Ray** (`get_next_block_xray`)
3. **0-Conf RBF Double-Spend Shield** (`check_rbf_fraud_shield`)
4. **Zero-Broadcast Consensus Simulator** (`simulate_raw_transaction`)
5. **EIP-7702 AuthTx Drainer Shield** (`inspect_eip7702_authorization`)

## Quickstart

```bash
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env
```

### 1. Smoke-Test MCP Connection (No LLM Key Required)
Verify connection to SovRoute's Remote Streamable HTTP MCP server:
```bash
python agent_demo.py --verify-mcp
```

### 2. Run OpenAI Agents SDK Security Guardrail
Configure your OpenAI API key (or any OpenAI-compatible provider such as OpenRouter or local endpoint) in `.env`:

```env
OPENAI_API_KEY=your-api-key
OPENAI_API_BASE=https://openrouter.ai/api/v1  # Optional: for OpenRouter or custom endpoint
LLM_MODEL=nvidia/nemotron-3.5-lightning:free     # Or gpt-4o, deepseek-v4.1, etc.
```

Run a live pre-flight audit against the freshest unconfirmed Bitcoin transaction from mempool:
```bash
python agent_demo.py --live-sample --delegate-address 0x000000000000000000000000000000000000dEaD
```

Or audit a specific Bitcoin transaction ID:
```bash
python agent_demo.py --txid 5b99afdf5342215ddad4ea382ff3aa933fcc231d64a0340b10785f9a3e4254d8
```

## Streamable HTTP MCP Code Snippet

```python
from agents import Agent, Runner, OpenAIChatCompletionsModel
from agents.mcp import MCPServerStreamableHttp
from openai import AsyncOpenAI

client = AsyncOpenAI(api_key="your-key")
model = OpenAIChatCompletionsModel(model="gpt-4o", openai_client=client)

async with MCPServerStreamableHttp(
    name="SovRoute MCP",
    params={"url": "https://node.sovroute.com/mcp"}
) as mcp_server:
    agent = Agent(
        name="SovRoute Pre-Flight Guardrail",
        instructions="Audit live Bitcoin mempool & fee state before transaction execution.",
        model=model,
        mcp_servers=[mcp_server],
    )
    result = await Runner.run(agent, input="Audit live network state")
    print(result.final_output)
```

## Sample Pre-Flight Security Report

```markdown
=== SOVROUTE x OPENAI AGENTS SDK PRE-FLIGHT SECURITY REPORT ===

# Pre-Flight Security Report

## Network Fees
- Fastest Fee Rate: 2.11 sat/vB
- Half Hour: 1.55 sat/vB
- Hour: 1.31 sat/vB
- Economic: 1.19 sat/vB

## Mempool State
- Unconfirmed Transactions: 52,292
- Total Mempool Size (vsize): 30,520,000 bytes
- Congestion Level: HIGH

## Candidate Block X-Ray
- Block Height: 976,596
- Total Selected Transactions: 3,412
- Cutoff Fee Rate: 2.05 sat/vB
- Queue Status: GUARANTEED_NEXT_BLOCK

## 0-Conf RBF Double-Spend Risk
- BIP-125 Replaceable: Yes
- Conflicting Spends: None
- Risk Level: HIGH_RISK_RBF_ENABLED
- Recommendation: Do not accept 0-confirmation payment. Wait for 1 on-chain block confirmation.

## EIP-7702 Delegation Check
- Target Address: 0x000000000000000000000000000000000000dEaD
- Risk Level: SUSPICIOUS_UNVERIFIED
- Details: Burn/dead address delegation detected with zero prior transaction history.

FINAL VERDICT: HOLD
```

## Multi-Rail Payment
SovRoute MCP includes **15 free evaluation calls per 24 hours per IP**. For high-throughput production agents, requests settle via:
- **Lightning Network (L402):** 1–5 satoshis per call
- **Base L2 (x402 v2):** $0.001–$0.005 USDC per call to `0x488cbDad29E60d8Bae53FFF4c4252C9711dF9784`

## License
MIT
