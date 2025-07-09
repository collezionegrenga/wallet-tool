import React, { useState } from "react";
import { useTranslation } from "react-i18next";
import { closeAccounts } from "../api";
import { useWallet } from "@solana/wallet-adapter-react";
import { Connection, VersionedTransaction } from "@solana/web3.js";

type RecoverButtonProps = {
  emptyAccounts: string[];
  reclaimableLamports: number;
};

const RecoverButton: React.FC<RecoverButtonProps> = ({ emptyAccounts, reclaimableLamports }) => {
  const { t } = useTranslation();
  const { publicKey, signTransaction } = useWallet();

  const [loading, setLoading] = useState(false);
  const [done, setDone] = useState(false);
  const [error, setError] = useState("");
  const [txid, setTxid] = useState("");

  const handleRecover = async () => {
    if (!publicKey || !signTransaction) {
      setError(t("error") + ": Wallet non connesso.");
      return;
    }

    setLoading(true);
    setError("");
    setTxid("");

    try {
      const userPubkey = publicKey.toBase58();
      const res = await closeAccounts(userPubkey, emptyAccounts, reclaimableLamports);

      if (!res?.tx) throw new Error("Transazione non generata dal server");

      const connection = new Connection("https://api.mainnet-beta.solana.com");

      // Decode base64 → Uint8Array → VersionedTransaction
      const txBytes = Uint8Array.from(atob(res.tx), c => c.charCodeAt(0));
      const tx = VersionedTransaction.deserialize(txBytes);

      const signedTx = await signTransaction(tx); // Wallet adapter signer
      const sig = await connection.sendRawTransaction(signedTx.serialize());

      setTxid(sig);
      setDone(true);
    } catch (err: any) {
      console.error("Errore durante il recupero:", err);
      setError(t("error") + ": " + (err.message || String(err)));
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="mt-6">
      <button
        className="bg-green-600 text-white px-4 py-2 rounded disabled:opacity-50"
        onClick={handleRecover}
        disabled={loading || done || !publicKey || emptyAccounts.length === 0}
      >
        {done
          ? t("already_recovered")
          : loading
          ? t("recover") + "..."
          : t("recover")}
      </button>
      {error && <div className="text-red-600 mt-2">{error}</div>}
      {txid && (
        <div className="text-green-700 mt-2">
          Tx: <a
            className="underline"
            href={`https://solscan.io/tx/${txid}`}
            target="_blank"
            rel="noopener noreferrer"
          >
            {txid}
          </a>
        </div>
      )}
    </div>
  );
};

export default RecoverButton;
