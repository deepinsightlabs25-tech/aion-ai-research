/**
 * App.jsx
 * Root component. Composes the Header and the Home page.
 * Dark mode is always applied (class="dark" on <html> in index.html).
 */

import React from 'react'
import Header from './components/Header'
import Home   from './pages/Home'
import { googleLogout, promptGoogleLogin } from './services/auth'
import { clearAuthToken, fetchCurrentUser, setAuthToken } from './services/api'

const AUTH_TOKEN_KEY = 'google_id_token'

const App = () => {
  const [user, setUser] = React.useState(null)
  const [isAuthLoading, setIsAuthLoading] = React.useState(true)

  const handleLogout = React.useCallback(() => {
    localStorage.removeItem(AUTH_TOKEN_KEY)
    clearAuthToken()
    googleLogout()
    setUser(null)
  }, [])

  const validateAndSetSession = React.useCallback(async (idToken) => {
    setAuthToken(idToken)
    const profile = await fetchCurrentUser()
    localStorage.setItem(AUTH_TOKEN_KEY, idToken)
    setUser(profile)
  }, [])

  React.useEffect(() => {
    let mounted = true
    const existingToken = localStorage.getItem(AUTH_TOKEN_KEY)
    if (!existingToken) {
      setIsAuthLoading(false)
      return
    }

    ;(async () => {
      try {
        await validateAndSetSession(existingToken)
      } catch {
        if (mounted) handleLogout()
      } finally {
        if (mounted) setIsAuthLoading(false)
      }
    })()

    return () => {
      mounted = false
    }
  }, [handleLogout, validateAndSetSession])

  const handleGoogleCredential = React.useCallback(
    async (credential) => {
      if (!credential) return
      setIsAuthLoading(true)
      try {
        await validateAndSetSession(credential)
      } catch {
        handleLogout()
      } finally {
        setIsAuthLoading(false)
      }
    },
    [handleLogout, validateAndSetSession],
  )

  return (
    <div className="min-h-screen font-body text-ink-800">
      <Header user={user} onGoogleCredential={handleGoogleCredential} onLogout={handleLogout} />
      <Home
        isAuthenticated={!isAuthLoading && Boolean(user)}
        onRequireLogin={() => promptGoogleLogin(handleGoogleCredential).catch(() => {})}
      />
    </div>
  )
}

export default App
