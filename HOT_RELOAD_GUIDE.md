# Hot-Reload Development Guide

Your Docker setup is **already configured** for automatic hot-reloading! This guide explains how it works and how to use it.

## Current Configuration ✅

### Backend (FastAPI)
- **File Watching**: Enabled via `--reload` flag in uvicorn
- **Volume Mount**: `./backend:/app` syncs local code to container
- **Auto-Restart**: Changes to `.py` files trigger automatic server restart (~1 second)

### Frontend (Next.js)
- **Hot Module Replacement (HMR)**: Built into Next.js dev mode
- **Volume Mount**: `./frontend:/app` syncs local code to container
- **Fast Refresh**: Updates browser instantly without full reload (~milliseconds)

## How to Start with Hot-Reload

```bash
# Start all services with hot-reload enabled
docker-compose up

# Or in detached mode (background)
docker-compose up -d

# View logs
docker-compose logs -f backend   # Backend logs
docker-compose logs -f frontend  # Frontend logs
```

## Testing Hot-Reload

### Test Backend Hot-Reload

1. **Start the services**:
   ```bash
   docker-compose up -d
   docker-compose logs -f backend
   ```

2. **Edit a Python file** (e.g., `backend/app/main.py`):
   - Add a comment or modify a log message
   - Save the file

3. **Observe the logs**:
   ```
   INFO:     Shutting down
   INFO:     Waiting for application shutdown.
   INFO:     Application shutdown complete.
   INFO:     Finished server process [X]
   INFO:     Started server process [Y]
   INFO:     Waiting for application startup.
   INFO:     Application startup complete.
   ```

   The server restarts automatically in ~1 second!

### Test Frontend Hot-Reload

1. **Start the services and open browser**:
   ```bash
   docker-compose up -d
   open http://localhost:3000
   ```

2. **Edit a React component** (e.g., `frontend/src/app/page.tsx`):
   - Change some text or styling
   - Save the file

3. **Observe the browser**:
   - Changes appear instantly (usually < 1 second)
   - No page refresh needed
   - State is preserved during updates

## What Gets Hot-Reloaded?

### Backend ✅
- Python files (`.py`)
- Configuration changes in `app/core/config.py`
- API route modifications
- Service logic updates

### Backend ❌ (Requires Restart)
- `requirements.txt` changes (new packages)
- Environment variables in `docker-compose.yml`
- Dockerfile changes
- Database schema changes (need migration)

### Frontend ✅
- React components (`.tsx`, `.jsx`)
- TypeScript files (`.ts`)
- CSS/Tailwind changes
- API client modifications
- Component state (preserved during reload)

### Frontend ❌ (Requires Restart)
- `package.json` changes (new packages)
- `next.config.js` changes
- Environment variables (`.env.local`)
- Dockerfile changes

## Troubleshooting

### Backend Not Reloading?

1. **Check logs for errors**:
   ```bash
   docker-compose logs backend
   ```

2. **Verify volume mount**:
   ```bash
   docker-compose exec backend ls -la /app/app/main.py
   # Should show recent timestamp
   ```

3. **Restart if needed**:
   ```bash
   docker-compose restart backend
   ```

### Frontend Not Reloading?

1. **Check Next.js logs**:
   ```bash
   docker-compose logs frontend
   ```

2. **Clear Next.js cache**:
   ```bash
   docker-compose exec frontend rm -rf .next
   docker-compose restart frontend
   ```

3. **Hard refresh browser**: `Cmd+Shift+R` (Mac) or `Ctrl+Shift+R` (Windows)

### Files Not Syncing?

**On macOS/Windows** (Docker Desktop):
- Volume mounts can be slow due to file system overhead
- For better performance, consider using Docker Volumes for `node_modules`:
  ```yaml
  volumes:
    - ./frontend:/app
    - /app/node_modules  # ✅ Already configured
  ```

**Permission Issues**:
```bash
# Fix permissions if needed
sudo chown -R $USER:$USER backend frontend
```

## When to Restart Containers

Restart containers when:
- Installing new Python packages (`pip install`)
- Installing new npm packages (`npm install`)
- Changing environment variables
- Modifying `docker-compose.yml`
- After pulling code with Dockerfile changes

```bash
# Rebuild and restart
docker-compose up -d --build

# Or for specific service
docker-compose up -d --build backend
```

## Performance Optimization

### Backend
The current setup is optimal:
- Multi-stage build for smaller images
- Only production dependencies in final image
- Volume mounts for development

### Frontend
The current setup is optimal:
- `node_modules` excluded from volume (faster)
- `.next` build cache excluded from volume (faster)
- Next.js Fast Refresh enabled by default

## Advanced: Debugging with Hot-Reload

### Python Debugger (pdb)
```python
# In any backend file
import pdb; pdb.set_trace()
```

Then attach to container:
```bash
docker-compose exec backend python -m pdb
```

### VS Code Remote Debugging
1. Install "Remote - Containers" extension
2. Attach to running container
3. Set breakpoints in Python/TypeScript files
4. Hot-reload works with breakpoints!

## Summary

You're **all set**! Just run:
```bash
docker-compose up
```

Then edit your code and watch it reload automatically:
- **Backend**: ~1 second restart
- **Frontend**: Instant HMR

Happy coding! 🚀
