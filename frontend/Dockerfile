# Stage 1: Dependencies
FROM node:18-alpine AS deps

WORKDIR /app

# Copy only package files for better caching
# This layer is cached unless package.json or package-lock.json changes
COPY package*.json ./

# Install dependencies with npm ci for faster, reproducible builds
RUN npm ci

# Stage 2: Development
FROM node:18-alpine AS dev

WORKDIR /app

# Copy node_modules from deps stage
COPY --from=deps /app/node_modules ./node_modules

# Copy application code (this invalidates cache only when code changes)
COPY . .

EXPOSE 3000

CMD ["npm", "run", "dev"]
