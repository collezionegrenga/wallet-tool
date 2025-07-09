import React from "react";
import { useTranslation } from "react-i18next";
import { WalletMultiButton } from "@solana/wallet-adapter-react-ui";
import "@solana/wallet-adapter-react-ui/styles.css";

const WalletConnectButton: React.FC = () => {
  const { t } = useTranslation();
  
  return (
    <WalletMultiButton className="!bg-blue-600 !text-white" />
  );
};

export default WalletConnectButton;
