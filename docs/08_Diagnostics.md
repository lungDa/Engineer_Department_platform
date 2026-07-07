# 08 Enterprise Diagnostics

Developer Mode provides:

- Google Sheet
- LINE Official Account
- Render API
- AI Service

## Health Score

Checks:

- Google Sheet
- Service Account
- API Base URL
- Health Endpoint
- Ready Endpoint
- LINE Secret
- LINE Access Token
- AI Key

A score is generated to quickly identify deployment issues.

## Troubleshooting

### Google Sheet

- Verify GOOGLE_SHEET_ID
- Verify Service Account JSON
- Share spreadsheet with service account

### LINE

- Verify Channel Secret
- Verify Access Token
- Verify Webhook URL

### Render

- Check /health
- Check /ready
- Review deployment logs
