#!/bin/bash
# AI PRODUCTIVITY HACKER: DIRECT DEPLOY SCRIPT (TERMUX BYPASS)
set -e

PROJECT_NAME="orcanime"

echo "🚀 Starting Deployment for $PROJECT_NAME to Cloudflare Pages..."

echo "🔧 Patching workerd for Termux..."
find node_modules -name "main.js" -path "*/workerd/lib/main.js" -exec sed -i 's/function generateBinPath() {/function generateBinPath() { return __filename;/g' {} +

echo "🛠️  Building project with @cloudflare/next-on-pages..."
rm -rf .next .vercel
CI=true pnpm exec next-on-pages

echo "🔧 Patching next-on-pages async_hooks module resolution for Next 15..."
find .vercel/output/static/_worker.js -type f -name "*.js" -exec sed -i 's/"async_hooks"/"node:async_hooks"/g' {} +

echo "🔧 Copying hashed chunks to unhashed names to fix Next 15 static references..."
pushd .vercel/output/static/_next/static/chunks || exit 1
for file in main-app-*.js; do [ -e "$file" ] && cp "$file" "main-app.js"; done
for file in main-*.js; do [[ "$file" != main-app* ]] && cp "$file" "main.js"; done
for file in polyfills-*.js; do [ -e "$file" ] && cp "$file" "polyfills.js"; done
popd

echo "📤 Deploying to Cloudflare Pages..."
CI=true pnpm exec wrangler pages deploy .vercel/output/static --project-name $PROJECT_NAME --branch main

echo -e "\n✅ Deployment Complete! Check: https://$PROJECT_NAME.pages.dev"