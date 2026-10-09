/** Original GhostOS product mark: a minimal ghost silhouette in a rounded-md tile. */
export function Logo({ size = 28 }: { size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 32 32" aria-hidden>
      <rect width="32" height="32" rx="7" fill="rgb(var(--accent))" />
      <path
        d="M9 25V15a7 7 0 0 1 14 0v10l-2.33-1.75L18.33 25 16 23.25 13.67 25l-2.34-1.75L9 25Z"
        fill="rgb(var(--bg))"
        opacity="0.92"
      />
      <circle cx="13.4" cy="15.2" r="1.35" fill="rgb(var(--accent))" />
      <circle cx="18.6" cy="15.2" r="1.35" fill="rgb(var(--accent))" />
    </svg>
  );
}
