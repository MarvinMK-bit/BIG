# Lightning payouts

BIG can pay owed rewards over Lightning through [Blink](https://www.blink.sv). An admin pays one
reward at a time from the **Rewards** page. There is no bulk payout, and nothing is paid
automatically.

Out of the box, payouts are **off**, and the API URL points at **Blink staging**, which uses test
sats. Paying anyone real bitcoin requires two deliberate changes, described below.

## Settings

All four live in the backend's environment (`backend/.env` locally, the host's environment
variables in production):

| Setting | Default | Meaning |
|---|---|---|
| `BLINK_API_URL` | `https://api.staging.blink.sv/graphql` | Blink's GraphQL endpoint. The default is **staging**. |
| `BLINK_API_KEY` | unset | API key from the Blink dashboard. Never commit it. |
| `BLINK_WALLET_ID` | unset | The BTC wallet payouts are sent from. |
| `PAYOUTS_ENABLED` | `false` | Master switch. Nothing is sent unless this is `true`. |

The admin section of `/rewards` shows a banner with the current state:

- **Grey:** payouts are off, or not fully configured.
- **Amber:** payouts are on against staging (test sats).
- **Red:** payouts are on against mainnet (real bitcoin), or against a URL BIG doesn't recognise.

## Why staging first

A payout can't be taken back. Staging runs the same API with test sats, so you can check the whole
path first: saving an address, pressing Pay, and seeing a failure recorded and retried. Nothing
you get wrong there costs anything. Do at least one successful and one failed payment on staging
before you switch.

## Getting a staging API key

1. Staging registration is limited. Ask for access on Blink's community chat at
   [chat.blink.sv](https://chat.blink.sv), as the
   [Blink API docs](https://dev.blink.sv/api/auth) describe. They can also tell you how to get
   test sats into a staging wallet.
2. Sign in at [dashboard.staging.blink.sv](https://dashboard.staging.blink.sv) and create an API
   key with the **Read** and **Write** scopes. Write is what allows sending. Read lets you look up
   the wallet id below.
3. Find the BTC wallet id:

   ```sh
   curl -s https://api.staging.blink.sv/graphql \
     -H "Content-Type: application/json" \
     -H "X-API-KEY: $BLINK_API_KEY" \
     -d '{"query":"query { me { defaultAccount { wallets { id walletCurrency } } } }"}'
   ```

   Use the `id` of the wallet whose `walletCurrency` is `BTC`.
4. Set `BLINK_API_KEY`, `BLINK_WALLET_ID` and `PAYOUTS_ENABLED=true`, leave `BLINK_API_URL` at its
   default, and restart the backend. The banner should turn amber and read **STAGING**.

## Switching to mainnet

> **A mainnet API key with Write permission can spend the whole balance of the wallet it belongs
> to.** Anyone who gets hold of it can send your bitcoin anywhere. Treat it like the wallet's
> private key.

Before switching:

- **Use a dedicated Blink account** for payouts, not a personal one. Keep only a small float in
  it, enough for the payouts you expect to make soon, and top it up as needed.
- **Put the key only in the host's secret environment variables**, e.g. Render's dashboard. Never
  put it in `.env.example`, `render.yaml`, a commit, a chat message or a ticket.
- **Don't reuse the staging key.** Keys are per environment. Create a new one at
  [dashboard.blink.sv](https://dashboard.blink.sv).

Then:

1. Create a mainnet key with **Read** and **Write** scopes at
   [dashboard.blink.sv](https://dashboard.blink.sv), and look up the mainnet BTC wallet id with the
   query above against `https://api.blink.sv/graphql`.
2. Set `BLINK_API_URL=https://api.blink.sv/graphql`, plus the new `BLINK_API_KEY` and
   `BLINK_WALLET_ID`, and restart.
3. Check that the banner on `/rewards` is **red** and reads **MAINNET**. From here, every Pay
   sends real bitcoin.

To stop payouts at any time, set `PAYOUTS_ENABLED=false` and restart. To be sure the key can't be
used even if it has leaked, revoke it in the Blink dashboard.

## How a payout works

Pressing **Pay** asks for confirmation (amount, address and network), then the backend does this:

1. Refuses unless the reward is still **owed**, the recipient has saved a Lightning address, and
   no earlier attempt for this reward has paid or may have paid.
2. Records an attempt as `attempting` and **commits it before calling Blink**. If the server
   crashes mid-payment, that record survives.
3. Sends the payment with Blink's `lnAddressPaymentSend` mutation.
4. Records the outcome:

| Attempt status | What it means | Reward | Can Pay again? |
|---|---|---|---|
| `success` | Blink sent it | paid; `payment_ref` is `blink:<transaction id>` | no |
| `already_paid` | Blink had already paid this; treated as success | paid | no |
| `failed` | Definitely not sent (Blink said FAILURE, or rejected the request) | owed | yes |
| `pending` | Outcome unknown: Blink said PENDING, or the call timed out or got a 5xx | owed | **no** |
| `attempting` | The server stopped mid-payment | owed | **no** |

Timeouts and server errors count as `pending`, not `failed`, because the payment may have gone
through. Retrying would risk paying twice. The database also enforces this: a reward can have at
most one attempt in a status that has paid or may have paid.

### Resolving a pending or unfinished attempt

Look up the payment in the Blink dashboard's transaction history.

- **If it went through:** use **Record payment** on the reward, with the Blink transaction id as
  the reference.
- **If it didn't:** there is no button yet to clear the stuck attempt so Pay can run again. Pay
  the person another way and record it, or ask a developer to mark the attempt `failed` in the
  database.

## What isn't supported

- **Memos.** `lnAddressPaymentSend` has no memo field, so the recipient's wallet shows no
  description. The payout service still takes a memo argument, but doesn't send it.
- **Paying several rewards at once.** This is deliberate: there is no endpoint for it.
