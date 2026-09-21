import Link from "next/link";

export default function Home() {
  return (
    <main className="mx-auto flex w-full max-w-2xl flex-1 flex-col justify-center gap-4 p-6">
      <h1 className="text-3xl font-semibold">BIG</h1>
      <div className="flex gap-4 text-sm">
        <Link href="/login" className="underline">
          Sign in
        </Link>
        <Link href="/dashboard" className="underline">
          Dashboard
        </Link>
      </div>
    </main>
  );
}
