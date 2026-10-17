# Haven Medical Relief: charity website

A content and fundraising website for a medical relief charity, built with Django and the
Wagtail CMS. It shows the work (programs, emergencies, countries, stories) and turns readers
into donors (card, monthly, bank transfer, tributes, gift catalogue, supporter fundraisers).

"Haven Medical Relief" is a **placeholder name**. Every name, number, photo, bank account and
piece of text in the demo content is a sample to be replaced in the admin before launch.

The plan and task list are in [`plans/`](plans/).

---

## Quick start (local, Windows / macOS / Linux)

Requirements: Python 3.12, Node 18+.

```bash
python -m venv .venv
.venv/Scripts/pip install -r requirements-dev.txt     # macOS/Linux: .venv/bin/pip
npm install
npm run build:css                                     # or: npm run watch:css while editing templates

python manage.py migrate
python manage.py setup_roles                          # staff roles + editorial approval workflow
python manage.py seed_demo                            # sample pages, menus, settings and records
python manage.py createsuperuser                      # this is the owner's login
python manage.py runserver
```

Open http://127.0.0.1:8000 for the site and http://127.0.0.1:8000/admin/ for the owner admin.

Local development defaults (in `config/settings/dev.py`):

| Setting | Local default | Why |
|---|---|---|
| Database | SQLite (`db.sqlite3`) | No server needed. Set `DATABASE_URL` to use PostgreSQL. |
| Payments | **Test mode**: no real cards | Checkout goes to a local "Approve / Decline" page that runs the real webhook code. |
| Emails | Saved to `sent-emails/` | Open receipts, e-cards and notices as files. |
| Background jobs | Run immediately | No Redis/Celery needed locally. |
| Admin 2FA | Off | Turn on with `ADMIN_REQUIRE_2FA=true`. It is **always on** in production. |

To rebuild the demo from scratch: `python manage.py seed_demo --reset`.

---

## The owner admin (`/admin/`)

Visitors who open `/admin/` see only a login page. The owner signs in with email and password,
and in production also a 6-digit code from an authenticator app (set up on first sign-in).
The address can be moved with `ADMIN_PATH` in `.env`.

Everything visitors see is edited here:

| What | Where in the admin |
|---|---|
| Any page (text, photos, blocks, stats, FAQs, timelines) | **Pages**. Edit, preview, schedule, publish, roll back. |
| Organisation name, logo, contact details, social links, tax text, sitewide alert banner, analytics IDs | **Settings > Organisation settings** |
| Header mega menu, footer columns, legal links | **Settings > Menus** |
| **Bank account numbers shown for donations** | **Giving > Bank accounts (shown on site)** |
| Suggested amounts, minimums, which payment methods appear, thank-you and receipt wording | **Settings > Donation settings** |
| Confirm or reject "I've made a transfer" notices | **Giving > Bank transfer queue** |
| Donations, monthly gifts, refunds, receipts, CSV/Excel export | **Giving > Donations / Monthly gifts** |
| Which donate buttons raise most | **Giving > Appeals report** |
| Gift catalogue items and orders, e-cards | **Giving** |
| Approve supporters' fundraiser pages | **Giving > Fundraisers (moderation)** |
| Newsletter subscribers (export) | **Giving > Newsletter subscribers** |
| Resources, situation reports, media alerts, past emergencies, leadership people, financial reports, offices, regions, topics | **Content library** |
| Events, open tenders, jobs | **Events, tenders & jobs** |
| Staff accounts and roles | **Settings > Users / Groups** |

When a staff member is signed in, every public page shows a small Wagtail button with
**Edit this page**, which jumps straight to the editor.

### Staff roles

`python manage.py setup_roles` creates: Content Editor (drafts only, needs approval), Publisher,
Communications, Fundraising & Finance, HR, Procurement, Events. Content Editors' changes go
through the "Editorial approval" workflow to a Publisher. Only Finance and superusers see donor data.

### Bank transfer donations

1. Add your real account(s) in **Giving > Bank accounts**, and delete the two SAMPLE accounts.
2. Visitors see them in the donate pop-up's **Bank transfer** tab (with a Copy button and a
   suggested reference), on emergency pages (an account linked to an emergency is shown there
   instead), and optionally on Contact/FAQ and in the footer.
3. A donor who has paid fills in **I've made a transfer**. You get an email and the notice
   appears in **Giving > Bank transfer queue**.
4. Check your bank statement, then **Confirm received** (optionally entering the amount that
   actually arrived). That records the donation, sends the receipt and counts it in all totals.
   **Reject** emails the donor your reason.

Any change to bank details is logged and emailed to the address in Donation settings
("notify email"), because swapped account numbers are a common fraud.

### Lost authenticator phone

`python manage.py reset_2fa owner@example.org`. The person sets up 2FA again at next sign-in.

---

## Supporters' account area (`/account/`)

Supporters can sign up (email + password, email verification) or give as guests. Once their
email is verified, earlier guest gifts under that email appear in their account. They can:

- update their name, phone, address, email and password
- see every gift, download PDF receipts and a yearly giving statement
- change, pause, resume or cancel a monthly gift, and update the card
- edit or cancel scheduled e-cards until they are sent, and re-send sent ones
- create a fundraiser page (reviewed by staff before going live), edit it, post updates,
  see donors, email them a thank-you and end it
- manage newsletter preferences, download their data or delete their account

Newsletter emails carry a signed unsubscribe link that works without signing in.

---

## Payments

| Currency | Provider | Set in `.env` |
|---|---|---|
| NGN | Paystack (one-time + monthly plans) | `PAYSTACK_SECRET_KEY`, `PAYSTACK_PUBLIC_KEY` |
| USD | Stripe Checkout + Billing | `STRIPE_SECRET_KEY`, `STRIPE_PUBLISHABLE_KEY`, `STRIPE_WEBHOOK_SECRET` |
| Any | Bank transfer | Admin, as above |

Webhook URLs to register with the providers:

- Paystack: `https://YOUR-DOMAIN/payments/webhooks/paystack/`
- Stripe: `https://YOUR-DOMAIN/payments/webhooks/stripe/` (events: `checkout.session.completed`,
  `checkout.session.async_payment_succeeded`, `invoice.paid`, `invoice.payment_failed`,
  `customer.subscription.deleted`, `charge.refunded`)

Webhooks are the source of truth: a donation only becomes "succeeded" when the provider says
so. Every webhook is stored once (duplicates are ignored). Failures show in
**Giving > Payment webhook log** with a "Process again" button.

Every donate button carries an appeal code (`/donate/?appeal=HOME-HERO`). Links like
`https://YOUR-DOMAIN/any-page/?form=donate&appeal=SPRING-EMAIL` open the donate pop-up
directly, which is useful in emails and adverts. Unknown codes are recorded and flagged under
**Giving > Appeal codes**.

> **Not yet exercised against the real providers.** The Paystack and Stripe code paths are
> written to their documented APIs but were tested here only through the offline test mode.
> Before launch, run test-mode payments with real test keys and the providers' webhook
> forwarding (Stripe CLI `stripe listen`, Paystack test webhooks) — see `plans/tasks.md` 6.18.

---

## Tests

```bash
.venv/Scripts/python -m pytest
```

39 tests cover: one-time, monthly and failed donations; appeal and emergency tagging; duplicate
webhooks; renewals; bank transfer notices and confirmation; tribute e-cards (sent only after
payment, editable until sent); gift catalogue checkout; refunds; owner login and 2FA; staff
permissions; the owner adding a bank account that then appears on the site; the supporter
account area; fundraiser approval; account deletion; newsletter signup and unsubscribe; and a
render check of every page in the demo site, data export, admin cancelling a monthly gift, webhook retry, photo metadata stripping, and future-dated e-cards.

---

## Production (Docker Compose)

```bash
cp .env.example .env          # fill in real values
docker compose up -d --build
docker compose exec web python manage.py setup_roles
docker compose exec web python manage.py createsuperuser
```

Services: `web` (gunicorn), `worker` (Celery: receipts, e-cards, newsletter sync), `beat`
(sends scheduled e-cards every 5 minutes, ends expired fundraisers), `db` (PostgreSQL 16),
`redis`. Put a TLS-terminating proxy (Caddy/nginx) in front of port 8000. Uploaded media lives
in the `media` volume, or in S3 if `AWS_STORAGE_BUCKET_NAME` is set.

`python manage.py check --deploy` passes with the production settings.

### Before launch

- Replace every SAMPLE: organisation details, bank accounts, people, figures, photos, text.
- Have the Privacy, Cookie, Terms and Fraud Alert pages written or reviewed by a lawyer.
- Only use photos with consent (the image library has a "consent obtained" box).
- Switch payment keys from test to live.

---

## Project layout

```
config/            settings (base, dev, test, prod), URLs, Celery
apps/core          site settings, menus, block library, base page, search, template tags, commands
apps/accounts      user model, admin 2FA, supporter account area
apps/pages         homepage, standard page, FAQ, contact
apps/about         history, leadership, financial reports
apps/programs      program pages
apps/emergencies   emergency hub, emergencies list, sitreps, media alerts
apps/countries     where we work (map), country pages
apps/stories       stories and news (filters), story pages
apps/giving        donations, monthly gifts, bank transfers, receipts, tributes, gift catalogue
apps/payments      Paystack, Stripe and test providers; webhooks
apps/fundraising   supporter fundraiser pages
apps/involvement   events, tenders, jobs
apps/newsletter    subscribers and Brevo sync
apps/dashboard     owner admin screens and menus
templates/         all page, block, email and account templates
static/            Tailwind source, site JS, vendored Alpine/HTMX/Leaflet
```

Design tokens (colours, fonts, breakpoints) are in `tailwind.config.js`. Icons are Lucide
(ISC licence); rebuild the sprite with `npm run build:icons`.
