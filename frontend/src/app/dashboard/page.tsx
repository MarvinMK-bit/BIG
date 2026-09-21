import { cookies } from "next/headers";
import { redirect } from "next/navigation";
import { API_BASE, TOKEN_COOKIE } from "@/lib/config";
import { LogoutButton } from "./logout-button";

export default async function DashboardPage() {
  const token = (await cookies()).get(TOKEN_COOKIE)?.value;
  if (!token) redirect("/login");

  const res = await fetch(`${API_BASE}/auth/me`, {
    headers: { Authorization: `Bearer ${token}` },
    cache: "no-store",
  }).catch(() => null);

  if (res?.status === 401) redirect("/login"); // expired or invalid token
  if (!res?.ok) throw new Error("Could not load the current user");

  const user: { username: string } = await res.json();

  return (
    <main className="mx-auto flex w-full max-w-2xl flex-1 flex-col justify-center gap-4 p-6">
      <h1 className="text-2xl font-semibold">Dashboard</h1>
      <p>Signed in as {user.username}</p>
      <div>
        <LogoutButton />
      </div>
    </main>
  );
}
