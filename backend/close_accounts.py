import sys
import asyncio
from solana.rpc.api import Client
from solders.pubkey import Pubkey as PublicKey
from solana.transaction import Transaction, TransactionInstruction, AccountMeta
from solana.system_program import TransferParams, transfer
from solana.rpc.async_api import AsyncClient
from solana.keypair import Keypair
from solana.rpc.types import TxOpts
from typing import List

RECIPIENT_10 = "5AVbEpWRAHhmk2VFwvJMubwvkqbBRxKuXjCWpz9GKqU"
TOKEN_PROGRAM_ID = "TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA"
LAMPORTS_PER_SOL = 1_000_000_000

async def build_close_accounts_tx(user_pubkey: str, empty_accounts: List[str], reclaimable_lamports: int) -> dict:
    """
    Prepara una transazione che chiude tutti gli account SPL inutilizzati e invia:
    - 90% dei lamports all'utente
    - 10% all'indirizzo fisso
    Restituisce la transazione serializzata pronta per la firma lato client.
    """
    client = AsyncClient("https://api.mainnet-beta.solana.com")
    user = PublicKey.from_string(user_pubkey)
    recipient_10 = PublicKey.from_string(RECIPIENT_10)
    tx = Transaction()
    # Istruzioni di chiusura account
    for acc in empty_accounts:
        acc_pub = PublicKey.from_string(acc)
        tx.add(
            TransactionInstruction(
                program_id=PublicKey.from_string(TOKEN_PROGRAM_ID),
                data=bytes([9]),  # closeAccount instruction
                keys=[
                    AccountMeta(pubkey=acc_pub, is_signer=False, is_writable=True),
                    AccountMeta(pubkey=user, is_signer=True, is_writable=True),
                    AccountMeta(pubkey=user, is_signer=True, is_writable=True),
                ],
            )
        )
    # Split lamports
    lamports_90 = int(reclaimable_lamports * 0.9)
    lamports_10 = reclaimable_lamports - lamports_90
    if lamports_90 > 0:
        tx.add(transfer(TransferParams(from_pubkey=user, to_pubkey=user, lamports=lamports_90)))
    if lamports_10 > 0:
        tx.add(transfer(TransferParams(from_pubkey=user, to_pubkey=recipient_10, lamports=lamports_10)))
    # Simula per ottenere fee e blockhash
    recent_blockhash = (await client.get_recent_blockhash())["result"]["value"]["blockhash"]
    tx.recent_blockhash = recent_blockhash
    tx.fee_payer = user
    await client.close()
    return {"tx": tx.serialize_message().hex()}

# Flask API usage example:
# from flask import request, jsonify
# @app.route('/api/close', methods=['POST'])
# def close_accounts():
#     data = request.json
#     user_pubkey = data['user_pubkey']
#     empty_accounts = data['empty_accounts']
#     reclaimable_lamports = data['reclaimable_lamports']
#     tx = asyncio.run(build_close_accounts_tx(user_pubkey, empty_accounts, reclaimable_lamports))
#     return jsonify(tx) 
