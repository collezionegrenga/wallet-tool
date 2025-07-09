import i18n from "i18next";
import { initReactI18next } from "react-i18next";

const resources = {
  it: {
    translation: {
      title: "Solana Wallet Scanner",
      subtitle: "Analizza il tuo wallet Solana: saldo, token, NFT, SOL recuperabili",
      connect: "Connetti wallet",
      disconnect: "Disconnetti",
      scan: "Scansiona",
      recover: "Recupera SOL",
      sol_balance: "Saldo SOL",
      tokens: "Token",
      nfts: "NFT",
      reclaimable: "SOL recuperabili",
      already_recovered: "Hai già recuperato i SOL inutilizzati.",
      error: "Errore",
      success: "Successo",
      lang_it: "Italiano",
      lang_en: "English"
    }
  },
  en: {
    translation: {
      title: "Solana Wallet Scanner",
      subtitle: "Analyze your Solana wallet: balance, tokens, NFTs, reclaimable SOL",
      connect: "Connect wallet",
      disconnect: "Disconnect",
      scan: "Scan",
      recover: "Recover SOL",
      sol_balance: "SOL Balance",
      tokens: "Tokens",
      nfts: "NFTs",
      reclaimable: "Reclaimable SOL",
      already_recovered: "You have already recovered unused SOL.",
      error: "Error",
      success: "Success",
      lang_it: "Italiano",
      lang_en: "English"
    }
  }
};

i18n.use(initReactI18next).init({
  resources,
  lng: "it",
  fallbackLng: "en",
  interpolation: { escapeValue: false }
});

export default i18n; 