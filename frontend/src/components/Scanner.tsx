import React, { useState, useEffect } from "react";
import { useTranslation } from "react-i18next";
import { scanWallet } from "../api";

type ScannerProps = {
  onScan: (data: { emptyAccounts: string[]; reclaimableLamports: number }) => void;
  connectedWallet: string;
  isWalletConnected: boolean;
};

const Scanner: React.FC<ScannerProps> = ({ onScan, connectedWallet, isWalletConnected }) => {
  const { t } = useTranslation();
  const [wallet, setWallet] = useState("");
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<any>(null);
  const [error, setError] = useState("");

  // Aggiorna l'indirizzo del wallet quando viene connesso
  useEffect(() => {
    if (isWalletConnected && connectedWallet) {
      setWallet(connectedWallet);
    }
  }, [connectedWallet, isWalletConnected]);

  const handleScan = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setError("");
    setResult(null);

    try {
      // Usa l'indirizzo del wallet connesso o quello inserito manualmente
      const addressToScan = isWalletConnected ? connectedWallet : wallet;
      
      if (!addressToScan) {
        throw new Error("Nessun indirizzo wallet specificato");
      }
      
      const data = await scanWallet(addressToScan);
      setResult(data);

      // Passa i dati a RecoverButton via App.tsx
      onScan({
        emptyAccounts: data.empty_accounts || [],
        reclaimableLamports: data.reclaimable_lamports || 0,
      });
    } catch (err: any) {
      setError(t("error") + ": " + err.message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div>
      <h1 className="text-2xl font-bold mb-2">{t("title")}</h1>
      <p className="mb-4 text-gray-600">{t("subtitle")}</p>
      <form onSubmit={handleScan} className="flex gap-2 mb-4">
        {/* Mostra l'input solo se il wallet non è connesso */}
        {!isWalletConnected ? (
          <input
            type="text"
            className="flex-1 border rounded px-3 py-2"
            placeholder="Wallet address"
            value={wallet}
            onChange={e => setWallet(e.target.value)}
            required
          />
        ) : (
          <div className="flex-1 border rounded px-3 py-2 bg-gray-100">
            {connectedWallet}
          </div>
        )}
        <button
          type="submit"
          className="bg-blue-600 text-white px-4 py-2 rounded"
          disabled={loading || (isWalletConnected ? false : !wallet)}
        >
          {loading ? t("scan") + "..." : t("scan")}
        </button>
      </form>
      {error && <div className="text-red-600 mb-2">{error}</div>}
      {result && (
        <div className="bg-gray-100 rounded p-4 mt-2">
          <div><b>{t("sol_balance")}:</b> {result.sol_balance} SOL</div>
          <div><b>{t("tokens")}:</b> {result.tokens?.length || 0}</div>
          <div><b>{t("nfts")}:</b> {result.nfts?.length || 0}</div>
          <div className="text-green-700 mt-2">
            <b>{t("reclaimable")}:</b> {result.reclaimable_sol} SOL
          </div>
        </div>
      )}
    </div>
  );
};

export default Scanner;
