import { Link } from 'react-router-dom'
import { useAuth } from '../../hooks/useAuth'

export function Header() {
  const { user, signOut } = useAuth()

  return (
    <header className="flex items-center justify-between px-6 py-4 bg-surface border-b border-border">
      <Link to="/scenes" className="flex items-center gap-2 no-underline">
        <span className="text-2xl font-bold text-accent">LEGO WORLDS</span>
      </Link>
      <div className="flex items-center gap-4">
        {user && (
          <>
            <span className="text-text-secondary text-sm">
              {user.user_metadata?.full_name || user.email}
            </span>
            <button
              onClick={signOut}
              className="text-sm text-text-secondary hover:text-text-primary transition-colors"
            >
              Sign out
            </button>
          </>
        )}
      </div>
    </header>
  )
}
