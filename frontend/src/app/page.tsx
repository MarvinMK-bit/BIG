import type { Metadata } from "next";
import Image from "next/image";
import Link from "next/link";

const REPO_URL = "https://github.com/MarvinMK-bit/BIG";

export const metadata: Metadata = {
  title: "BIG — Bitcoin Incentivized Grading",
  description:
    "Mark like a chess engine. Teacher-written mark schemes, paid in sats, as a zero-marginal-cost alternative to grading every script with an LLM.",
};

const linkClass = "underline underline-offset-2 hover:text-zinc-950 dark:hover:text-white";

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section className="flex flex-col gap-4">
      <h2 className="text-xl font-semibold tracking-tight">{title}</h2>
      {children}
    </section>
  );
}

function PathCard({ name, points }: { name: string; points: [string, string][] }) {
  return (
    <div className="flex flex-col gap-3 rounded-lg border border-zinc-300 p-5 dark:border-zinc-700">
      <h3 className="font-semibold">{name}</h3>
      <dl className="flex flex-col gap-2 text-sm">
        {points.map(([label, value]) => (
          <div key={label} className="flex justify-between gap-4">
            <dt className="text-zinc-500 dark:text-zinc-400">{label}</dt>
            <dd className="text-right">{value}</dd>
          </div>
        ))}
      </dl>
    </div>
  );
}

export default function Home() {
  return (
    <main className="mx-auto flex w-full max-w-3xl flex-1 flex-col gap-16 px-4 py-12 leading-relaxed text-zinc-800 sm:px-6 sm:py-16 dark:text-zinc-200">
      <header className="flex flex-col items-center gap-6 text-center">
        <Image
          src="/images/big-logo.png"
          alt="BIG logo"
          width={1410}
          height={642}
          loading="eager"
          fetchPriority="high"
          className="h-auto w-56 rounded-lg sm:w-72"
        />
        <div className="flex flex-col gap-2">
          <h1 className="text-2xl font-semibold tracking-tight text-zinc-950 sm:text-3xl dark:text-white">
            BIG — Bitcoin Incentivized Grading
          </h1>
          <p className="text-lg text-zinc-500 dark:text-zinc-400">Mark like a chess engine</p>
        </div>
      </header>

      <section className="flex flex-col items-center gap-8 sm:flex-row sm:items-start">
        <figure className="flex w-48 shrink-0 flex-col gap-2 sm:w-56">
          <Image
            src="/images/deep-blue-cabinet.jpg"
            alt="The Deep Blue cabinet on display at the Computer History Museum"
            width={400}
            height={601}
            sizes="(min-width: 640px) 224px, 192px"
            className="h-auto w-full rounded"
          />
          <figcaption className="text-xs text-zinc-500 dark:text-zinc-400">
            Deep Blue by James the photographer, via{" "}
            <a href="https://commons.wikimedia.org/wiki/File:Deep_Blue.jpg" className={linkClass}>
              Wikimedia Commons
            </a>
            ,{" "}
            <a href="https://creativecommons.org/licenses/by/2.0/" className={linkClass}>
              CC BY 2.0
            </a>
          </figcaption>
        </figure>
        <div className="flex flex-col gap-4">
          <p>
            IBM&apos;s Deep Blue beat Garry Kasparov in 1997. It filled a cabinet, weighed over a
            tonne, and won by searching more positions than any human could.
          </p>
          <p>
            A chess engine on your phone beats any human alive today, drawing a few amps and
            searching a fraction as deep. What changed was not the search. The knowledge moved out
            of the search and into the evaluation.
          </p>
          <p className="font-semibold text-zinc-950 dark:text-white">
            Automated grading is at its Deep Blue moment.
          </p>
        </div>
      </section>

      <Section title="The problem">
        <p>
          Automated grading works, but every script costs tokens. That arithmetic does not close
          for a school marking 600 candidates across nine subjects. Cheaper models grade worse.
        </p>
      </Section>

      <Section title="The finding">
        <p>
          Given a basic rubric, GPT-3.5 scored 0.263. Given an elaborated one, it reached 0.449 —
          while the same rubric did nothing for GPT-4.
        </p>
        <blockquote className="border-l-2 border-zinc-400 pl-4 text-lg italic text-zinc-950 dark:border-zinc-500 dark:text-white">
          “Encoding the answer key benefits the weak model substantially and the strong model not
          at all.”
        </blockquote>
        <p className="text-sm">
          <a href="https://arxiv.org/abs/2407.05733" className={linkClass}>
            arXiv:2407.05733
          </a>
        </p>
      </Section>

      <Section title="Two paths">
        <div className="grid gap-4 sm:grid-cols-2">
          <PathCard
            name="LLM grader"
            points={[
              ["Cost", "Tokens per script"],
              ["Audit", "Not auditable"],
              ["Coverage", "Broad"],
            ]}
          />
          <PathCard
            name="Mark scheme"
            points={[
              ["Cost", "Zero marginal cost"],
              ["Audit", "Readable and testable"],
              ["Coverage", "Narrow but growing"],
            ]}
          />
        </div>
        <p className="text-sm text-zinc-500 dark:text-zinc-400">
          Both write the same per-question results, so the two can be compared directly.
        </p>
      </Section>

      <Section title="Bitcoin">
        <p>
          Schemes are written by teachers, who are paid in sats over Lightning: 100 sats for useful
          feedback, 500 for a scheme or a material improvement.
        </p>
      </Section>

      <Section title="Status and access">
        <p>
          BIG is at an early stage. This hosted instance is invite-only because it handles student
          work. The code is open source, and anyone may run their own.
        </p>
        <div className="flex flex-col gap-3 sm:flex-row">
          <a
            href={REPO_URL}
            className="rounded-md bg-zinc-900 px-5 py-2.5 text-center text-sm font-medium text-white hover:bg-zinc-700 dark:bg-zinc-100 dark:text-zinc-900 dark:hover:bg-zinc-300"
          >
            Read the code
          </a>
          <Link
            href="/login"
            className="rounded-md border border-zinc-400 px-5 py-2.5 text-center text-sm font-medium hover:bg-zinc-100 dark:border-zinc-600 dark:hover:bg-zinc-900"
          >
            Sign in
          </Link>
        </div>
      </Section>

      <footer className="flex flex-col gap-1 border-t border-zinc-300 pt-6 text-xs text-zinc-500 sm:flex-row sm:justify-between dark:border-zinc-700 dark:text-zinc-400">
        <span>Apache-2.0 · © 2026 Maali Marvin Kenneth</span>
        <a href={`${REPO_URL}/blob/main/docs/ARCHITECTURE.md`} className={linkClass}>
          Architecture
        </a>
      </footer>
    </main>
  );
}
