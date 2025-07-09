import React, { useState } from "react";
import LangSwitcher from "./components/LangSwitcher";
import WalletConnectButton from "./components/WalletConnectButton";
import Scanner from "./components/Scanner";
import RecoverButton from "./components/RecoverButton";

const App: React.FC = () => {
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
        <Scanner onScan={handleScan} />
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

export default App;
