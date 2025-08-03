#!/bin/bash

echo "🚀 Deploying IndraAI API to Vercel..."

# Check if Vercel CLI is installed
if ! command -v vercel &> /dev/null; then
    echo "Installing Vercel CLI..."
    npm install -g vercel
fi

# Login to Vercel
echo "Please login to Vercel..."
vercel login

# Set environment variables
echo "Setting up environment variables..."
echo "Please set the following environment variables in Vercel:"
echo "  SUPABASE_URL"
echo "  SUPABASE_ANON_KEY"
echo "  SUPABASE_SERVICE_ROLE_KEY"
echo "  REDIS_URL (optional)"

read -p "Press enter when environment variables are set..."

# Deploy to Vercel
echo "Deploying to Vercel..."
vercel --prod

echo "✅ Deployment to Vercel completed!"
echo "🌐 Your IndraAI API is now live on Vercel"
echo ""
echo "Test your deployment:"
echo "curl https://your-deployment-url.vercel.app/health"
