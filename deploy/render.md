# Render deployment

This repo is configured for Render through `render.yaml`.

## Service

- Name: `nathan-fergo-risk-analyst`
- Runtime: Docker
- Plan: free
- Health check: `/api/health`
- Expected URL: `https://nathan-fergo-risk-analyst.onrender.com`

## Setup

1. In Render, choose **New** then **Blueprint**.
2. Connect the GitHub repository `Nathan-Gomes/multifamily-risk-app`.
3. Render will read `render.yaml` and create the web service.
4. After the deploy finishes, open:

```text
https://nathan-fergo-risk-analyst.onrender.com
```

The app runs with generated demo data only. It does not connect to private client data, bank accounts, or accounting systems.
