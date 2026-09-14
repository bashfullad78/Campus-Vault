import { NavLink, Outlet, useNavigate } from 'react-router-dom'
import { logout } from '../api/client'
import { forgetLocalSession } from '../api/auth'
import { useSession } from '../hooks/useSession'
import { CoinChip } from './CoinChip'

const NAV_ITEMS = [
  { to: '/', label: 'Notes' },
  { to: '/upload', label: 'Upload' },
  { to: '/my', label: 'My uploads' },
  { to: '/wallet', label: 'Wallet' },
]

const linkClass = ({ isActive }: { isActive: boolean }) =>
  `rounded-lg px-2.5 py-1.5 text-sm transition-colors ${
    isActive
      ? 'bg-surface-raised font-semibold text-slate-100'
      : 'text-slate-400 hover:text-slate-100'
  }`

export function Layout() {
  const { user } = useSession()
  const navigate = useNavigate()

  const handleLogout = async () => {
    // Server revokes ALL of the user's tokens globally (token_invalid_before),
    // then we clear local state and bounce to /login.
    await logout()
    forgetLocalSession()
    navigate('/login', { replace: true })
  }

  return (
    <div className="flex min-h-dvh flex-col">
      <header className="sticky top-0 z-10 border-b border-line bg-page/90 backdrop-blur">
        <div className="mx-auto flex w-full max-w-5xl items-center gap-3 px-4 py-3">
          <NavLink to="/" className="mr-2 text-sm font-bold tracking-tight text-slate-100">
            College&nbsp;Uploader
          </NavLink>
          <nav className="flex items-center gap-1 overflow-x-auto">
            {NAV_ITEMS.map((item) => (
              <NavLink key={item.to} to={item.to} className={linkClass}>
                {item.label}
              </NavLink>
            ))}
          </nav>
          <div className="ml-auto flex items-center gap-2">
            <CoinChip />
            {user && (
              <button
                type="button"
                onClick={handleLogout}
                className="rounded-lg px-2.5 py-1.5 text-sm text-slate-400 transition-colors hover:text-slate-100"
                title={`Signed in as ${user.email}`}
              >
                Log out
              </button>
            )}
          </div>
        </div>
      </header>
      <main className="fade-up mx-auto w-full max-w-5xl flex-1 px-4 py-6">
        <Outlet />
      </main>
      <footer className="border-t border-line py-4 text-center text-xs text-slate-500">
        Upload a PDF → earn coins · spend coins on other students' notes
      </footer>
    </div>
  )
}
