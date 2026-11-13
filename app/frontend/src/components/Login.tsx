import { useState } from 'react'
import { login } from '../api'

export function Login({ onSuccess }: { onSuccess: () => void }) {
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)

  async function submit(e: React.FormEvent) {
    e.preventDefault()
    setBusy(true)
    setError(null)
    try {
      await login(username, password)
      onSuccess()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Login failed')
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="flex min-h-screen items-center justify-center px-6">
      <form
        onSubmit={submit}
        className="w-full max-w-sm rounded-2xl border border-black/5 bg-white/80 p-7 shadow-sm backdrop-blur-xl"
      >
        <h1 className="mb-1 text-lg font-semibold tracking-tight">Home Climate Control</h1>
        <p className="mb-5 text-sm text-slate-500">Sign in to continue</p>
        <label className="mb-1 block text-xs font-medium text-slate-500">Username</label>
        <input
          className="mb-3 w-full rounded-lg border border-black/10 px-3 py-2 text-sm outline-none focus:border-blue-400"
          value={username}
          onChange={(e) => setUsername(e.target.value)}
          autoComplete="username"
          autoFocus
        />
        <label className="mb-1 block text-xs font-medium text-slate-500">Password</label>
        <input
          type="password"
          className="mb-4 w-full rounded-lg border border-black/10 px-3 py-2 text-sm outline-none focus:border-blue-400"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          autoComplete="current-password"
        />
        {error && <div className="mb-3 rounded-lg bg-red-50 px-3 py-2 text-sm text-red-600">{error}</div>}
        <button
          type="submit"
          disabled={busy}
          className="w-full rounded-lg bg-[#0071e3] px-4 py-2 text-sm font-medium text-white transition hover:bg-[#0062c4] disabled:opacity-50"
        >
          {busy ? 'Signing in…' : 'Sign in'}
        </button>
      </form>
    </div>
  )
}
