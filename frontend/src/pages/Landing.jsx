/**
 * pages/Landing.jsx
 * Marketing landing aligned with Figma Make (AION AI Research).
 * "Get Started" navigates to the research generation flow at /research.
 */

import React from 'react'
import { Link } from 'react-router-dom'

const iconClass = 'w-5 h-5 sm:w-6 sm:h-6 text-brand-600'

const IconBrain = () => (
  <svg className={iconClass} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" aria-hidden>
    <path d="M12 5a3 3 0 1 0-5.997.125 4 4 0 0 0-2.526 5.77 4 4 0 0 0 .556 6.588A4 4 0 1 0 12 18Z" />
    <path d="M12 5a3 3 0 1 1 5.997.125 4 4 0 0 1 2.526 5.77 4 4 0 0 1-.556 6.588A4 4 0 1 1 12 18Z" />
    <path d="M15 13a4.5 4.5 0 0 1-3-4 4.5 4.5 0 0 1-3 4" />
    <path d="M12 18v4" />
  </svg>
)

const IconDatabase = () => (
  <svg className={iconClass} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" aria-hidden>
    <ellipse cx="12" cy="5" rx="9" ry="3" />
    <path d="M3 5v14c0 1.66 4 3 9 3s9-1.34 9-3V5" />
    <path d="M3 12c0 1.66 4 3 9 3s9-1.34 9-3" />
  </svg>
)

const IconDatabaseLarge = () => (
  <svg className="w-8 h-8 text-brand-600 mb-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" aria-hidden>
    <ellipse cx="12" cy="5" rx="9" ry="3" />
    <path d="M3 5v14c0 1.66 4 3 9 3s9-1.34 9-3V5" />
    <path d="M3 12c0 1.66 4 3 9 3s9-1.34 9-3" />
  </svg>
)

const IconZap = () => (
  <svg className={iconClass} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" aria-hidden>
    <path d="M4 14a1 1 0 0 1-.78-1.63l9.9-10.2a.5.5 0 0 1 .86.46l-1.92 6.02A1 1 0 0 0 13 10h7a1 1 0 0 1 .78 1.63l-9.9 10.2a.5.5 0 0 1-.86-.46l1.92-6.02A1 1 0 0 0 11 14z" />
  </svg>
)

const IconTrendingUp = () => (
  <svg className="w-8 h-8 text-brand-600 mb-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" aria-hidden>
    <path d="M3 3v18h18" />
    <path d="m19 9-5 5-4-4-3 3" />
  </svg>
)

const IconGitBranch = () => (
  <svg className="w-8 h-8 text-brand-600 mb-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" aria-hidden>
    <line x1="6" y1="3" x2="6" y2="15" />
    <circle cx="18" cy="6" r="3" />
    <circle cx="6" cy="18" r="3" />
    <path d="M18 9a9 9 0 0 1-9 9" />
  </svg>
)

const IconBookOpen = () => (
  <svg className="w-8 h-8 text-brand-600 mb-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" aria-hidden>
    <path d="M2 3h6a4 4 0 0 1 4 4v14a3 3 0 0 0-3-3H2z" />
    <path d="M22 3h-6a4 4 0 0 0-4 4v14a3 3 0 0 1 3-3h7z" />
  </svg>
)

const IconArrowRight = () => (
  <svg className="w-5 h-5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden>
    <path d="M5 12h14" />
    <path d="m12 5 7 7-7 7" />
  </svg>
)

const GetStartedButton = ({ className = '' }) => (
  <Link
    to="/research"
    className={`inline-flex items-center gap-2 rounded-xl bg-brand-600 text-white px-8 py-4 font-semibold shadow-sm shadow-brand-600/25 transition-all duration-200 hover:bg-brand-700 ${className}`}
  >
    Get Started
    <IconArrowRight />
  </Link>
)

const Landing = () => {
  return (
    <div className="min-h-screen bg-ink-50">
      <main className="pt-16">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">

          <section className="py-16 sm:py-20 text-center">
            <div className="max-w-3xl mx-auto space-y-6 animate-fade-up">
              <h2 className="font-display text-4xl sm:text-5xl font-bold text-ink-900 leading-tight">
                Turn Any Topic Into a Structured Research Report
              </h2>
              <p className="text-lg sm:text-xl text-ink-600 leading-relaxed">
                AI-powered research assistant that combines semantic search, intelligent caching, and multi-source data gathering to deliver comprehensive insights in minutes.
              </p>
              <div className="pt-4">
                <GetStartedButton className="mt-2" />
              </div>
            </div>
          </section>

          <section className="py-14 sm:py-16">
            <div className="text-center mb-12">
              <h2 className="font-display text-2xl sm:text-3xl font-bold text-ink-900 mb-4">How It Works</h2>
              <p className="text-ink-600 max-w-2xl mx-auto leading-relaxed">
                Our intelligent research pipeline combines caching, AI agents, and real-time data to deliver accurate results fast.
              </p>
            </div>

            <div className="grid md:grid-cols-3 gap-8">
              <div className="space-y-4 rounded-2xl border border-ink-200 bg-white p-6 shadow-sm shadow-ink-900/5">
                <div className="w-12 h-12 bg-brand-50 rounded-xl flex items-center justify-center border border-brand-100">
                  <IconDatabase />
                </div>
                <h3 className="font-display text-lg font-semibold text-ink-900">1. Semantic Cache Lookup</h3>
                <p className="text-ink-600 text-[15px] leading-relaxed">
                  First, we check our Qdrant vector store for similar questions. If found, you get instant results from our RAG-style cache.
                </p>
              </div>

              <div className="space-y-4 rounded-2xl border border-ink-200 bg-white p-6 shadow-sm shadow-ink-900/5">
                <div className="w-12 h-12 bg-brand-50 rounded-xl flex items-center justify-center border border-brand-100">
                  <IconBrain />
                </div>
                <h3 className="font-display text-lg font-semibold text-ink-900">2. AI Agent Research</h3>
                <p className="text-ink-600 text-[15px] leading-relaxed">
                  On cache miss, our LangGraph + Gemini ReAct agent springs into action, reasoning through your question and calling specialized tools.
                </p>
              </div>

              <div className="space-y-4 rounded-2xl border border-ink-200 bg-white p-6 shadow-sm shadow-ink-900/5">
                <div className="w-12 h-12 bg-brand-50 rounded-xl flex items-center justify-center border border-brand-100">
                  <IconZap />
                </div>
                <h3 className="font-display text-lg font-semibold text-ink-900">3. Live Progress &amp; Results</h3>
                <p className="text-ink-600 text-[15px] leading-relaxed">
                  Watch the agent work in real-time, see each reasoning step, and receive your final report rendered in beautiful markdown.
                </p>
              </div>
            </div>
          </section>

          <section className="py-14 sm:py-16 rounded-2xl bg-ink-100/60 border border-ink-200/80 px-4 sm:px-8 mb-8">
            <div className="max-w-7xl mx-auto">
              <div className="text-center mb-12">
                <h2 className="font-display text-2xl sm:text-3xl font-bold text-ink-900 mb-4">Powered by Multi-Source Intelligence</h2>
                <p className="text-ink-600 max-w-2xl mx-auto leading-relaxed">
                  Our AI agent has access to a comprehensive toolkit of data sources through MCP integration.
                </p>
              </div>

              <div className="grid sm:grid-cols-2 lg:grid-cols-4 gap-6">
                <div className="bg-white p-6 rounded-xl border border-ink-200 shadow-sm">
                  <IconTrendingUp />
                  <h4 className="font-display font-semibold text-ink-900 mb-2">News &amp; Trends</h4>
                  <p className="text-sm text-ink-600 leading-relaxed">
                    Latest news articles and trending topics from multiple sources
                  </p>
                </div>

                <div className="bg-white p-6 rounded-xl border border-ink-200 shadow-sm">
                  <IconGitBranch />
                  <h4 className="font-display font-semibold text-ink-900 mb-2">GitHub</h4>
                  <p className="text-sm text-ink-600 leading-relaxed">
                    Open-source projects, code examples, and developer insights
                  </p>
                </div>

                <div className="bg-white p-6 rounded-xl border border-ink-200 shadow-sm">
                  <IconBookOpen />
                  <h4 className="font-display font-semibold text-ink-900 mb-2">arXiv</h4>
                  <p className="text-sm text-ink-600 leading-relaxed">
                    Academic papers and cutting-edge research publications
                  </p>
                </div>

                <div className="bg-white p-6 rounded-xl border border-ink-200 shadow-sm">
                  <IconDatabaseLarge />
                  <h4 className="font-display font-semibold text-ink-900 mb-2">Reddit &amp; More</h4>
                  <p className="text-sm text-ink-600 leading-relaxed">
                    Community discussions and diverse perspectives
                  </p>
                </div>
              </div>
            </div>
          </section>

          <section className="py-16 sm:py-20 text-center">
            <div className="max-w-3xl mx-auto space-y-6">
              <h2 className="font-display text-3xl sm:text-4xl font-bold text-ink-900">Ready to Start Researching?</h2>
              <p className="text-lg sm:text-xl text-ink-600 leading-relaxed">
                Get comprehensive, AI-generated research reports on any topic in minutes.
              </p>
              <GetStartedButton />
            </div>
          </section>

          <footer className="py-8 border-t border-ink-200 text-center text-sm text-ink-500">
            <p>© 2026 AION AI Research. Intelligent research at your fingertips.</p>
          </footer>
        </div>
      </main>
    </div>
  )
}

export default Landing
