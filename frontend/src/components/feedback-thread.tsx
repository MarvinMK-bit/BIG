"use client";

import { useId, useState } from "react";
import { RelativeTime } from "@/components/relative-time";
import { muted } from "@/components/ui";
import { apiRequest, postJson } from "@/lib/api-client";
import {
  FEEDBACK_REWARD_SATS,
  feedbackListPath,
  type Feedback,
  type FeedbackStatus,
  type FeedbackTarget,
} from "@/lib/types";

const BADGES: Partial<Record<FeedbackStatus, [string, string]>> = {
  pending: ["awaiting review", "bg-amber-200 text-amber-900 dark:bg-amber-900 dark:text-amber-100"],
  rejected: ["rejected", "bg-red-200 text-red-900 dark:bg-red-900 dark:text-red-100"],
};

const linkButton = "min-h-9 text-sm underline disabled:opacity-50";
const field =
  "w-full rounded border border-zinc-400 bg-transparent px-3 py-2 text-base sm:text-sm dark:border-zinc-600";
const primaryButton =
  "min-h-11 rounded bg-foreground px-4 text-sm text-background disabled:opacity-50";

// Which inline form is open, if any; only one at a time.
type Open = { mode: "reply" | "edit"; id: string } | null;

export function FeedbackThread({
  target,
  username,
  initialItems,
  onCountChange,
}: {
  target: FeedbackTarget;
  // The signed-in user, to recognise their own items
  username: string;
  // Fetched by the server component, so the thread renders without a loading state
  initialItems: Feedback[];
  onCountChange?: (count: number) => void;
}) {
  const [items, setItems] = useState(initialItems);
  const [open, setOpen] = useState<Open>(null);
  const [error, setError] = useState<string | null>(null);

  async function reload() {
    const result = await apiRequest<Feedback[]>(`/api${feedbackListPath(target)}`, { method: "GET" });
    if (!result.ok) return setError(result.error);
    setError(null);
    setItems(result.data);
    onCountChange?.(result.data.length);
  }

  const ids = new Set(items.map((i) => i.id));
  // A reply whose parent the viewer can't see (e.g. muted) stands on its own
  const topLevel = items.filter((i) => i.parent_id === null || !ids.has(i.parent_id));
  const repliesTo = (id: string) => items.filter((i) => i.parent_id === id);

  const itemProps = { username, target, open, setOpen, reload };

  return (
    <div className="flex flex-col gap-4">
      {items.length === 0 ? (
        <p className={`text-sm ${muted}`}>No feedback yet.</p>
      ) : (
        <ol className="flex flex-col gap-4">
          {topLevel.map((item) => (
            <li key={item.id} className="flex flex-col gap-3">
              <FeedbackItem
                item={item}
                canReply={item.parent_id === null}
                hiddenParent={item.parent_id !== null}
                {...itemProps}
              />
              {repliesTo(item.id).length > 0 && (
                <ol className="ml-3 flex flex-col gap-3 border-l-2 border-zinc-300 pl-3 sm:ml-4 sm:pl-4 dark:border-zinc-700">
                  {repliesTo(item.id).map((reply) => (
                    <li key={reply.id}>
                      <FeedbackItem item={reply} canReply={false} hiddenParent={false} {...itemProps} />
                    </li>
                  ))}
                </ol>
              )}
            </li>
          ))}
        </ol>
      )}

      {error && (
        <p role="alert" className="text-sm text-red-600">
          {error}
        </p>
      )}

      <div className="flex flex-col gap-2 border-t border-zinc-300 pt-4 dark:border-zinc-700">
        <p className={`text-sm ${muted}`}>
          Feedback is public. Useful feedback earns {FEEDBACK_REWARD_SATS} sats once an admin approves it.
        </p>
        <Composer target={target} parentId={null} onDone={reload} />
      </div>
    </div>
  );
}

function FeedbackItem({
  item,
  canReply,
  hiddenParent,
  username,
  target,
  open,
  setOpen,
  reload,
}: {
  item: Feedback;
  canReply: boolean;
  // A reply shown on its own because its parent isn't visible
  hiddenParent: boolean;
  username: string;
  target: FeedbackTarget;
  open: Open;
  setOpen: (open: Open) => void;
  reload: () => Promise<void>;
}) {
  const badge = BADGES[item.status];
  const canEdit = item.author_username === username && item.status === "pending";
  const editing = open?.mode === "edit" && open.id === item.id;
  const replying = open?.mode === "reply" && open.id === item.id;

  async function done() {
    setOpen(null);
    await reload();
  }

  return (
    <article className="flex flex-col gap-1">
      <header className="flex flex-wrap items-baseline gap-x-2 gap-y-1 text-sm">
        <span className={`font-mono text-xs ${muted}`}>{item.public_ref}</span>
        <span className="font-medium">{item.author_username}</span>
        {item.author_context && <span className={muted}>{item.author_context}</span>}
        <span className={`text-xs ${muted}`}>
          <RelativeTime iso={item.created_at} />
          {item.edited_at && " · edited"}
        </span>
        {badge && (
          <span className={`inline-block rounded-full px-2 py-0.5 text-xs font-medium ${badge[1]}`}>
            {badge[0]}
          </span>
        )}
      </header>

      {hiddenParent && (
        <p className={`text-xs ${muted}`}>In reply to {item.parent_public_ref}</p>
      )}

      {editing ? (
        <Editor item={item} onDone={done} onCancel={() => setOpen(null)} />
      ) : (
        <p className="whitespace-pre-wrap break-words text-sm">{item.body}</p>
      )}

      {!editing && (canReply || canEdit) && (
        <div className="flex gap-4">
          {canReply && (
            <button
              onClick={() => setOpen(replying ? null : { mode: "reply", id: item.id })}
              aria-expanded={replying}
              className={linkButton}
            >
              Reply
            </button>
          )}
          {canEdit && (
            <button onClick={() => setOpen({ mode: "edit", id: item.id })} className={linkButton}>
              Edit
            </button>
          )}
        </div>
      )}

      {replying && (
        <div className="mt-1 ml-3 border-l-2 border-zinc-300 pl-3 sm:ml-4 sm:pl-4 dark:border-zinc-700">
          <Composer
            target={target}
            parentId={item.id}
            replyTo={item.public_ref}
            onDone={done}
            onCancel={() => setOpen(null)}
          />
        </div>
      )}
    </article>
  );
}

function Composer({
  target,
  parentId,
  replyTo,
  onDone,
  onCancel,
}: {
  target: FeedbackTarget;
  parentId: string | null;
  replyTo?: string;
  onDone: () => Promise<void>;
  onCancel?: () => void;
}) {
  const id = useId();
  const [body, setBody] = useState("");
  const [context, setContext] = useState("");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setSaving(true);
    const result = await postJson<Feedback>("/api/feedback", {
      target_type: target.kind === "result" ? "question_result" : "mark_scheme",
      question_result_id: target.kind === "result" ? target.id : null,
      mark_scheme_version: target.kind === "scheme" ? target.version : null,
      parent_id: parentId,
      body,
      author_context: context.trim() || null,
    });
    setSaving(false);
    if (!result.ok) return setError(result.error);
    setBody("");
    await onDone();
  }

  return (
    <form onSubmit={submit} className="flex flex-col gap-2">
      <label htmlFor={`${id}-body`} className="text-sm font-medium">
        {replyTo ? `Reply to ${replyTo}` : "Post feedback"}
      </label>
      <textarea
        id={`${id}-body`}
        value={body}
        onChange={(e) => setBody(e.target.value)}
        required
        rows={3}
        maxLength={10000}
        className={field}
      />
      <label htmlFor={`${id}-context`} className={`text-xs ${muted}`}>
        About you (optional)
      </label>
      <input
        id={`${id}-context`}
        value={context}
        onChange={(e) => setContext(e.target.value)}
        placeholder="e.g. Teacher of S3 Mathematics"
        maxLength={200}
        className={field}
      />
      <div className="flex items-center gap-4">
        <button type="submit" disabled={saving || !body.trim()} className={primaryButton}>
          {saving ? "Posting…" : replyTo ? "Post reply" : "Post feedback"}
        </button>
        {onCancel && (
          <button type="button" onClick={onCancel} className={linkButton}>
            Cancel
          </button>
        )}
      </div>
      {error && (
        <p role="alert" className="text-sm text-red-600">
          {error}
        </p>
      )}
    </form>
  );
}

function Editor({
  item,
  onDone,
  onCancel,
}: {
  item: Feedback;
  onDone: () => Promise<void>;
  onCancel: () => void;
}) {
  const [body, setBody] = useState(item.body);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setSaving(true);
    const result = await apiRequest<Feedback>(`/api/feedback/${item.id}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ body }),
    });
    setSaving(false);
    if (!result.ok) return setError(result.error);
    await onDone();
  }

  return (
    <form onSubmit={submit} className="flex flex-col gap-2">
      <textarea
        aria-label={`Edit ${item.public_ref}`}
        value={body}
        onChange={(e) => setBody(e.target.value)}
        required
        rows={3}
        maxLength={10000}
        className={field}
        autoFocus
      />
      <div className="flex items-center gap-4">
        <button type="submit" disabled={saving || !body.trim()} className={primaryButton}>
          {saving ? "Saving…" : "Save"}
        </button>
        <button type="button" onClick={onCancel} className={linkButton}>
          Cancel
        </button>
      </div>
      {error && (
        <p role="alert" className="text-sm text-red-600">
          {error}
        </p>
      )}
    </form>
  );
}
