# Deployment Guide

This guide covers deploying the WhatIf Graph application to production.

## Architecture

- **Frontend**: React + Vite (static files)
- **Backend**: Python FastAPI with FalkorDB
- **Database**: FalkorDB Cloud

## Deployment Options

### Option 1: Render (Recommended - Free tier available)

#### Deploy Backend (Render)

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

#### Deploy Frontend (Vercel)

1. Go to [vercel.com](https://vercel.com) and sign up
2. Click "Add New Project"
3. Import your GitHub repository
4. Configure:
   - **Framework Preset**: Vite
   - **Root Directory**: `artifacts/whatif-graph`
   - **Build Command**: `pnpm run build`
   - **Output Directory**: `dist`
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
