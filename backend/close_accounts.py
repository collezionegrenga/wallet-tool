import sys
import asyncio
from solana.rpc.api import AsyncClient
from solders.pubkey import Pubkey as PublicKey
from solders.instruction import AccountMeta, Instruction as TransactionInstruction
from solders.hash import Hash
from solana.transaction import Transaction
from solders.system_program import TransferParams, transfer
from typing import List

RECIPIENT_10 = "5AVbEpWRAHhmk2VFwvJMubwvkqbBRxKuXjCWpz9GKqU"
TOKEN_PROGRAM_ID = "TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA"
LAMPORTS_PER_SOL = 1_000_000_000
SYSTEM_PROGRAM_ID = "11111111111111111111111111111111"

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
        # Utilizziamo transfer da solders.system_program
        tx.add(
            TransactionInstruction(
                program_id=PublicKey.from_string(SYSTEM_PROGRAM_ID),
                data=bytes([2, 0, 0, 0, 0, 0, 0, 0]) + lamports_90.to_bytes(8, byteorder='little', signed=False),
                keys=[
                    AccountMeta(pubkey=user, is_signer=True, is_writable=True),
                    AccountMeta(pubkey=user, is_signer=False, is_writable=True),
                ],
            )
        )
    if lamports_10 > 0:
        tx.add(
            TransactionInstruction(
                program_id=PublicKey.from_string(SYSTEM_PROGRAM_ID),
                data=bytes([2, 0, 0, 0, 0, 0, 0, 0, 0]) + lamports_10.to_bytes(8, byteorder='little', signed=False),
                keys=[
                    AccountMeta(pubkey=user, is_signer=True, is_writable=True),
                    AccountMeta(pubkey=recipient_10, is_signer=False, is_writable=True),
                ],
            )
        )
    # Simula per ottenere fee e blockhash
    recent_blockhash = (await client.get_recent_blockhash())["result"]["value"]["blockhash"]
    tx.recent_blockhash = Hash.from_string(recent_blockhash)
    tx.fee_payer = user
    await client.close()
    return {"tx": tx.serialize_message().hex()}
