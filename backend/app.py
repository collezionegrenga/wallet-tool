from flask import Flask, render_template, request, jsonify, Response
from flask_cors import CORS
import asyncio
import sys
import json
import os
import time
from datetime import datetime
import threading
import logging
from typing import Dict, Any, Optional
import base64

# Configurazione logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("app.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("wallet-scanner")

# Importa le funzioni principali dal modulo scanner.py
from scanner import scan_wallet, batch_process, generate_recovery_script
from close_accounts import build_close_accounts_tx

app = Flask(__name__, template_folder='templates', static_folder='static')
CORS(app)

# === CACHE E RATE LIMIT ===
scan_cache = {}
CACHE_EXPIRY = 300  # 5 minuti

request_limits = {}
MAX_REQUESTS_PER_MINUTE = 10
REQUEST_WINDOW = 60  # secondi

# === GESTORE SCANSIONI IN BACKGROUND ===
class ScanManager:
    def __init__(self):
        self.pending_scans = {}
        self.lock = threading.Lock()
    
    def get_scan_status(self, scan_id):
        with self.lock:
            return self.pending_scans.get(scan_id, {"status": "not_found"})
    
    def register_scan(self, scan_id, wallet_address):
        with self.lock:
            self.pending_scans[scan_id] = {
                "status": "pending",
                "wallet": wallet_address,
                "start_time": time.time(),
                "result": None,
                "error": None
            }
        # Avvia thread per la scansione
        threading.Thread(
            target=self._run_scan_thread,
            args=(scan_id, wallet_address),
            daemon=True
        ).start()
        return scan_id
    
    def _run_scan_thread(self, scan_id, wallet_address):
        try:
            # Configura event loop per Windows se necessario
            if sys.platform == 'win32':
                asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            report = loop.run_until_complete(scan_wallet(wallet_address, detailed=True))
            loop.close()
            # Aggiorna stato e cache
            with self.lock:
                if report:
                    self.pending_scans[scan_id]["status"] = "completed"
                    self.pending_scans[scan_id]["result"] = report
                    scan_cache[wallet_address] = {
                        "timestamp": time.time(),
                        "data": report
                    }
                else:
                    self.pending_scans[scan_id]["status"] = "failed"
                    self.pending_scans[scan_id]["error"] = "Scansione fallita"
        except Exception as e:
            logger.error(f"Errore durante la scansione {scan_id}: {str(e)}")
            with self.lock:
                self.pending_scans[scan_id]["status"] = "failed"
                self.pending_scans[scan_id]["error"] = str(e)

scan_manager = ScanManager()

@app.before_request
def limit_request_rate():
    """Limita le richieste per indirizzo IP"""
    ip = request.remote_addr
    current_time = time.time()
    # Pulisci vecchie richieste
    if ip in request_limits:
        request_limits[ip] = [timestamp for timestamp in request_limits[ip] 
                             if current_time - timestamp < REQUEST_WINDOW]
    else:
        request_limits[ip] = []
    # Controlla limite
    if len(request_limits[ip]) >= MAX_REQUESTS_PER_MINUTE:
        return jsonify({
            "error": "Troppe richieste. Riprova tra qualche minuto."
        }), 429
    # Registra richiesta
    request_limits[ip].append(current_time)

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/scan", methods=["POST"])
def scan():
    """Avvia una scansione asincrona"""
    wallet_address = request.form.get("wallet")
    wallet_type = request.form.get("type", "solana")
    if not wallet_address:
        return jsonify({"error": "Nessun wallet inserito"}), 400
    if wallet_type not in ["solana", "coinbase"]:
        return jsonify({"error": "Tipo wallet non supportato"}), 400
    if wallet_type == "coinbase":
        return jsonify({"error": "Supporto Coinbase in arrivo. Al momento solo Solana/Phantom."}), 400
    # Usa la cache se disponibile
    if wallet_address in scan_cache:
        cache_entry = scan_cache[wallet_address]
        if time.time() - cache_entry["timestamp"] < CACHE_EXPIRY:
            logger.info(f"Risultato in cache per {wallet_address}")
            return jsonify({
                "status": "completed",
                "cached": True,
                "result": cache_entry["data"]
            })
    # Genera ID scansione
    scan_id = f"{int(time.time())}-{wallet_address[:8]}"
    scan_manager.register_scan(scan_id, wallet_address)
    return jsonify({
        "status": "pending",
        "scan_id": scan_id,
        "message": "Scansione avviata. Usa l'endpoint /status per controllare lo stato."
    })

@app.route("/status/<scan_id>", methods=["GET"])
def check_status(scan_id):
    """Controlla lo stato di una scansione"""
    status = scan_manager.get_scan_status(scan_id)
    if status["status"] == "not_found":
        return jsonify({"error": "Scansione non trovata"}), 404
    response = {
        "status": status["status"],
        "wallet": status["wallet"],
        "elapsed": round(time.time() - status["start_time"], 2)
    }
    if status["status"] == "completed":
        response["result"] = status["result"]
    elif status["status"] == "failed":
        response["error"] = status["error"]
    return jsonify(response)

@app.route("/batch", methods=["POST"])
def batch_scan():
    """Endpoint per scansione batch"""
    if "file" not in request.files:
        return jsonify({"error": "Nessun file caricato"}), 400
    file = request.files["file"]
    if file.filename == "":
        return jsonify({"error": "Nessun file selezionato"}), 400
    temp_path = f"temp_batch_{int(time.time())}.txt"
    file.save(temp_path)
    try:
        if sys.platform == 'win32':
            asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        export_format = request.form.get("export_format", "json")
        detailed = request.form.get("detailed", "false").lower() == "true"
        results = loop.run_until_complete(batch_process(temp_path, export_format, detailed))
        loop.close()
        os.remove(temp_path)
        if not results:
            return jsonify({"error": "Nessun risultato dalla scansione batch"}), 500
        return jsonify({
            "status": "completed",
            "wallets_processed": len(results),
            "results": results
        })
    except Exception as e:
        logger.error(f"Errore durante la scansione batch: {str(e)}")
        if os.path.exists(temp_path):
            os.remove(temp_path)
        return jsonify({"error": str(e)}), 500

@app.route("/recovery", methods=["POST"])
def generate_recovery():
    """Genera script di recupero rent"""
    wallet_address = request.form.get("wallet")
    if not wallet_address:
        return jsonify({"error": "Nessun wallet inserito"}), 400
    try:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"recovery_{wallet_address[:8]}_{timestamp}.sh"
        filepath = os.path.join("static", "scripts", filename)
        os.makedirs(os.path.dirname(filepath), exist_ok=True)
        generate_recovery_script(wallet_address, filepath)
        script_url = f"/static/scripts/{filename}"
        return jsonify({
            "status": "completed",
            "script_url": script_url,
            "message": "Script di recupero generato con successo"
        })
    except Exception as e:
        logger.error(f"Errore durante la generazione dello script: {str(e)}")
        return jsonify({"error": str(e)}), 500

@app.route("/download/<path:filename>")
def download_file(filename):
    """Download di file generati"""
    directory = os.path.join(app.root_path, "static", "scripts")
    return Response(
        open(os.path.join(directory, filename), 'rb').read(),
        mimetype="text/plain",
        headers={"Content-Disposition": f"attachment;filename={filename}"}
    )

@app.errorhandler(404)
def page_not_found(e):
    return render_template("404.html"), 404

@app.errorhandler(500)
def server_error(e):
    return render_template("500.html"), 500

@app.route("/api/scan/<wallet>", methods=["GET"])
def api_scan(wallet):
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    data = loop.run_until_complete(scan_wallet(wallet, export_format="", detailed=False))
    if not data:
        return jsonify({"error": "Scan failed"}), 400
    reclaimable_lamports = int(data.get("rent_reclaimable", 0) * 1_000_000_000)
    reclaimable_sol = round(reclaimable_lamports * 0.9 / 1_000_000_000, 6)
    return jsonify({
        "sol_balance": data.get("sol_balance", 0),
        "tokens": data.get("tokens", []),
        "nfts": data.get("nfts", []),
        "empty_accounts": [acc["pubkey"] for acc in data.get("empty_accounts", []) if not acc.get("is_nft")],
        "reclaimable_lamports": reclaimable_lamports,
        "reclaimable_sol": reclaimable_sol
    })

@app.route("/api/close", methods=["POST"])
def api_close():
    req = request.get_json()
    user_pubkey = req.get("user_pubkey")
    empty_accounts = req.get("empty_accounts", [])
    reclaimable_lamports = req.get("reclaimable_lamports", 0)
    if not user_pubkey or not empty_accounts or not reclaimable_lamports:
        return jsonify({"error": "Missing parameters"}), 400
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    tx = loop.run_until_complete(build_close_accounts_tx(user_pubkey, empty_accounts, reclaimable_lamports))
    return jsonify(tx)

@app.route("/api/send_signed_tx", methods=["POST"])
def send_signed_tx():
    req = request.get_json()
    signed_tx = req.get("signed_tx")
    if not signed_tx:
        return jsonify({"error": "Missing signed_tx"}), 400
    try:
        from solana.rpc.async_api import AsyncClient
        from solana.rpc.types import TxOpts
        from solana.transaction import Transaction
        async def send():
            # Usa la tua endpoint Alchemy anche qui!
            async with AsyncClient("https://solana-mainnet.g.alchemy.com/v2/eY-ghQjhqRjXBuzWmmOUXn62584U3CX0") as client:
                tx_bytes = base64.b64decode(signed_tx)
                tx = Transaction.deserialize(tx_bytes)
                resp = await client.send_raw_transaction(tx.serialize(), opts=TxOpts(skip_preflight=True))
                return resp
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        resp = loop.run_until_complete(send())
        if "result" in resp:
            return jsonify({"txid": resp["result"]})
        else:
            return jsonify({"error": resp}), 400
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    os.makedirs(os.path.join(app.root_path, "static", "scripts"), exist_ok=True)
    app.run(debug=False, host="0.0.0.0", port=5000)
