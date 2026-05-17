# GitHub Pages Deployment Guide

## Overview
This guide provides step-by-step instructions to deploy the frontend on GitHub Pages.

---

## Prerequisites
- GitHub account with the repository set up
- Node.js and npm installed locally
- Git installed and configured

---

## Step 1: Repository Configuration

### 1.1 Ensure Remote Repository is Set Up
```bash
cd /workspaces/aion-ai-research
git remote -v
```
You should see origin pointing to your GitHub repository.

### 1.2 Verify the Repository Name
The `homepage` in `package.json` is set to:
```
"homepage": "https://deepinsightlabs25-tech.github.io/aion-ai-research/"
```

This matches the repository `aion-ai-research` under the organization `deepinsightlabs25-tech`.

---

## Step 2: Initial Local Build Test

Test the build locally before deploying:

```bash
cd /workspaces/aion-ai-research/frontend

# Install dependencies (if not already done)
npm install

# Build the project
npm run build

# Preview the build
npm run preview
```

If the build completes successfully without errors, you're ready to deploy.

---

## Step 3: GitHub Pages Configuration

### 3.1 GitHub Repository Settings
1. Go to your GitHub repository
2. Navigate to **Settings** → **Pages**
3. Under "Build and deployment":
   - **Source**: Select "GitHub Actions"
   - **Branch**: Keep as is (workflow will handle this)

### 3.2 Personal Access Token (Optional for gh-pages CLI)
If deploying manually with `npm run deploy`, ensure GitHub CLI is configured:
```bash
gh auth login
```

---

## Step 4: Deploy

### Option A: Automatic Deployment (Recommended)
The GitHub Actions workflow will automatically deploy when you push to the `main` branch:

```bash
cd /workspaces/aion-ai-research
git add .
git commit -m "Configure GitHub Pages deployment"
git push origin main
```

**Monitor deployment:**
1. Go to your GitHub repository
2. Click on **Actions** tab
3. Watch the "Deploy Frontend to GitHub Pages" workflow
4. Once complete, your site will be live at: `https://deepinsightlabs25-tech.github.io/aion-ai-research/`

### Option B: Manual Deployment (One-time)
If you prefer manual deployment:

```bash
cd /workspaces/aion-ai-research/frontend
npm run deploy
```

This command:
1. Builds the project
2. Creates a `dist` folder
3. Pushes the contents to the `gh-pages` branch

---

## Step 5: Verify Deployment

1. Wait 1-2 minutes for GitHub Pages to process
2. Visit your deployment URL: `https://deepinsightlabs25-tech.github.io/aion-ai-research/`
3. Check for any 404 errors or styling issues

---

## Troubleshooting

### Issue: 404 Errors on Deployed Site
**Solution:** Verify the `base` path in `vite.config.js` matches the repository name:
```javascript
base: '/aion-ai-research/',
```

### Issue: Assets Not Loading
**Solution:** Check browser console for incorrect asset paths. The base path should be prepended to all relative paths.

### Issue: GitHub Actions Workflow Fails
**Solution:**
1. Check the workflow logs in GitHub Actions tab
2. Verify `npm install` succeeds
3. Ensure Node version compatibility
4. Verify repository name in `package.json` homepage field

### Issue: GitHub Pages Branch Not Set
**Solution:**
1. Check repository Settings → Pages
2. Ensure source is set to "GitHub Actions"
3. The workflow will automatically create the `gh-pages` branch on first successful run

---

## Configuration Changes Made

### 1. Updated `vite.config.js`
Changed from:
```javascript
base: './',
```
To:
```javascript
base: '/aion-ai-research/',
```

### 2. Created GitHub Actions Workflow
File: `.github/workflows/deploy-frontend.yml`
- Automatically builds and deploys on push to `main` branch
- Handles dependency installation and build process

### 3. Existing Configuration (No Changes Needed)
- `package.json` already has correct scripts:
  - `npm run build` - Builds the project
  - `npm run deploy` - Deploys using gh-pages
  - `npm run predeploy` - Runs build before deployment
- `gh-pages` package already installed
- `.gitignore` already excludes `dist/` folder

---

## Quick Reference: Deployment Commands

```bash
# Local testing
cd frontend
npm install
npm run build
npm run preview

# Manual deployment
npm run deploy

# Push changes to GitHub (triggers automatic workflow)
git add .
git commit -m "Your message"
git push origin main
```

---

## Live Site URL
Once deployed, your frontend will be available at:
```
https://deepinsightlabs25-tech.github.io/aion-ai-research/
```

---

## Next Steps
1. Test the deployed site thoroughly
2. Set up custom domain (optional) in GitHub Pages settings
3. Configure CORS if backend API is on a different domain
4. Set up automated deployments on merge to main

