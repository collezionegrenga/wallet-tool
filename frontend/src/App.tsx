import React, { useState } from "react";
import { WalletAdapterNetwork } from "@solana/wallet-adapter-base";
import { ConnectionProvider, WalletProvider, useWallet } from "@solana/wallet-adapter-react";
import { WalletModalProvider } from "@solana/wallet-adapter-react-ui";
import { PhantomWalletAdapter, SolflareWalletAdapter } from "@solana/wallet-adapter-wallets";
import { clusterApiUrl } from "@solana/web3.js";
import LangSwitcher from "./components/LangSwitcher";
import WalletConnectButton from "./components/WalletConnectButton";
import Scanner from "./components/Scanner";
import RecoverButton from "./components/RecoverButton";
import "@solana/wallet-adapter-react-ui/styles.css";

// Contenuto principale dell'app
const AppContent: React.FC = () => {
  const { publicKey, connected } = useWallet();
  const [emptyAccounts, setEmptyAccounts] = useState<string[]>([]);
  const [reclaimableLamports, setReclaimableLamports] = useState<number>(0);
  const [scanDone, setScanDone] = useState<boolean>(false);

  const handleScan = (data: {
    emptyAccounts: string[];
    reclaimableLamports: number;
  }) => {
    setEmptyAccounts(data.emptyAccounts);
    setReclaimableLamports(data.reclaimableLamports);
    setScanDone(true);
  };

  return (
    <div className="min-h-screen bg-gray-50">
      <header className="flex justify-between items-center p-4 border-b bg-white">
        <div className="flex-1">
          <LangSwitcher />
        </div>
        <div className="flex-1 text-right">
          <WalletConnectButton />
        </div>
      </header>
      <main className="max-w-xl mx-auto mt-10 p-4 bg-white rounded shadow">
        <Scanner 
          onScan={handleScan} 
          connectedWallet={publicKey ? publicKey.toString() : ""} 
          isWalletConnected={connected}
        />
        {scanDone && (
          <RecoverButton
            emptyAccounts={emptyAccounts}
            reclaimableLamports={reclaimableLamports}
          />
        )}
      </main>
    </div>
  );
};

// Wrapper con i provider per wallet
const App: React.FC = () => {
  const network = WalletAdapterNetwork.Mainnet;
  const endpoint = clusterApiUrl(network);
  const wallets = [new PhantomWalletAdapter(), new SolflareWalletAdapter()];

  return (
    <ConnectionProvider endpoint={endpoint}>
      <WalletProvider wallets={wallets} autoConnect>
        <WalletModalProvider>
          <AppContent />
        </WalletModalProvider>
      </WalletProvider>
    </ConnectionProvider>
  );
};

export default App;
