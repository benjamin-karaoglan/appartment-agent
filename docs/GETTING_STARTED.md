# Getting Started with Appartment Agent

This guide will help you set up and run Appartment Agent on your local machine.

## Prerequisites

- Docker and Docker Compose
- Anthropic API key (get one at https://console.anthropic.com/)

## Quick Start with Docker

1. **Clone the repository**
   ```bash
   git clone <repository-url>
   cd appartment-agent
   ```

2. **Set up environment variables**

   Create a `.env` file in the root directory:
   ```bash
   ANTHROPIC_API_KEY=your_api_key_here
   SECRET_KEY=your-secret-key-at-least-32-characters-long
   ```

   Copy the backend environment example:
   ```bash
   cd backend
   cp .env.example .env
   # Edit .env and add your API keys
   ```

   Copy the frontend environment example:
   ```bash
   cd ../frontend
   cp .env.local.example .env.local
   ```

3. **Start the application**
   ```bash
   cd ..
   docker-compose up -d
   ```

   This will start:
   - PostgreSQL database on port 5432
   - Backend API on port 8000
   - Frontend on port 3000

4. **Access the application**
   - Frontend: http://localhost:3000
   - Backend API docs: http://localhost:8000/docs

## Local Development (Without Docker)

### Backend Setup

1. **Create a virtual environment**
   ```bash
   cd backend
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

2. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

3. **Set up PostgreSQL**
   ```bash
   # Install PostgreSQL and create a database
   createdb appartment_agent
   ```

4. **Configure environment**
   ```bash
   cp .env.example .env
   # Edit .env with your database URL and API keys
   ```

5. **Run the backend**
   ```bash
   uvicorn app.main:app --reload
   ```

### Frontend Setup

1. **Install dependencies**
   ```bash
   cd frontend
   npm install
   ```

2. **Configure environment**
   ```bash
   cp .env.local.example .env.local
   ```

3. **Run the frontend**
   ```bash
   npm run dev
   ```

## Importing DVF Data

To use the price analysis features, you need to import French DVF data:

1. **Download DVF data**

   Visit https://www.data.gouv.fr/fr/datasets/demandes-de-valeurs-foncieres/

   Download the CSV file for your desired region/year.

2. **Import the data**
   ```bash
   cd backend
   python scripts/import_dvf.py /path/to/dvf_data.csv
   ```

   This may take several minutes depending on the file size.

## First Steps

1. **Register an account**
   - Go to http://localhost:3000
   - Click "Get Started"
   - Register with your email

2. **Create a property**
   - Enter the apartment address and details
   - Input the asking price

3. **Upload documents**
   - Upload PV d'AG (assembly meeting minutes)
   - Upload diagnostic documents (DPE, amiante, plomb)
   - Upload tax and charges documents

4. **Run analysis**
   - Click "Analyze Property"
   - Wait for AI to process all documents
   - View comprehensive report and recommendations

## Troubleshooting

### Database connection issues
- Ensure PostgreSQL is running
- Check DATABASE_URL in .env file
- Verify database exists: `psql -l`

### API key errors
- Verify ANTHROPIC_API_KEY is set correctly
- Check API key has sufficient credits

### Port conflicts
- If ports 3000, 8000, or 5432 are in use, modify docker-compose.yml
- Update environment variables accordingly

## Next Steps

- Read the [API Documentation](http://localhost:8000/docs)
- Explore the features in the web interface
- Check out the [Architecture Guide](./ARCHITECTURE.md)

## Support

For issues and questions:
- Check existing GitHub issues
- Create a new issue with detailed description
- Include logs and error messages
