# 13 Security

## LINE

- Validate Signature
- HTTPS Only
- Store Access Token in Environment Variables

## Google

- Service Account
- Principle of Least Privilege

## API

- HTTP 403 for Invalid Signature
- HTTP 400 for Invalid Payload
- Health Endpoint
- Ready Endpoint

## Secrets

Never commit:

- .env
- Service Account JSON
- LINE Access Token
