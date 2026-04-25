# AI Research Agent — Frontend

A production-ready React frontend for generating AI-powered research papers on any topic. Built with Vite, Tailwind CSS, and a refined editorial dark-mode aesthetic.

---

## ✨ Features

- **Topic Input** — Large textarea with character limit validation, example prompts, and keyboard shortcut (⌘ Enter)
- **Loading State** — Animated skeleton + cycling status messages during generation
- **Research Result** — Markdown-rendered paper with copy, download (.md), and print-to-PDF actions
- **Error Handling** — Friendly error banners with retry flow
- **Dark Mode** — Designed exclusively in a refined dark palette
- **Responsive** — Mobile-first, works on all screen sizes
- **Smooth UX** — Fade-up animations, scroll-to-result, micro-interactions

---

## 🗂 Folder Structure

```
src/
├── components/
│   ├── Header.jsx         # Fixed top navigation
│   ├── TopicInput.jsx     # Hero input + example pills
│   ├── Loader.jsx         # Skeleton + animated status
│   └── ResearchResult.jsx # Markdown renderer + action toolbar
├── pages/
│   └── Home.jsx           # State machine: idle → loading → result/error
├── services/
│   └── api.js             # Axios client + generateResearch()
├── App.jsx
├── main.jsx
└── index.css              # Tailwind + custom CSS
```

---

## 🚀 Getting Started

### 1. Install dependencies
```bash
npm install
```

### 2. Configure environment
```bash
cp .env.example .env.local
# Edit VITE_API_BASE_URL to point to your backend
```

### 3. Run dev server
```bash
npm run dev
```

### 4. Build for production
```bash
npm run build
```

---

## 🔌 API Contract

**POST** `/api/research`

```json
// Request
{ "topic": "Impact of AI on Healthcare" }

// Response
{ "content": "# Impact of AI on Healthcare\n\n..." }
```

The `content` field must be a Markdown-formatted string.

---

## 🌐 Deployment (GitHub Pages)

1. Install the deploy helper:
   ```bash
   npm install --save-dev gh-pages
   ```
2. Build and publish:
   ```bash
   npm run deploy
   ```
3. After a successful deploy, the site will be available at:
   `https://mahendra705.github.io/research-ai-fe`

The `vite.config.js` file is already set with `base: './'`, which supports GitHub Pages.

---

## 🛠 Tech Stack

| Tool | Purpose |
|------|---------|
| React 18 | UI framework |
| Vite 5 | Build tool |
| Tailwind CSS 3 | Styling |
| Axios | HTTP client |
| React Markdown | Markdown rendering |
| remark-gfm | GFM tables/strikethrough support |

---

## 🎨 Design Decisions

- **Fonts**: Playfair Display (headings) + DM Sans (body) + JetBrains Mono (code/labels)
- **Color**: Ink palette (warm dark) with amber accents
- **Animations**: CSS-only fade-up sequences, shimmer skeletons, pulsing dot
- **Texture**: Subtle dot-grid background, glassmorphism header
