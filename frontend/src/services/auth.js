const GOOGLE_SCRIPT_SRC = 'https://accounts.google.com/gsi/client'
const DEFAULT_GOOGLE_CLIENT_ID = '175829896291-kurqbip4mo4h75kgnno5lr54qnef1tsl.apps.googleusercontent.com'

let googleScriptPromise = null

function loadGoogleScript() {
  if (typeof window === 'undefined') return Promise.reject(new Error('Google Sign-In is only available in the browser.'))
  if (window.google?.accounts?.id) return Promise.resolve()

  if (!googleScriptPromise) {
    googleScriptPromise = new Promise((resolve, reject) => {
      const script = document.createElement('script')
      script.src = GOOGLE_SCRIPT_SRC
      script.async = true
      script.defer = true
      script.onload = () => resolve()
      script.onerror = () => reject(new Error('Failed to load Google Sign-In SDK.'))
      document.head.appendChild(script)
    })
  }

  return googleScriptPromise
}

export function getGoogleClientId() {
  return import.meta.env.VITE_GOOGLE_CLIENT_ID || DEFAULT_GOOGLE_CLIENT_ID
}

export async function renderGoogleLoginButton(container, onCredential) {
  const clientId = getGoogleClientId()
  if (!clientId) throw new Error('VITE_GOOGLE_CLIENT_ID is missing.')
  if (!container) throw new Error('Missing Google login container.')

  await loadGoogleScript()

  window.google.accounts.id.initialize({
    client_id: clientId,
    callback: (response) => {
      if (response?.credential) onCredential(response.credential)
    },
  })

  container.innerHTML = ''
  window.google.accounts.id.renderButton(container, {
    type: 'standard',
    theme: 'outline',
    size: 'medium',
    text: 'signin_with',
    shape: 'pill',
    logo_alignment: 'left',
  })
}

export async function promptGoogleLogin(onCredential) {
  const clientId = getGoogleClientId()
  if (!clientId) throw new Error('VITE_GOOGLE_CLIENT_ID is missing.')

  await loadGoogleScript()
  window.google.accounts.id.initialize({
    client_id: clientId,
    callback: (response) => {
      if (response?.credential) onCredential(response.credential)
    },
  })
  window.google.accounts.id.prompt()
}

export function googleLogout() {
  if (window.google?.accounts?.id) {
    window.google.accounts.id.disableAutoSelect()
  }
}
