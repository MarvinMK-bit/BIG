import { notFound } from "next/navigation";
import { muted } from "@/components/ui";
import { backendGet } from "@/lib/backend";
import type { AccessRequest, Feedback, GradingSession, Me, PendingScheme } from "@/lib/types";
import { AccessRequestList } from "./access-request-list";
import { ModerationList } from "./moderation-list";
import { SchemeReviewList, type TestSession } from "./scheme-review-list";

export default async function ModerationPage() {
  const me = await backendGet<Me>("/auth/me");
  // Admins only; everyone else gets the same 404 as any unknown page
  if (!me.is_admin) notFound();

  const [accessRequests, pending, schemes, sessions] = await Promise.all([
    backendGet<AccessRequest[]>("/access-requests"), // pending first, newest first
    backendGet<Feedback[]>("/feedback/pending"),
    backendGet<PendingScheme[]>("/grading/schemes/pending"), // newest first
    backendGet<GradingSession[]>("/grading/sessions"), // the admin's own, newest first
  ]);
  const newestFirst = pending.toSorted((a, b) => Date.parse(b.created_at) - Date.parse(a.created_at));
  // Only what the picker shows; the OCR text stays on the server
  const testSessions: TestSession[] = sessions
    .filter((s) => s.status === "completed")
    .map(({ id, original_filename, subject, created_at }) => ({ id, original_filename, subject, created_at }));

  return (
    <main className="flex flex-col gap-8">
      <header className="flex flex-col gap-1">
        <h1 className="text-xl font-semibold">Moderation</h1>
        <p className={`text-sm ${muted}`}>
          Access requests, contributed schemes and feedback awaiting review.
        </p>
      </header>

      <section className="flex flex-col gap-3">
        <div className="flex flex-col gap-1">
          <h2 className="text-lg font-semibold">Access requests</h2>
          <p className={`text-sm ${muted}`}>
            Approving creates the account with the password the applicant chose; let them know on the
            email or phone they gave. Declining creates nothing.
          </p>
        </div>
        <AccessRequestList initialItems={accessRequests} />
      </section>

      <section className="flex flex-col gap-3">
        <div className="flex flex-col gap-1">
          <h2 className="text-lg font-semibold">Schemes</h2>
          <p className={`text-sm ${muted}`}>
            Accepting a scheme admits it to BIG&apos;s public corpus. Pending and declined schemes stay
            usable for grading either way.
          </p>
        </div>
        <SchemeReviewList initialItems={schemes} sessions={testSessions} />
      </section>

      <section className="flex flex-col gap-3">
        <div className="flex flex-col gap-1">
          <h2 className="text-lg font-semibold">Feedback</h2>
          <p className={`text-sm ${muted}`}>
            Approved items appear publicly; rejected and muted ones don&apos;t.
          </p>
        </div>
        <ModerationList initialItems={newestFirst} />
      </section>
    </main>
  );
}
