import type { ReactNode } from 'react'

/**
 * Shared split layout for /login and /register: form on the left, short
 * brand blurb about the coin economy on the right (frontend.txt §1 — modal
 * over app was rejected; dedicated pages chosen).
 */
export function AuthShell({ children }: { children: ReactNode }) {
  return (
    <div className="flex min-h-dvh items-center justify-center px-4 py-10">
      <div className="grid w-full max-w-3xl gap-10 md:grid-cols-2 md:items-center">
        <div className="flex flex-col gap-3">
          <p className="text-lg font-bold tracking-tight text-slate-100">
            College&nbsp;Uploader
          </p>
          <p className="text-sm leading-relaxed text-slate-400">
            Share your notes, earn coins. Every PDF you upload earns{' '}
            <span className="font-semibold text-coin">+10 coins</span> — up to 5
            rewards a day. Other students' notes cost{' '}
            <span className="font-semibold text-coin">5 coins</span> each.
          </p>
          <p className="text-xs leading-relaxed text-slate-500">
            PDFs only, max 25 MB. Duplicates are rejected automatically.
          </p>
        </div>
        <div className="rounded-xl border border-line bg-surface p-6">{children}</div>
      </div>
    </div>
  )
}
