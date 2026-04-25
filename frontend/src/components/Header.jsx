/**
 * components/Header.jsx
 * Minimal top bar with brand and status.
 */

import React from 'react'
import GoogleLoginButton from './GoogleLoginButton'

const DotPulseIcon = () => (
  <svg width="14" height="14" viewBox="0 0 24 24" fill="currentColor">
    <circle cx="12" cy="12" r="4" />
  </svg>
)

const Header = ({ user, onGoogleCredential, onLogout }) => {
  return (
    <header className="fixed top-0 left-0 right-0 z-50">
      <div className="border-b border-ink-200/70 bg-white/90 backdrop-blur-md">
        <div className="max-w-6xl mx-auto px-6 h-16 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-brand-600 flex items-center justify-center text-white shadow-sm shadow-brand-600/30">
              <svg width="18" height="18" viewBox="0 0 24 24" fill="currentColor">
                <path d="M4 5a3 3 0 0 1 3-3h6.5a3 3 0 0 1 2.4 1.2l3.5 4.67A3 3 0 0 1 20 9.67V19a3 3 0 0 1-3 3H7a3 3 0 0 1-3-3V5zm10 0v4h4" />
              </svg>
            </div>
            <div>
              <p className="font-display font-bold tracking-tight text-ink-900 text-[15px]">Research Agent</p>
              <p className="text-xs text-ink-500">AI-powered report generation</p>
            </div>
          </div>

          <div className="flex items-center gap-3">
            <div className="flex items-center gap-2 text-brand-700 bg-brand-50 border border-brand-100 rounded-full px-3.5 py-1.5">
              <span className="animate-pulse">
                <DotPulseIcon />
              </span>
              <span className="font-mono text-[11px] font-medium tracking-wider uppercase">
                Live AI
              </span>
            </div>

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
