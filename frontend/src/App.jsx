/**
 * App.jsx
 * Root component: auth shell, header, and routed views (landing + research).
 */

import React from 'react'
import { Routes, Route } from 'react-router-dom'
import Header from './components/Header'
import Landing from './pages/Landing'
import Home from './pages/Home'
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
      <Routes>
        <Route path="/" element={<Landing />} />
        <Route
          path="/research"
          element={
            <Home
              isAuthenticated={!isAuthLoading && Boolean(user)}
              onRequireLogin={() => promptGoogleLogin(handleGoogleCredential).catch(() => {})}
            />
          }
        />
      </Routes>
    </div>
  )
}

export default App
