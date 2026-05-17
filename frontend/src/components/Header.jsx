/**
 * components/Header.jsx
 * Minimal top bar with brand and status.
 */

import React from 'react'
import { Link } from 'react-router-dom'
import GoogleLoginButton from './GoogleLoginButton'

const DotPulseIcon = () => (
  <svg width="14" height="14" viewBox="0 0 24 24" fill="currentColor">
    <circle cx="12" cy="12" r="4" />
  </svg>
)

const iconClass = 'w-5 h-5 sm:w-6 sm:h-6 text-brand-600'

const IconBrain = () => (
  <svg className={iconClass} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" aria-hidden>
    <path d="M12 5a3 3 0 1 0-5.997.125 4 4 0 0 0-2.526 5.77 4 4 0 0 0 .556 6.588A4 4 0 1 0 12 18Z" />
    <path d="M12 5a3 3 0 1 1 5.997.125 4 4 0 0 1 2.526 5.77 4 4 0 0 1-.556 6.588A4 4 0 1 1 12 18Z" />
    <path d="M15 13a4.5 4.5 0 0 1-3-4 4.5 4.5 0 0 1-3 4" />
    <path d="M12 18v4" />
  </svg>
)

const Header = ({ user, onGoogleCredential, onLogout }) => {
  return (
    <header className="fixed top-0 left-0 right-0 z-50">
      <div className="border-b border-ink-200/70 bg-white/90 backdrop-blur-md">
        <div className="max-w-6xl mx-auto px-6 h-16 flex items-center justify-between gap-4">
          <div className="flex items-center gap-4 sm:gap-6 min-w-0">
            <Link to="/" className="flex items-center gap-3 rounded-lg outline-none ring-brand-500/0 focus-visible:ring-2 focus-visible:ring-brand-500 shrink-0">
            <header className="py-8">
            <div className="flex items-center gap-3">
              <div className="w-10 h-10 rounded-xl bg-brand-600/10 flex items-center justify-center">
                <IconBrain />
              </div>
              <h1 className="font-display text-2xl font-bold tracking-tight text-ink-900">AION AI Research</h1>
            </div>
          </header>
            </Link>
          </div>

          <div className="flex items-center gap-2 sm:gap-3 shrink-0">
            {/* <div className="flex items-center gap-2 text-brand-700 bg-brand-50 border border-brand-100 rounded-full px-3.5 py-1.5">
              <span className="animate-pulse">
                <DotPulseIcon />
              </span>
              <span className="font-mono text-[11px] font-medium tracking-wider uppercase">
                Live AI
              </span>
            </div> */}

            {user ? (
              <div className="flex items-center gap-2">
                <div className="hidden sm:flex items-center gap-2 px-3 py-1.5 rounded-full border border-ink-200 bg-white">
                  {user.picture ? (
                    <img src={user.picture} alt={user.name || 'User'} className="w-5 h-5 rounded-full" />
                  ) : (
                    <div className="w-5 h-5 rounded-full bg-ink-200" />
                  )}
                  <span className="text-xs text-ink-700 max-w-[140px] truncate">{user.name || user.email || 'Signed in'}</span>
                </div>
                <button
                  type="button"
                  onClick={onLogout}
                  className="text-xs font-medium text-ink-700 border border-ink-200 rounded-full px-3 py-2 hover:bg-ink-50"
                >
                  Logout
                </button>
              </div>
            ) : (
              <GoogleLoginButton onCredential={onGoogleCredential} />
            )}
          </div>
        </div>
      </div>
    </header>
  )
}

export default Header
