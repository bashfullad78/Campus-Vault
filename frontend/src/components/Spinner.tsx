export function Spinner({ className = 'h-4 w-4' }: { className?: string }) {
  return (
    <span
      className={`inline-block animate-spin rounded-full border-2 border-slate-500 border-t-transparent ${className}`}
      role="status"
      aria-label="Loading"
    />
  )
}
