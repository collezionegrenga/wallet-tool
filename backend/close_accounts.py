import sys
import asyncio
from solana.rpc.async_api import AsyncClient
from solders.pubkey import Pubkey as PublicKey
from solana.system_program import TransferParams, transfer
from solders.instruction import AccountMeta, Instruction as TransactionInstruction
from solders.hash import Hash
from solana.transaction import Transaction
from typing import List

RECIPIENT_10 = "5AVbEpWRAHhmk2VFwvJMubwvkqbBRxKuXjCWpz9GKqU"
TOKEN_PROGRAM_ID = "TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA"

async def build_close_accounts_tx(user_pubkey: str, empty_accounts: List[str], reclaimable_lamports: int) -> dict:
    client = AsyncClient("https://api.mainnet-beta.solana.com")
    user = PublicKey.from_string(user_pubkey)
    recipient_10 = PublicKey.from_string(RECIPIENT_10)
    tx = Transaction()

    # Istruzioni di chiusura account SPL token
    for acc in empty_accounts:
        acc_pub = PublicKey.from_string(acc)
        tx.add(
            TransactionInstruction(
                program_id=PublicKey.from_string(TOKEN_PROGRAM_ID),
                data=bytes([9]),  # closeAccount instruction
                keys=[
                    AccountMeta(pubkey=acc_pub, is_signer=False, is_writable=True),
                    AccountMeta(pubkey=user, is_signer=False, is_writable=True),    # destination
                    AccountMeta(pubkey=user, is_signer=True, is_writable=False),    # owner
                ],
            )
        )

    # Divisione lamports
    lamports_90 = int(reclaimable_lamports * 0.9)
    lamports_10 = reclaimable_lamports - lamports_90

    # Transfer 90% lamports all'utente stesso
    if lamports_90 > 0:
        tx.add(
            transfer(
                TransferParams(
                    from_pubkey=user,
                    to_pubkey=user,
                    lamports=lamports_90
                )
            )
        )

    # Transfer 10% lamports al destinatario fisso
    if lamports_10 > 0:
        tx.add(
            transfer(
                TransferParams(
                    from_pubkey=user,
                    to_pubkey=recipient_10,
                    lamports=lamports_10
                )
            )
        )

    # Ottieni recent blockhash per la transazione
    recent_blockhash = (await client.get_recent_blockhash())["result"]["value"]["blockhash"]
    tx.recent_blockhash = Hash.from_string(recent_blockhash)
    tx.fee_payer = user

    await client.close()

    return {"tx": tx.serialize_message().hex()}
