# 🛠️ wallet-tool

Questo progetto è una web app completa per l'analisi e il recupero di fondi da wallet Solana. È costituito da un frontend React (Vite + TailwindCSS) e un backend Python Flask, con deploy automatico su Netlify.

## 📁 Struttura del progetto

wallet-tool/
├── backend/ # Flask backend con API per scansione e transazioni
│ ├── app.py
│ ├── scanner.py
│ ├── close_accounts.py
│ ├── freeze.py
│ └── templates/ # HTML fallback
│ ├── index.html
│ ├── 404.html
│ └── 500.html
├── frontend/ # React + Tailwind + Vite + Wallet Adapter
│ ├── src/
│ │ ├── App.tsx
│ │ ├── api.ts
│ │ ├── i18n.ts
│ │ ├── index.tsx
│ │ └── components/
│ │ ├── LangSwitcher.tsx
│ │ ├── Scanner.tsx
│ │ ├── WalletConnectButton.tsx
│ │ └── RecoverButton.tsx
│ ├── index.html
│ ├── index.css
│ ├── tailwind.config.js
│ ├── postcss.config.js
│ └── vite.config.ts
├── netlify.toml # Configurazione per deploy Netlify
├── requirements.txt # Dipendenze Python
└── README.md # (Questo file)

markdown
Copia
Modifica

## 🚀 Obiettivo

L'app permette di:
- Collegare un wallet Solana tramite browser
- Scansionare token, NFT e fondi disponibili
- Calcolare i SOL recuperabili
- Gestire automaticamente le operazioni di recupero tramite firma

Tutto avviene con:
- Localizzazione multilingua (Italiano e Inglese)
- UI responsive e accessibile
- Backend robusto con log e gestione errori

## 🔗 Deploy e Hosting

Il frontend viene automaticamente buildato e pubblicato su Netlify a partire dalla cartella `frontend`, usando:

```toml
[build]
base = "frontend"
command = "npm run build"
publish = "frontend/dist"
Il backend Flask viene eseguito localmente oppure su hosting separato se necessario.

✅ Note operative
Il sito è destinato all’uso pubblico ma il repository è privato

Il frontend React comunica con Flask via fetch su /api/...

Wallet compatibili: Phantom e altri con supporto @solana/wallet-adapter

Tutte le operazioni critiche richiedono firma dell’utente

📌 TODO personale
 Ottimizzare caricamento NFT (attualmente best effort via Solscan)

 Migliorare messaggi multilingua

 Integrare analytics lato admin