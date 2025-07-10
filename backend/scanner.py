import sys
import os
import time
import json
import csv
import asyncio
import aiohttp
import traceback
from datetime import datetime

from solana.rpc.api import Client
from solana.rpc.types import TokenAccountOpts
from solders.pubkey import Pubkey as PublicKey

# === CONFIG ===
SOLANA_RPC = "https://solana-mainnet.g.alchemy.com/v2/eY-ghQjhqRjXBuzWmmOUXn62584U3CX0"
BACKUP_RPC = [
    "https://solana-api.projectserum.com",
    "https://api.mainnet-beta.solana.com",
]
TOKEN_PROGRAM_ID = "TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA"
RATE_LIMIT_RETRY_SECONDS = 1.5
MAX_RETRIES = 5
API_TIMEOUT = 15

token_symbol_cache = {}
token_price_cache = {}
nft_metadata_cache = {}

class EnhancedSolanaClient:
    def __init__(self, primary_endpoint, backup_endpoints=None):
        self.primary_client = Client(primary_endpoint)
        self.backup_clients = [Client(endpoint) for endpoint in (backup_endpoints or [])]
        self.current_client_index = 0
        self.clients = [self.primary_client] + self.backup_clients

    def get_current_client(self):
        return self.clients[self.current_client_index]

    def rotate_client(self):
        self.current_client_index = (self.current_client_index + 1) % len(self.clients)
        return self.get_current_client()

    def execute_with_retry(self, method_name, *args, **kwargs):
        retries = 0
        last_exc = None
        while retries < MAX_RETRIES:
            try:
                client = self.get_current_client()
                method = getattr(client, method_name)
                return method(*args, **kwargs)
            except Exception as e:
                last_exc = e
                msg = str(e)
                print(f"RPC error on endpoint {getattr(client, 'endpoint_uri', client)}: {type(e).__name__}: {msg}. Rotating endpoint and retrying ({retries+1}/{MAX_RETRIES})...")
                self.rotate_client()
                time.sleep(RATE_LIMIT_RETRY_SECONDS)
                retries += 1
        raise Exception(f"Failed after {MAX_RETRIES} attempts: {last_exc} ({type(last_exc).__name__})")

solana_client = EnhancedSolanaClient(SOLANA_RPC, BACKUP_RPC)

def lamports_to_sol(lamports: int) -> float:
    return lamports / 1_000_000_000

def format_number(num: float) -> str:
    if num >= 1_000_000:
        return f"{num/1_000_000:.2f}M"
    elif num >= 1_000:
        return f"{num/1_000:.2f}K"
    else:
        return f"{num:.4f}".rstrip('0').rstrip('.') if '.' in f"{num:.4f}" else f"{num}"

# === API HELPERS ===
async def fetch_api_data(session, url, headers=None):
    for attempt in range(MAX_RETRIES):
        try:
            async with session.get(url, headers=headers, timeout=API_TIMEOUT) as response:
                if response.status == 200:
                    return await response.json()
                elif response.status == 429:
                    wait_time = RATE_LIMIT_RETRY_SECONDS * (attempt + 1)
                    print(f"Rate limited. Waiting {wait_time}s before retry...")
                    await asyncio.sleep(wait_time)
                    continue
                else:
                    print(f"API error: Status code {response.status} for URL: {url}")
                    return None
        except Exception as e:
            print(f"API error: {str(e)} for URL: {url}")
            if attempt < MAX_RETRIES - 1:
                await asyncio.sleep(RATE_LIMIT_RETRY_SECONDS)
                continue
            else:
                print(f"Max retries reached for URL: {url}")
                return None
    return None

async def get_token_metadata(session, mint_address: str) -> dict:
    if mint_address in token_symbol_cache:
        return token_symbol_cache[mint_address]
    try:
        data = await fetch_api_data(session, f"https://public-api.solscan.io/token/meta?tokenAddress={mint_address}")
        if not data or not data.get("symbol"):
            jupiter_data = await fetch_api_data(session, f"https://token.jup.ag/token/{mint_address}")
            if jupiter_data:
                data = {
                    "symbol": jupiter_data.get("symbol", mint_address[:4] + "..."),
                    "name": jupiter_data.get("name", "Unknown"),
                    "decimals": jupiter_data.get("decimals", 0),
                    "icon": jupiter_data.get("logoURI", "")
                }
        if not data or not data.get("symbol"):
            data = {
                "symbol": mint_address[:4] + "...",
                "name": "Unknown",
                "decimals": 0,
                "icon": ""
            }
        token_symbol_cache[mint_address] = data
        return data
    except Exception as e:
        print(f"Error getting token metadata for {mint_address}: {e}")
        fallback = {"symbol": mint_address[:4] + "...", "name": "Unknown", "decimals": 0, "icon": ""}
        token_symbol_cache[mint_address] = fallback
        return fallback

async def get_token_price(session, mint_address: str) -> float:
    if mint_address in token_price_cache:
        return token_price_cache[mint_address]
    try:
        data = await fetch_api_data(session, f"https://price.jup.ag/v4/price?ids={mint_address}")
        if data and "data" in data and mint_address in data["data"]:
            price = data["data"][mint_address]["price"]
            token_price_cache[mint_address] = price
            return price
        data = await fetch_api_data(session, f"https://public-api.solscan.io/market/token/{mint_address}")
        if data and "priceUsdt" in data:
            price = float(data["priceUsdt"])
            token_price_cache[mint_address] = price
            return price
        return 0.0
    except Exception:
        return 0.0

async def is_nft(session, mint_address: str) -> bool:
    data = await fetch_api_data(session, f"https://public-api.solscan.io/token/meta?tokenAddress={mint_address}")
    if data and data.get("tokenType") == "nft":
        return True
    if data and data.get("decimals", 1) == 0 and str(data.get("supply", "2")) in ["1", "1.0"]:
        return True
    try:
        metaplex_data = await fetch_api_data(
            session,
            f"https://api.metaplex.solana.com/v1/tokens/{mint_address}/metadata"
        )
        if metaplex_data and "uri" in metaplex_data:
            return True
    except Exception:
        pass
    return False

async def get_nft_metadata(session, mint_address: str) -> dict:
    if mint_address in nft_metadata_cache:
        return nft_metadata_cache[mint_address]
    data = await fetch_api_data(session, f"https://public-api.solscan.io/nft/meta?tokenAddress={mint_address}")
    if data and data.get("name"):
        result = {
            "symbol": data.get("symbol", ""),
            "name": data.get("name", ""),
            "decimals": 0,
            "icon": data.get("icon", ""),
            "uri": data.get("metadataUri", ""),
            "collection": data.get("collection", {}).get("name", ""),
        }
        nft_metadata_cache[mint_address] = result
        return result
    try:
        metaplex_data = await fetch_api_data(
            session,
            f"https://api.metaplex.solana.com/v1/tokens/{mint_address}/metadata"
        )
        if metaplex_data and "name" in metaplex_data:
            result = {
                "symbol": metaplex_data.get("symbol", ""),
                "name": metaplex_data.get("name", ""),
                "decimals": 0,
                "icon": metaplex_data.get("image", ""),
                "uri": metaplex_data.get("uri", ""),
                "collection": metaplex_data.get("collection", {}).get("name", ""),
            }
            nft_metadata_cache[mint_address] = result
            return result
    except Exception:
        pass
    fallback = {
        "symbol": mint_address[:4] + "...",
        "name": "Unknown NFT",
        "decimals": 0,
        "icon": "",
        "uri": "",
        "collection": ""
    }
    nft_metadata_cache[mint_address] = fallback
    return fallback

async def scan_wallet(wallet_address: str, export_format: str = None, detailed: bool = False):
    print(f"🔎 Scansione wallet: {wallet_address}")
    start_time = time.time()
    try:
        try:
            pubkey = PublicKey.from_string(wallet_address)
            wallet_address_str = str(pubkey)
        except Exception as e:
            print(f"❌ Indirizzo wallet non valido: {wallet_address}: {e}")
            return None

        try:
            print(f"ℹ️ Richiesta get_balance per: {pubkey}")
            sol_balance_resp = solana_client.execute_with_retry("get_balance", pubkey)
            sol_balance = lamports_to_sol(sol_balance_resp.value)
            print(f"✅ Bilancio SOL trovato: {sol_balance}")

            print(f"ℹ️ Richiesta get_token_accounts_by_owner per: {wallet_address_str}")
            resp = solana_client.execute_with_retry(
                "get_token_accounts_by_owner",
                pubkey,
                TokenAccountOpts(program_id=PublicKey.from_string(TOKEN_PROGRAM_ID))
            )
            accounts = resp.value
            print(f"✅ Trovati {len(accounts)} token account\n")

            token_data = []
            nft_data = []
            empty_accounts = []
            total_rent_reclaimable = 0

            async with aiohttp.ClientSession() as session:
                for acc in accounts:
                    pubkey_obj = acc.pubkey
                    pubkey_str = str(pubkey_obj)
                    print(f"ℹ️ Richiesta get_account_info per: {pubkey_str}")

                    account_info_resp = solana_client.execute_with_retry(
                        "get_account_info",
                        pubkey_obj,
                        encoding="jsonParsed"
                    )
                    account_info = account_info_resp.value
                    if not account_info or "parsed" not in account_info.get("data", {}):
                        continue

                    lamports = account_info.get("lamports", 0)
                    parsed_data = account_info["data"]["parsed"]["info"]
                    mint = parsed_data["mint"]
                    amount = int(parsed_data["tokenAmount"]["amount"])
                    decimals = int(parsed_data["tokenAmount"]["decimals"])
                    ui_amount = amount / (10 ** decimals) if decimals > 0 else amount

                    if ui_amount == 0:
                        is_nft_token = await is_nft(session, mint)
                        empty_accounts.append({
                            "pubkey": pubkey_str,
                            "mint": mint,
                            "lamports": lamports,
                            "is_nft": is_nft_token
                        })
                        if not is_nft_token:
                            total_rent_reclaimable += lamports
                    else:
                        if await is_nft(session, mint):
                            metadata = await get_nft_metadata(session, mint)
                            nft_data.append({
                                "mint": mint,
                                "symbol": metadata.get("symbol", mint[:4] + "..."),
                                "name": metadata.get("name", "Unknown"),
                                "balance": ui_amount,
                                "decimals": 0,
                                "icon": metadata.get("icon", ""),
                                "uri": metadata.get("uri", ""),
                                "collection": metadata.get("collection", ""),
                            })
                        else:
                            metadata = await get_token_metadata(session, mint)
                            symbol = metadata.get("symbol", mint[:4] + "...")
                            name = metadata.get("name", "Unknown")
                            price = await get_token_price(session, mint)
                            value_usd = ui_amount * price
                            token_data.append({
                                "mint": mint,
                                "symbol": symbol,
                                "name": name,
                                "balance": ui_amount,
                                "price_usd": price,
                                "value_usd": value_usd,
                                "decimals": decimals
                            })

            token_data.sort(key=lambda x: x["value_usd"], reverse=True)
            total_value_usd = sum(t["value_usd"] for t in token_data)
            async with aiohttp.ClientSession() as session:
                sol_price = await get_token_price(session, "So11111111111111111111111111111111111111112")
            sol_value_usd = sol_balance * sol_price
            grand_total_usd = total_value_usd + sol_value_usd

            rent_reclaimable_sol = lamports_to_sol(total_rent_reclaimable) * 0.9
            rent_reclaimable_usd = lamports_to_sol(total_rent_reclaimable) * sol_price * 0.9

            report = {
                "wallet": wallet_address_str,
                "sol_balance": sol_balance,
                "sol_value_usd": sol_value_usd,
                "token_accounts": len(accounts),
                "empty_accounts": len(empty_accounts),
                "nft_accounts": len(nft_data) + sum(1 for acc in empty_accounts if acc["is_nft"]),
                "rent_reclaimable": rent_reclaimable_sol,
                "rent_reclaimable_usd": rent_reclaimable_usd,
                "tokens": token_data,
                "nfts": nft_data,
                "total_token_value_usd": total_value_usd,
                "grand_total_usd": grand_total_usd,
                "scan_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "execution_time": time.time() - start_time
            }

            print_wallet_report(report, detailed)
            if export_format:
                export_report(report, wallet_address_str, export_format)
            return report

        except Exception as e:
            print(f"❌ Errore durante la scansione: {str(e)}")
            print(traceback.format_exc())
            return None
    except Exception as e:
        print(f"❌ Errore generale: {str(e)}")
        print(traceback.format_exc())
        return None

def print_wallet_report(report: dict, detailed: bool = False):
    print(f"\n{'='*60}")
    print(f"📊 REPORT WALLET: {report['wallet']}")
    print(f"{'='*60}")
    print(f"💰 SOL Balance: {report['sol_balance']:.6f} (\${report['sol_value_usd']:.2f})")
    print(f"\n📁 STATISTICHE ACCOUNT:")
    print(f"   - Token account totali: {report['token_accounts']}")
    print(f"   - Account vuoti: {report['empty_accounts']}")
    print(f"   - Account NFT: {report['nft_accounts']}")
    print(f"   - SOL recuperabili: {report['rent_reclaimable']:.6f} (\${report['rent_reclaimable_usd']:.2f})")
    print(f"\n💎 TOKEN RESIDUI:")
    if report['tokens']:
        if detailed:
            print(f"{'SIMBOLO':<10} {'NOME':<20} {'BALANCE':<16} {'PREZZO USD':<12} {'VALORE USD':<12}")
            print(f"{'-'*10} {'-'*20} {'-'*16} {'-'*12} {'-'*12}")
            for token in report['tokens']:
                print(f"{token['symbol']:<10} {token['name'][:20]:<20} {format_number(token['balance']):<16} ${token['price_usd']:<11.6f} ${token['value_usd']:<11.2f}")
        else:
            for token in report['tokens']:
                value_str = f" (\${token['value_usd']:.2f})" if token['value_usd'] > 0 else ""
                print(f"   - {token['symbol']}: {format_number(token['balance'])}{value_str}")
    else:
        print("   Nessun token residuo trovato.")
    print(f"\n🖼️ NFT POSSEDUTI:")
    if report['nfts']:
        for nft in report['nfts']:
            print(
                f"   - {nft['name']} ({nft['symbol']}) [{nft['mint']}]"
                f"{'- Collezione: ' + nft['collection'] if nft['collection'] else ''}"
            )
    else:
        print("   Nessun NFT trovato tra i token con saldo.")
    print(f"\n💵 VALORE TOTALE:")
    print(f"   - Token: \${report['total_token_value_usd']:.2f}")
    print(f"   - SOL: \${report['sol_value_usd']:.2f}")
    print(f"   - TOTALE: \${report['grand_total_usd']:.2f}")
    print(f"\n⏱️ Scansione completata in {report['execution_time']:.2f} secondi")

def export_report(report: dict, wallet_address: str, format_type: str):
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename_base = f"solana_wallet_{wallet_address[:6]}_{timestamp}"
    try:
        if format_type.lower() == "csv":
            with open(f"{filename_base}_tokens.csv", "w", newline="", encoding="utf-8") as csvfile:
                fieldnames = ["symbol", "name", "balance", "price_usd", "value_usd", "mint"]
                writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
                writer.writeheader()
                for token in report["tokens"]:
                    writer.writerow({k: token[k] for k in fieldnames})
            with open(f"{filename_base}_nfts.csv", "w", newline="", encoding="utf-8") as csvfile:
                fieldnames = ["symbol", "name", "mint", "collection", "icon", "uri", "balance"]
                writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
                writer.writeheader()
                for nft in report["nfts"]:
                    writer.writerow({k: nft.get(k, "") for k in fieldnames})
            with open(f"{filename_base}_summary.csv", "w", newline="", encoding="utf-8") as csvfile:
                writer = csv.writer(csvfile)
                writer.writerow(["Wallet", report["wallet"]])
                writer.writerow(["SOL Balance", report["sol_balance"]])
                writer.writerow(["SOL Value USD", report["sol_value_usd"]])
                writer.writerow(["Token Accounts", report["token_accounts"]])
                writer.writerow(["Empty Accounts", report["empty_accounts"]])
                writer.writerow(["NFT Accounts", report["nft_accounts"]])
                writer.writerow(["Rent Reclaimable SOL", report["rent_reclaimable"]])
                writer.writerow(["Rent Reclaimable USD", report["rent_reclaimable_usd"]])
                writer.writerow(["Total Token Value USD", report["total_token_value_usd"]])
                writer.writerow(["Grand Total USD", report["grand_total_usd"]])
                writer.writerow(["Scan Time", report["scan_time"]])
            print(f"✅ Report esportato in: {filename_base}_tokens.csv, {filename_base}_nfts.csv e {filename_base}_summary.csv")
        elif format_type.lower() == "json":
            with open(f"{filename_base}.json", "w", encoding="utf-8") as jsonfile:
                json.dump(report, jsonfile, indent=2, default=str)
            print(f"✅ Report esportato in: {filename_base}.json")
        elif format_type.lower() == "txt":
            with open(f"{filename_base}.txt", "w", encoding="utf-8") as txtfile:
                txtfile.write(f"SOLANA WALLET REPORT\n")
                txtfile.write(f"==========================================\n")
                txtfile.write(f"Wallet: {report['wallet']}\n")
                txtfile.write(f"Scan Time: {report['scan_time']}\n\n")
                txtfile.write(f"SOL BALANCE\n")
                txtfile.write(f"------------------------------------------\n")
                txtfile.write(f"SOL: {report['sol_balance']:.6f} (\${report['sol_value_usd']:.2f})\n\n")
                txtfile.write(f"ACCOUNT STATISTICS\n")
                txtfile.write(f"------------------------------------------\n")
                txtfile.write(f"Token Accounts: {report['token_accounts']}\n")
                txtfile.write(f"Empty Accounts: {report['empty_accounts']}\n")
                txtfile.write(f"NFT Accounts: {report['nft_accounts']}\n")
                txtfile.write(f"Rent Reclaimable: {report['rent_reclaimable']:.6f} SOL (\${report['rent_reclaimable_usd']:.2f})\n\n")
                txtfile.write(f"TOKEN BALANCES\n")
                txtfile.write(f"------------------------------------------\n")
                if report['tokens']:
                    for token in report['tokens']:
                        txtfile.write(f"{token['symbol']} ({token['name']}): {format_number(token['balance'])} ")
                        if token['price_usd'] > 0:
                            txtfile.write(f"@ ${token['price_usd']:.6f} = ${token['value_usd']:.2f}\n")
                        else:
                            txtfile.write("\n")
                else:
                    txtfile.write("Nessun token residuo trovato.\n")
                txtfile.write(f"\nNFT BALANCES\n")
                txtfile.write(f"------------------------------------------\n")
                if report['nfts']:
                    for nft in report['nfts']:
                        txtfile.write(f"{nft['name']} ({nft['symbol']}): MINT: {nft['mint']} COLLEZIONE: {nft['collection']}\n")
                else:
                    txtfile.write("Nessun NFT trovato tra i token con saldo.\n")
                txtfile.write(f"\nTOTAL VALUE\n")
                txtfile.write(f"------------------------------------------\n")
                txtfile.write(f"Token Value: \${report['total_token_value_usd']:.2f}\n")
                txtfile.write(f"SOL Value: \${report['sol_value_usd']:.2f}\n")
                txtfile.write(f"TOTAL VALUE: \${report['grand_total_usd']:.2f}\n")
            print(f"✅ Report esportato in: {filename_base}.txt")
    except Exception as e:
        print(f"❌ Errore durante l'esportazione: {str(e)}")

async def batch_process(input_file: str, export_format: str = None, detailed: bool = False):
    try:
        with open(input_file, 'r') as f:
            wallets = [line.strip() for line in f if line.strip()]
        print(f"🔄 Elaborazione batch di {len(wallets)} wallet...")
        results = []
        for i, wallet in enumerate(wallets):
            print(f"\n[{i+1}/{len(wallets)}] Elaborazione wallet: {wallet}")
            result = await scan_wallet(wallet, export_format, detailed)
            if result:
                results.append(result)
            if i < len(wallets) - 1:
                await asyncio.sleep(1)
        if export_format and results:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"solana_batch_report_{timestamp}.{export_format}"
            if export_format.lower() == "json":
                with open(filename, "w") as f:
                    json.dump(results, f, indent=2, default=str)
            elif export_format.lower() == "csv":
                with open(filename, "w", newline="") as f:
                    writer = csv.writer(f)
                    writer.writerow([
                        "Wallet", "SOL Balance", "SOL Value USD", "Token Accounts", 
                        "Empty Accounts", "NFT Accounts", "Rent Reclaimable", 
                        "Rent Reclaimable USD", "Token Value USD", "Grand Total USD"
                    ])
                    for r in results:
                        writer.writerow([
                            r["wallet"], r["sol_balance"], r["sol_value_usd"],
                            r["token_accounts"], r["empty_accounts"], r["nft_accounts"],
                            r["rent_reclaimable"], r["rent_reclaimable_usd"],
                            r["total_token_value_usd"], r["grand_total_usd"]
                        ])
            print(f"✅ Report batch esportato in: {filename}")
        return results
    except Exception as e:
        print(f"❌ Errore durante l'elaborazione batch: {str(e)}")
        return None

def generate_recovery_script(wallet_address: str, output_file: str = None):
    try:
        try:
            pubkey = PublicKey.from_string(wallet_address)
            wallet_address_str = str(pubkey)
        except Exception:
            print(f"❌ Indirizzo wallet non valido: {wallet_address}")
            return

        resp = solana_client.execute_with_retry(
            "get_token_accounts_by_owner",
            pubkey,
            TokenAccountOpts(program_id=PublicKey.from_string(TOKEN_PROGRAM_ID))
        )
        accounts = resp.value
        if not accounts:
            print(f"❌ Nessun token account trovato per wallet {wallet_address_str}")
            return

        empty_accounts = []

        for acc in accounts:
            pubkey_str = str(acc.pubkey)
            acc_pub = PublicKey.from_string(pubkey_str)
            account_info_resp = solana_client.execute_with_retry(
                "get_account_info", acc_pub, encoding="jsonParsed"
            )
            account_info = account_info_resp.value
            if not account_info or "parsed" not in account_info.get("data", {}):
                continue

            parsed_data = account_info["data"]["parsed"]["info"]
            amount = int(parsed_data["tokenAmount"]["amount"])
            if amount == 0:
                empty_accounts.append(pubkey_str)

        if not empty_accounts:
            print("❌ Nessun account vuoto trovato da cui recuperare rent.")
            return

        script = "#!/usr/bin/env bash\n\n"
        script += "# Script per recuperare SOL da account token vuoti\n"
        script += f"# Generato il {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
        script += f"# Per wallet: {wallet_address_str}\n\n"
        script += "# Requisiti: Solana CLI installata e configurata\n\n"
        script += "WALLET_ADDRESS=$(solana address)\n"
        script += f'if [ "$WALLET_ADDRESS" != "{wallet_address_str}" ]; then\n'
        script += f'    echo "⚠️  ATTENZIONE: L\'indirizzo del wallet Solana CLI ($WALLET_ADDRESS) non corrisponde al wallet target ({wallet_address_str})."\n'
        script += '    read -p "Vuoi continuare? (s/n): " confirm\n'
        script += '    if [ "$confirm" != "s" ]; then\n'
        script += '        echo "Operazione annullata."\n'
        script += '        exit 1\n'
        script += '    fi\n'
        script += 'fi\n\n'
        script += f'echo "🔄 Chiusura di {len(empty_accounts)} account token vuoti..."\n\n'

        for i, account in enumerate(empty_accounts):
            script += f'echo "[{i+1}/{len(empty_accounts)}] Chiusura account: {account}"\n'
            script += f'solana close-token-account {account} --owner {wallet_address_str}\n'
            script += 'sleep 1\n\n'

        script += 'echo ""\n'
        script += 'echo "✅ Operazione completata. Verifica il tuo balance SOL."\n'

        if output_file:
            with open(output_file, "w") as f:
                f.write(script)
            os.chmod(output_file, 0o755)
            print(f"✅ Script di recupero salvato in: {output_file}")
        else:
            print("\n" + "="*60)
            print("📜 SCRIPT DI RECUPERO RENT")
            print("="*60 + "\n")
            print(script)
    except Exception as e:
        print(f"❌ Errore durante la generazione dello script: {str(e)}")
