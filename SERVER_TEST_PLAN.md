# TGLottery server test plan — daily case

## 1. Pre-deploy

- Back up `database.db`, `.env`, certificates, and Redis data.
- Rotate any credentials that were previously stored in source code.
- Ensure the production TLS certificate is valid for the public webhook domain.
- Run locally or in CI:

  ```powershell
  python -m unittest discover -s tests -v
  python -m compileall -q .
  docker compose config --quiet
  ```

## 2. Deploy smoke test

1. Rebuild and restart:

   ```bash
   docker compose up -d --build
   docker compose ps
   docker compose logs --tail=200 bot web redis
   ```

2. Confirm that `bot`, `web`, and `redis` are healthy/running.
3. Confirm that the bot answers `/start` and the menu contains `🎁 Ежедневный кейс`.
4. Check the migrated columns in `users`:

   - `daily_case_opened_at`
   - `daily_case_notification_claimed_at`
   - `daily_case_notification_sent_at`

## 3. Case UI and cooldown

Use a dedicated Telegram test account.

1. Open the daily case and verify all three animation frames appear in one edited message.
2. Confirm the terminal result is one of: empty, diamonds, or extra dice attempts.
3. Confirm the reply-menu button changes to `⏳ Кейс (HH:MM)`.
4. Press the timer button and verify no second reward is issued.
5. Check `daily_case_opened_at` and, for a diamond result, `prize_balance` in SQLite.
6. Press the case button simultaneously from two Telegram clients. Exactly one animation/reward must start.

## 4. Dice extra-attempt test

When the case returns extra dice attempts:

1. Inspect Redis for `game:extra_attempts:dice:<telegram_id>:<YYYY-MM-DD>`.
2. Verify its value equals the won amount and has an expiry ending at the next local midnight.
3. Verify the dice game permits `base admin limit + extra attempts`.
4. Verify casino, bowling, and darts limits are unchanged.
5. After the date changes, verify the extra attempts are no longer included.

## 5. Notification test

On a staging copy of the database, set the test user's:

- `daily_case_opened_at` to more than 24 hours ago;
- `daily_case_notification_sent_at` to `NULL`;
- `daily_case_notification_claimed_at` to `NULL`.

Then:

1. Wait up to `CASE_NOTIFICATION_SCAN_SECONDS`.
2. Verify one silent message arrives: `📦 Кейс снова можно открыть!`.
3. Verify it contains `🔓 Открыть кейс` with callback `daily_case_open`.
4. Wait for at least two more scheduler intervals; no duplicate message must arrive.
5. Press the inline button and verify it starts the normal case animation directly.

## 6. Restart recovery test

1. Make a test user ready and leave `sent_at` as `NULL`.
2. Restart the bot before the next scheduler tick.
3. Verify the startup scan sends the missed notification.
4. To emulate a crashed sender, set `claimed_at` to more than 10 minutes ago and `sent_at` to `NULL`, then restart.
5. Verify the stale claim is recovered and exactly one notification is sent.

## 7. Failure-path test

1. Temporarily use an invalid test chat ID or simulate a Telegram API exception in staging.
2. Verify a transient failure clears `claimed_at`, leaves `sent_at` as `NULL`, and is retried later.
3. Verify a blocked/deleted bot chat marks the user inactive and does not retry every minute.
4. Verify a Redis failure does not write `daily_case_opened_at` or award a partial case result.

## 8. Acceptance monitoring

For the first 24–48 hours monitor:

- duplicate case rewards;
- duplicate notifications;
- `database is locked` errors;
- Redis connection/lock errors;
- Telegram `RetryAfter`, `Forbidden`, and `BadRequest` errors;
- notification claims older than 10 minutes;
- users with a ready case, `sent_at IS NULL`, and no active claim.

Production acceptance is complete only after one real 24-hour cooldown, one silent notification, one restart-recovery scenario, and one inline opening have succeeded.
