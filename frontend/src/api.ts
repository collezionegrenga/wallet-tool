export async function scanWallet(wallet: string) {
  const res = await fetch(`/api/scan/${wallet}`);
  if (!res.ok) throw new Error("Scan error");
  return await res.json();
}

export async function closeAccounts(user_pubkey: string, empty_accounts: string[], reclaimable_lamports: number) {
  const res = await fetch(`/api/close`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ user_pubkey, empty_accounts, reclaimable_lamports })
  });
  if (!res.ok) throw new Error("Close error");
  return await res.json();
} 