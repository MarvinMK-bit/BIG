// Hands a blob to the browser as a download, without leaving the page.
export function saveBlob(blob: Blob, filename: string) {
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  a.remove();
  // Give the download a moment to start before the URL is revoked
  setTimeout(() => URL.revokeObjectURL(url), 10_000);
}

// filename*=UTF-8''… (RFC 5987) when present, so non-ASCII titles survive; else filename="…".
export function filenameFrom(disposition: string | null, fallback: string): string {
  if (!disposition) return fallback;
  const star = /filename\*\s*=\s*UTF-8''([^;]+)/i.exec(disposition);
  if (star) {
    try {
      return decodeURIComponent(star[1].trim());
    } catch {
      // fall through to the plain filename
    }
  }
  const plain = /filename\s*=\s*"([^"]+)"/i.exec(disposition);
  return plain?.[1] ?? fallback;
}
