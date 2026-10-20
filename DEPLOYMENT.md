# Deployment Guide

This guide covers deploying the WhatIf Graph application to production.

## Architecture

- **Frontend**: React + Vite (static files)
- **Backend**: Python FastAPI with FalkorDB
- **Database**: FalkorDB Cloud

## Pre-Deployment Setup

The frontend has been modified to work with Render by:
- Removing Replit-specific monorepo dependencies (`catalog:` protocol)
- Copying the `api-client-react` library into the frontend source
- Creating a standalone `package.json` with explicit versions
- Removing Replit-specific Vite plugins
- Configuring Tailwind CSS v3 for production builds

**Important**: The frontend now includes a copy of the API client library in `src/lib/api-client-react/`. If you update the API spec, you'll need to regenerate this file and copy it to this location.

## Deployment Options

### Option 1: Render (Recommended - Free tier available)

#### Option 1A: Using render.yaml (Automated - Recommended)

A `render.yaml` configuration file has been created in the project root for easy deployment.

**Prerequisites:**
- Push your code to GitHub
- Create a Render account at [render.com](https://render.com)

**Steps:**

1. Push your code to GitHub (ensure `render.yaml` is committed)
2. Go to [render.com](https://render.com) and sign up
3. Click "New +" → "Blueprint" (New Experience)
4. Connect your GitHub repository
5. Render will automatically detect the `render.yaml` file
6. Review the configuration and click "Apply Blueprint"
7. Render will create both services:
   - `whatif-graph-api` (Backend)
   - `whatif-graph-frontend` (Frontend)

**Environment Variables to Set in Render Dashboard:**

For the backend service (`whatif-graph-api`):
```
FALKORDB_HOST=r-6jissuruar.instance-keqdkat0a.hc-7up0crkyn.ap-south-1.aws.f2e0a955bb84.cloud
FALKORDB_PORT=65332
FALKORDB_USERNAME=falkordb
FALKORDB_PASSWORD=whatif-graph-001
FALKORDB_SSL=false
FALKORDB_GRAPH_NAME=whatif_graph
```

For the frontend service (`whatif-graph-frontend`):
```
VITE_API_URL=https://whatif-graph-api.onrender.com/api
```

After deployment, you can access:
- Backend API: `https://whatif-graph-api.onrender.com`
- Frontend: `https://whatif-graph-frontend.onrender.com`

#### Option 1B: Manual Deployment

**Deploy Backend (Render):**

1. Push your code to GitHub
2. Go to [render.com](https://render.com) and sign up
3. Click "New +" → "Web Service"
4. Connect your GitHub repository
5. Configure:
   - **Name**: whatif-graph-api
   - **Root Directory**: `artifacts/api-server`
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `python src/main.py`
   - **Python Version**: 3.11
6. Add Environment Variables:
   ```
   FALKORDB_HOST=r-6jissuruar.instance-keqdkat0a.hc-7up0crkyn.ap-south-1.aws.f2e0a955bb84.cloud
   FALKORDB_PORT=65332
   FALKORDB_USERNAME=falkordb
   FALKORDB_PASSWORD=whatif-graph-001
   FALKORDB_SSL=false
   FALKORDB_GRAPH_NAME=whatif_graph
   ```
7. Click "Deploy Web Service"
8. Copy the deployed URL (e.g., `https://whatif-graph-api.onrender.com`)

**Deploy Frontend (Render):**

1. Click "New +" → "Web Service"
2. Connect your GitHub repository
3. Configure:
   - **Name**: whatif-graph-frontend
   - **Environment**: Node
   - **Root Directory**: `artifacts/whatif-graph`
   - **Build Command**: `npm install && npm run build`
   - **Start Command**: `node server.js`
4. Add Environment Variable:
   ```
   VITE_API_URL=https://whatif-graph-api.onrender.com/api
   ```
5. Click "Deploy Web Service"
6. Your frontend will be live on Render

#### Option 1C: Backend on Render, Frontend on Vercel

**Deploy Backend (Render):**

1. Push your code to GitHub
2. Go to [render.com](https://render.com) and sign up
3. Click "New +" → "Web Service"
4. Connect your GitHub repository
5. Configure:
   - **Name**: whatif-graph-api
   - **Root Directory**: `artifacts/api-server`
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `python src/main.py`
   - **Python Version**: 3.11
6. Add Environment Variables:
   ```
   FALKORDB_HOST=r-6jissuruar.instance-keqdkat0a.hc-7up0crkyn.ap-south-1.aws.f2e0a955bb84.cloud
   FALKORDB_PORT=65332
   FALKORDB_USERNAME=falkordb
   FALKORDB_PASSWORD=whatif-graph-001
   FALKORDB_SSL=false
   FALKORDB_GRAPH_NAME=whatif_graph
   ```
7. Click "Deploy Web Service"
8. Copy the deployed URL (e.g., `https://whatif-graph-api.onrender.com`)

**Deploy Frontend (Vercel):**

1. Go to [vercel.com](https://vercel.com) and sign up
2. Click "Add New Project"
3. Import your GitHub repository
4. Configure:
   - **Framework Preset**: Vite
   - **Root Directory**: `artifacts/whatif-graph`
   - **Build Command**: `npm install --legacy-peer-deps && npm run build`
   - **Output Directory**: `dist/public`
5. Add Environment Variable:
   ```
   VITE_API_URL=https://whatif-graph-api.onrender.com/api
   ```
6. Click "Deploy"
7. Your frontend will be live on Vercel

### Option 2: Railway

#### Deploy Backend

1. Go to [railway.app](https://railway.app) and sign up
2. Click "New Project" → "Deploy from GitHub repo"
3. Select your repository
4. Add environment variables in the Variables tab
5. Railway will auto-detect Python and deploy

#### Deploy Frontend

1. Use Vercel or Netlify for frontend (static hosting)

### Option 3: Heroku

#### Deploy Backend

1. Install Heroku CLI: `npm install -g heroku`
2. Login: `heroku login`
3. Create app: `heroku create whatif-graph-api`
4. Add buildpack: `heroku buildpacks:set heroku/python`
5. Set environment variables:
   ```bash
   heroku config:set FALKORDB_HOST=r-6jissuruar.instance-keqdkat0a.hc-7up0crkyn.ap-south-1.aws.f2e0a955bb84.cloud
   heroku config:set FALKORDB_PORT=65332
   heroku config:set FALKORDB_USERNAME=falkordb
   heroku config:set FALKORDB_PASSWORD=whatif-graph-001
   heroku config:set FALKORDB_SSL=false
   heroku config:set FALKORDB_GRAPH_NAME=whatif_graph
   ```
6. Deploy: `git push heroku main`

#### Deploy Frontend

Use Vercel or Netlify as described above

### Option 4: Docker Deployment

#### Build Docker Images

**Backend Dockerfile** (create `artifacts/api-server/Dockerfile`):
```dockerfile
FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY src/ ./src/

CMD ["python", "src/main.py"]
```

**Frontend Dockerfile** (create `artifacts/whatif-graph/Dockerfile`):
```dockerfile
FROM node:18-alpine as builder

WORKDIR /app
COPY package.json pnpm-lock.yaml ./
RUN npm install -g pnpm && pnpm install
COPY . .
RUN pnpm run build

FROM nginx:alpine
COPY --from=builder /app/dist /usr/share/nginx/html
EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]
```

#### Docker Compose (create `docker-compose.yml`):
```yaml
version: '3.8'

services:
  backend:
    build: ./artifacts/api-server
    ports:
      - "8888:8888"
    environment:
      - FALKORDB_HOST=r-6jissuruar.instance-keqdkat0a.hc-7up0crkyn.ap-south-1.aws.f2e0a955bb84.cloud
      - FALKORDB_PORT=65332
      - FALKORDB_USERNAME=falkordb
      - FALKORDB_PASSWORD=whatif-graph-001
      - FALKORDB_SSL=false
      - FALKORDB_GRAPH_NAME=whatif_graph

  frontend:
    build: ./artifacts/whatif-graph
    ports:
      - "3000:80"
    depends_on:
      - backend
```

#### Deploy with Docker:

```bash
docker-compose up -d
```

### Option 5: VPS (AWS EC2, DigitalOcean, etc.)

1. Provision a VPS with Ubuntu 20.04+
2. SSH into the server
3. Install dependencies:
   ```bash
   sudo apt update
   sudo apt install python3.11 python3-pip nginx -y
   ```
4. Clone your repository
5. Install Python dependencies:
   ```bash
   cd artifacts/api-server
   pip3 install -r requirements.txt
   ```
6. Set up environment variables
7. Run backend with systemd:
   ```bash
   sudo nano /etc/systemd/system/whatif-api.service
   ```
   ```
   [Unit]
   Description=WhatIf Graph API
   After=network.target

   [Service]
   User=www-data
   WorkingDirectory=/path/to/artifacts/api-server/src
   ExecStart=/usr/bin/python3 main.py
   Restart=always

   [Install]
   WantedBy=multi-user.target
   ```
8. Enable and start service:
   ```bash
   sudo systemctl enable whatif-api
   sudo systemctl start whatif-api
   ```
9. Configure nginx as reverse proxy
10. Build and serve frontend

## Environment Variables

### Required for Backend

```bash
FALKORDB_HOST=r-6jissuruar.instance-keqdkat0a.hc-7up0crkyn.ap-south-1.aws.f2e0a955bb84.cloud
FALKORDB_PORT=65332
FALKORDB_USERNAME=falkordb
FALKORDB_PASSWORD=whatif-graph-001
FALKORDB_SSL=false
FALKORDB_GRAPH_NAME=whatif_graph
```

### Required for Frontend

```bash
VITE_API_URL=https://your-backend-url.com/api
```

### Optional (AI Features)

```bash
OPENAI_API_KEY=your-openai-api-key
OPENAI_BASE_URL=https://api.openai.com/v1
OPENAI_MODEL=gpt-5-nano
```

## Security Notes

⚠️ **IMPORTANT**:
- Never commit `.env` files to version control
- Use your deployment platform's secret management
- Enable SSL/TLS in production
- Use environment-specific configuration
- Set up proper CORS origins (not `*`)
- Add rate limiting for API endpoints
- Implement authentication if needed

## Troubleshooting

### Backend Won't Start

1. Check environment variables are set correctly
2. Verify FalkorDB connection details
3. Check logs: `heroku logs --tail` (Heroku) or `journalctl -u whatif-api` (systemd)
4. Ensure port is not already in use

### Frontend Can't Connect to API

1. Verify `VITE_API_URL` is correct
2. Check CORS configuration in backend
3. Ensure backend is accessible
4. Check browser console for errors

### FalkorDB Connection Issues

1. Verify host, port, username, password
2. Check if SSL is required
3. Test connection with FalkorDB CLI
4. Check firewall/security group settings

## Monitoring

Set up monitoring for:
- API response times
- Error rates
- Database connection health
- Uptime

Recommended tools:
- Uptime monitoring: UptimeRobot, Pingdom
- APM: New Relic, Datadog
- Logging: LogRocket, Sentry

## Backup Strategy

- FalkorDB handles data replication
- Consider periodic graph exports
- Keep `.env.example` updated with all required variables
- Document your deployment configuration
