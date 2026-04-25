import React, { useEffect, useRef, useState } from 'react'
import { renderGoogleLoginButton } from '../services/auth'

const GoogleLoginButton = ({ onCredential }) => {
  const containerRef = useRef(null)
  const [error, setError] = useState('')

  useEffect(() => {
    let mounted = true

    renderGoogleLoginButton(containerRef.current, onCredential)
      .then(() => {
        if (mounted) setError('')
      })
      .catch((err) => {
        if (mounted) setError(err?.message || 'Google Sign-In is unavailable.')
      })

    return () => {
      mounted = false
    }
  }, [onCredential])

  if (error) {
    return (
      <button
        type="button"
        disabled
        title={error}
        className="text-xs font-medium text-ink-500 border border-ink-200 rounded-full px-4 py-2 cursor-not-allowed"
      >
        Google Login Unavailable
      </button>
    )
  }

  return <div ref={containerRef} />
}

export default GoogleLoginButton
