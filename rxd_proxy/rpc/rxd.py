"""
Radiant blockchain RPC interface.
"""
import json


async def getblocktemplate(session, node_url: str):
    """
    Get a block template from the Radiant node.
    Radiant doesn't use SegWit, so we request a standard template.
    """
    data = {
        "jsonrpc": "1.0",
        "id": "stratum",
        "method": "getblocktemplate",
        "params": [{}],
    }
    async with session.post(node_url, data=json.dumps(data)) as resp:
        return await resp.json()


async def submitblock(session, node_url: str, block_hex: str):
    """Submit a solved block to the Radiant network."""
    data = {
        "jsonrpc": "1.0",
        "id": "stratum",
        "method": "submitblock",
        "params": [block_hex],
    }
    async with session.post(node_url, data=json.dumps(data)) as resp:
        return await resp.json()


async def getblock(session, node_url: str, block_hash: str):
    """Query a block for confirmation status."""
    data = {
        "jsonrpc": "1.0",
        "id": "stratum",
        "method": "getblock",
        "params": [block_hash],
    }
    async with session.post(node_url, data=json.dumps(data)) as resp:
        return await resp.json()


async def getblockchaininfo(session, node_url: str):
    """Get blockchain info including chain tip."""
    data = {
        "jsonrpc": "1.0",
        "id": "stratum",
        "method": "getblockchaininfo",
        "params": [],
    }
    async with session.post(node_url, data=json.dumps(data)) as resp:
        return await resp.json()


async def getmininginfo(session, node_url: str):
    """Get mining-related information."""
    data = {
        "jsonrpc": "1.0",
        "id": "stratum",
        "method": "getmininginfo",
        "params": [],
    }
    async with session.post(node_url, data=json.dumps(data)) as resp:
        return await resp.json()
