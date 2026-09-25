"use client";

import { useState } from "react";
import { FeedbackThread } from "@/components/feedback-thread";
import type { Feedback } from "@/lib/types";

// Collapsed per question; the count tracks posts made while it's open.
export function FeedbackToggle({
  resultId,
  username,
  initialItems,
}: {
  resultId: string;
  username: string;
  initialItems: Feedback[];
}) {
  const [count, setCount] = useState(initialItems.length);

  return (
    <details className="group">
      <summary className="flex min-h-9 cursor-pointer items-center text-sm underline">
        Feedback ({count})
      </summary>
      {/* Linked to from /moderation; browsers open the <details> when the fragment is inside it */}
      <div id={`feedback-${resultId}`} className="mt-2 scroll-mt-4">
        <FeedbackThread
          target={{ kind: "result", id: resultId }}
          username={username}
          initialItems={initialItems}
          onCountChange={setCount}
        />
      </div>
    </details>
  );
}
