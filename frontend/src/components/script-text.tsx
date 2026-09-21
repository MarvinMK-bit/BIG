import { muted } from "./ui";

// A question's OCR text, monospace, with an optional label. null text means the script had no
// block for this question.
export function ScriptText({
  label,
  text,
  className = "",
}: {
  label: string | null;
  text: string | null;
  className?: string;
}) {
  return (
    <div className={`min-w-0 ${className}`}>
      {label && <p className={`mb-1 text-xs font-medium ${muted}`}>{label}</p>}
      {text !== null ? (
        <pre className="whitespace-pre-wrap break-words font-mono text-sm">{text}</pre>
      ) : (
        <p className={`text-sm italic ${muted}`}>No matching text found in the script.</p>
      )}
    </div>
  );
}
