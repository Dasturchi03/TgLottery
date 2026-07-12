# Webhook deployment checklist

1. Point a public DNS name to the bot server. Do not register a raw IP address as the HTTPS callback URL.
2. Replace `bot_cert.pem` and `bot_key.pem` with a currently valid certificate and key for that DNS name (for example, Let's Encrypt).
3. Set `PUBLIC_BASE_URL`, `WEBHOOK_CERT_FILE`, `WEBHOOK_KEY_FILE`, and `WEBHOOK_PORT` in `.env`.
4. Rebuild and start the services with `docker compose up -d --build`.
5. Verify `https://<domain>/health` returns `{"status":"ok"}` without a certificate warning.
6. In CryptoBot, register `https://<domain>/<CRYPTO_WEBHOOK_SECRET>` and enable webhooks.
7. Configure pnmVPN to POST to `https://<domain>/pnmvpn/trial/credit` with the matching HMAC secret.
8. If FreeKassa is used, configure its Result URL, `FREEKASSA_MERCHANT_ID`, and `FREEKASSA_SECRET_WORD_2`.

The certificate currently present in this workspace expired on 2026-01-07 and must not be deployed.
