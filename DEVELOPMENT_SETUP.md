# Development Setup Complete ✅

## Summary

Your development environment is now **fully configured** with automatic hot-reload for both frontend and backend!

## What's Configured

### 🔥 Hot-Reload Setup
- **Backend (FastAPI)**: Uvicorn with `--reload` flag
  - Watches all `.py` files
  - Automatic restart in ~1 second
  - Volume mount: `./backend:/app`

- **Frontend (Next.js)**: Built-in Fast Refresh
  - Instant HMR (Hot Module Replacement)
  - No page refresh needed
  - State preservation during updates
  - Volume mount: `./frontend:/app`

### 📁 Files Created/Modified

1. **[HOT_RELOAD_GUIDE.md](HOT_RELOAD_GUIDE.md)** - Complete guide to hot-reload functionality
2. **[dev.sh](dev.sh)** - Development helper script with shortcuts
3. **[.vscode/settings.json](.vscode/settings.json)** - VS Code auto-save and optimizations
4. **[README.md](README.md)** - Updated with hot-reload info
5. **[.gitignore](.gitignore)** - Modified to track VS Code settings

## Quick Start

### Option 1: Using Dev Script (Recommended)
```bash
# Start everything with hot-reload
./dev.sh start

# View logs
./dev.sh logs

# Restart specific service
./dev.sh restart backend
```

### Option 2: Direct Docker Compose
```bash
# Start all services
docker-compose up

# Or in background
docker-compose up -d

# View logs
docker-compose logs -f backend
docker-compose logs -f frontend
```

## How It Works

### When you edit a Python file:
1. Save the file (auto-save enabled in VS Code after 1 second)
2. Docker volume sync picks up the change
3. Uvicorn detects the file change
4. Server automatically restarts (~1 second)
5. Your API is updated!

### When you edit a React/TypeScript file:
1. Save the file (auto-save enabled)
2. Docker volume sync picks up the change
3. Next.js Fast Refresh detects the change
4. Browser updates instantly (< 1 second)
5. Component state is preserved!

## Testing Hot-Reload

### Test Backend
```bash
# 1. Start services and watch logs
./dev.sh start
./dev.sh logs backend

# 2. Edit backend/app/main.py
# Add a comment or change a log message

# 3. Watch the logs - you'll see:
#    "Shutting down"
#    "Started server process"
#    "Application startup complete"
```

### Test Frontend
```bash
# 1. Start services
./dev.sh start

# 2. Open http://localhost:3000 in browser

# 3. Edit frontend/src/app/page.tsx
# Change some text

# 4. Watch browser update instantly!
```

## Current Configuration

### docker-compose.yml
```yaml
backend:
  volumes:
    - ./backend:/app          # ✅ Code sync
  command: uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload  # ✅ Hot-reload

frontend:
  volumes:
    - ./frontend:/app         # ✅ Code sync
    - /app/node_modules      # ✅ Exclude (performance)
    - /app/.next             # ✅ Exclude (performance)
  command: npm run dev        # ✅ Next.js HMR
```

### VS Code Settings (.vscode/settings.json)
```json
{
  "files.autoSave": "afterDelay",      // ✅ Auto-save after 1 second
  "files.autoSaveDelay": 1000,
  "files.watcherExclude": {            // ✅ Ignore build dirs
    "**/node_modules/**": true,
    "**/.next/**": true,
    "**/__pycache__/**": true
  }
}
```

## Performance Tips

### Already Optimized ✅
1. **Multi-stage Docker builds** - Smaller images, faster rebuilds
2. **Layer caching** - Only rebuild what changed
3. **Volume exclusions** - node_modules and .next excluded from sync
4. **Auto-save configured** - 1 second delay for optimal performance

### For Faster Volume Sync (macOS/Windows)
If file sync feels slow on macOS/Windows Docker Desktop, you can:

1. **Enable VirtioFS** (Docker Desktop Settings → Experimental Features)
2. **Use native Docker volumes for dependencies**:
   ```yaml
   # Already configured in docker-compose.yml!
   volumes:
     - /app/node_modules  # ✅ Uses Docker volume (fast)
   ```

## Common Tasks

### Start Development
```bash
./dev.sh start
```

### View All Logs
```bash
./dev.sh logs
```

### View Backend Logs Only
```bash
./dev.sh logs backend
```

### Restart Backend
```bash
./dev.sh restart backend
```

### Install New Python Package
```bash
# 1. Add to backend/requirements.txt
# 2. Rebuild backend
./dev.sh rebuild backend
```

### Install New npm Package
```bash
# 1. Add to frontend/package.json or run npm install
docker-compose exec frontend npm install <package>

# 2. Rebuild frontend
./dev.sh rebuild frontend
```

### Run Database Migrations
```bash
docker-compose exec backend alembic upgrade head
```

### Access Database Shell
```bash
docker-compose exec db psql -U appartment -d appartment_agent
```

### Access Backend Shell
```bash
./dev.sh shell backend
```

## Troubleshooting

### Backend not reloading?
```bash
# Check logs for errors
./dev.sh logs backend

# Restart backend
./dev.sh restart backend

# If still not working, rebuild
./dev.sh rebuild backend
```

### Frontend not reloading?
```bash
# Check Next.js logs
./dev.sh logs frontend

# Clear Next.js cache
docker-compose exec frontend rm -rf .next
./dev.sh restart frontend

# Hard refresh browser: Cmd+Shift+R (Mac) or Ctrl+Shift+R (Windows)
```

### Port already in use?
```bash
# Stop all services
./dev.sh stop

# Check what's using the port
lsof -i :3000  # Frontend
lsof -i :8000  # Backend

# Kill the process if needed
kill -9 <PID>
```

## Next Steps

1. **Start developing**: `./dev.sh start`
2. **Open your editor**: Edit any `.py` or `.tsx` file
3. **Watch it reload**: Changes appear automatically!

## Resources

- [HOT_RELOAD_GUIDE.md](HOT_RELOAD_GUIDE.md) - Detailed hot-reload documentation
- [README.md](README.md) - Project overview and setup
- [backend/README.md](backend/README.md) - Backend-specific docs
- FastAPI Docs: https://fastapi.tiangolo.com/
- Next.js Docs: https://nextjs.org/docs

## Dev Script Help

Run `./dev.sh help` to see all available commands:
```
Commands:
    start               Start all services with hot-reload
    stop                Stop all services
    restart [service]   Restart a specific service
    rebuild [service]   Rebuild and restart service(s)
    logs [service]      Follow logs
    status              Show services status
    shell [service]     Open shell in container
    test                Test hot-reload functionality
    help                Show help message
```

---

**You're all set!** 🚀 Just run `./dev.sh start` and start coding. Changes will reload automatically!
