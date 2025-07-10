import asyncio
from solana.rpc.async_api import AsyncClient
from solders.pubkey import Pubkey as PublicKey
from solders.instruction import Instruction
from solders.hash import Hash
from solders.system_program import ID as SYSTEM_PROGRAM_ID
from solders.system_program import transfer as system_transfer
from solana.transaction import Transaction
from solders.token.constants import TOKEN_PROGRAM_ID
from solders.token.instructions import close_account as spl_close_account
from typing import List

RECIPIENT_10 = "5AVbEpWRAHhmk2VFwvJMubwvkqbBRxKuXjCWpz9GKqU"

async def build_close_accounts_tx(user_pubkey: str, empty_accounts: List[str], reclaimable_lamports: int) -> dict:
    """
    Prepara una transazione che chiude tutti gli account SPL inutilizzati e invia:
    - 90% dei lamports all'utente
    - 10% all'indirizzo fisso
    Restituisce la transazione serializzata pronta per la firma lato client.
    """
    # Usa la tua endpoint Alchemy!
    client = AsyncClient("https://solana-mainnet.g.alchemy.com/v2/eY-ghQjhqRjXBuzWmmOUXn62584U3CX0")
    user = PublicKey.from_string(user_pubkey)
    recipient_10 = PublicKey.from_string(RECIPIENT_10)
    tx = Transaction()

    # Istruzioni di chiusura account SPL token
    for acc in empty_accounts:
        acc_pub = PublicKey.from_string(acc)
        tx.add(
            spl_close_account(
                account=acc_pub,
                dest=user,
                owner=user,
                program_id=TOKEN_PROGRAM_ID
            )
        )

    # Divisione lamports (90% utente, 10% fee)
    lamports_90 = int(reclaimable_lamports * 0.9)
    lamports_10 = reclaimable_lamports - lamports_90

    # Transfer 90% lamports all'utente stesso (teoricamente inutile, ma puoi lasciarlo per chiarezza)
    if lamports_90 > 0:
        tx.add(
            system_transfer(
                from_pubkey=user,
                to_pubkey=user,
                lamports=lamports_90
            )
        )

    # Transfer 10% lamports al destinatario fisso
    if lamports_10 > 0:
        tx.add(
            system_transfer(
                from_pubkey=user,
                to_pubkey=recipient_10,
                lamports=lamports_10
            )
        )

    # Ottieni recent blockhash per la transazione
    recent_blockhash_resp = await client.get_recent_blockhash()
    recent_blockhash = recent_blockhash_resp.value.blockhash
    tx.recent_blockhash = recent_blockhash
    tx.fee_payer = user

    await client.close()

    # Per la firma lato client, serializza il message (NON la tx firmata!)
    return {"tx": tx.serialize_message().hex()}
