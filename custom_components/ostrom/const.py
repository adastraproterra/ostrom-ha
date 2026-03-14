"""Constants for the Ostrom integration."""

DOMAIN = "ostrom"

CONF_CLIENT_ID = "client_id"
CONF_CLIENT_SECRET = "client_secret"
CONF_ZIP_CODE = "zip_code"
CONF_ARBEITSPREIS = "arbeitspreis"
CONF_ENVIRONMENT = "environment"

ENV_PRODUCTION = "production"
ENV_SANDBOX = "sandbox"

URI_AUTH = {
    ENV_PRODUCTION: "https://production.ostrom-api.io/oauth2/token",
    ENV_SANDBOX:    "https://sandbox.ostrom-api.io/oauth2/token",
}
URI_API = {
    ENV_PRODUCTION: "https://production.ostrom-api.io",
    ENV_SANDBOX:    "https://sandbox.ostrom-api.io",
}

UPDATE_INTERVAL_MINUTES = 60
