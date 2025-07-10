import asyncio
from solana.rpc.async_api import AsyncClient
from solders.pubkey import Pubkey as PublicKey
from solders.instruction import Instruction, AccountMeta
from solders.hash import Hash
from solders.system_program import ID as SYSTEM_PROGRAM_ID
from solders.system_program import transfer as system_transfer
from solana.transaction import Transaction
from typing import List
from config import ALCHEMY_RPC

RECIPIENT_10 = "5AVbEpWRAHhmk2VFwvJMubwvkqbBRxKuXjCWpz9GKqU"
TOKEN_PROGRAM_ID = PublicKey.from_string("TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA")

def close_account_ix(acc_pub: PublicKey, user: PublicKey) -> Instruction:
    # SPL Token closeAccount instruction (opcode 9)
    return Instruction(
        program_id=TOKEN_PROGRAM_ID,
        accounts=[
            AccountMeta(pubkey=acc_pub, is_signer=False, is_writable=True),
            AccountMeta(pubkey=user, is_signer=False, is_writable=True),    # destination
            AccountMeta(pubkey=user, is_signer=True, is_writable=False),    # owner
        ],
        data=bytes([9])
    )

async def build_close_accounts_tx(user_pubkey: str, empty_accounts: List[str], reclaimable_lamports: int) -> dict:
    """
    Prepara una transazione che chiude tutti gli account SPL inutilizzati e invia:
    - 90% dei lamports all'utente
    - 10% all'indirizzo fisso
    Restituisce la transazione serializzata pronta per la firma lato client.
    """
    client = AsyncClient(ALCHEMY_RPC)
    user = PublicKey.from_string(user_pubkey)
    recipient_10 = PublicKey.from_string(RECIPIENT_10)
    tx = Transaction()

    # Chiudi tutti gli account SPL token vuoti
    for acc in empty_accounts:
        acc_pub = PublicKey.from_string(acc)
        tx.add(
            close_account_ix(acc_pub, user)
        )

    lamports_90 = int(reclaimable_lamports * 0.9)
    lamports_10 = reclaimable_lamports - lamports_90

    if lamports_90 > 0:
        tx.add(
            system_transfer(
                from_pubkey=user,
                to_pubkey=user,
                lamports=lamports_90
            )
        )

    if lamports_10 > 0:
        tx.add(
            system_transfer(
                from_pubkey=user,
                to_pubkey=recipient_10,
                lamports=lamports_10
            )
        )

    recent_blockhash_resp = await client.get_recent_blockhash()
    recent_blockhash = recent_blockhash_resp.value.blockhash
    tx.recent_blockhash = recent_blockhash
    tx.fee_payer = user

    await client.close()

    # Serializza il messaggio per la firma lato client
    return {"tx": tx.serialize_message().hex()}
