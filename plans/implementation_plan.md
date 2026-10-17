# Implementation Plan — Humanitarian Medical Charity Website

Date: 14 October 2026
Source spec: `Humanitarian-Charity-Website-Build-Spec.pdf` (this folder)
Reference site: internationalmedicalcorps.org (read 14 October 2026)

---

## 1. Context

We are building a content and fundraising website for a global medical relief charity. It
matches the reference site's structure, page templates, features, interactions and visual
style one-to-one. It has two jobs:

1. **Show the work:** programs, emergencies, countries, stories, reports.
2. **Turn readers into donors:** nearly every page ends with a donate block and a newsletter
   signup, and every donate button carries an appeal code so each gift is traced to the page
   it came from.

The site carries **its own brand**: name, logo, copy, photos and colour values. The reference
charity's text and photos are copyrighted, and a donation site that looks identical to a real
charity would work as a scam page. Everything else (layout, flows, features, page anatomy)
matches.

Hundreds of URLs come from about 19 templates. The data rests on four taxonomy tags:
**Program, Country, Emergency, Topic**. Stories, resources and reports link to them, which
powers every "Read more on X" block and the stories filter.

### What this plan adds beyond the PDF

The PDF describes only the public site. The reference site edits content in a hidden
WordPress admin, and the public cannot update anything on the frontend. This plan adds:

- **A login-protected owner admin (section 7).** The app owner signs in at `/admin/` with an
  email and password (plus a 2FA code) and updates *everything visitors see*: text, photos,
  pages, menus, stats, emergencies, stories, contact details, **and the bank account numbers
  shown on the site for bank-transfer donations** (section 9.1). Visitors cannot reach
  the admin without logging in. Every piece of content, menu, setting, donation,
  subscriber, fundraiser, e-card, tender, job and event is managed from one admin with roles,
  approval workflow, scheduling, revision history, audit log, dashboards and CSV exports.
  Staff never need the raw Django admin or a developer to change the site.
- **A frontend account area for supporters (section 8).** Donors, monthly givers and
  fundraisers sign in on the public site to update their own details, manage recurring gifts,
  download receipts, edit scheduled e-cards and run their own fundraiser pages.
- **Edit shortcuts for staff on the live site (section 8.4).** A logged-in editor browsing the
  public site sees an "Edit this page" bar that jumps straight to the editor for that page.

---

## 2. Assumptions (confirm or change before Phase 1)

These questions are still open. The plan proceeds on these defaults, and each one can be
changed in a single place.

| # | Decision | Default used in this plan | Where it is changed |
|---|---|---|---|
| A1 | Organisation name, logo, tagline, tax ID | Placeholders, editable in admin **Site Settings** | Admin → Settings → Organisation |
| A2 | Currencies and payment providers | **Both:** NGN via **Paystack**, USD via **Stripe** | `payments` provider registry plus settings |
| A3 | Stack | Django + **Wagtail CMS**, PostgreSQL, Tailwind, Alpine.js + HTMX, Celery + Redis, Docker Compose (as the PDF recommends) | — |
| A4 | Newsletter platform | **Brevo** (Mailchimp adapter possible) | Settings plus env vars |
| A5 | Media storage | S3-compatible bucket with a CDN (Cloudinary as an option) | env vars |
| A6 | Peer fundraising, shop, careers | Fundraising and jobs **built in**. Shop deferred (optional, later). | — |
| A7 | Brand colours and fonts | Same *style* as the reference (dark brand blue, a bright accent reserved for donate, a sans-serif with a serif accent) with **our own** values and free fonts | `tailwind.config` design tokens |

---

## 3. Tech stack

| Layer | Choice | Why |
|---|---|---|
| Backend | Python 3.12, Django (current LTS), Wagtail (current LTS) | Wagtail gives editors a block-based page builder, a polished admin, workflows, revisions and scheduling |
| DB | PostgreSQL 16 | Full-text search, JSON fields, reliability |
| Frontend | Django templates, Tailwind CSS, Alpine.js (menus, tabs, accordions, modals), HTMX (filters, pagination, cart, account partials) | No SPA; fast server-rendered pages, good for SEO |
| Search | Wagtail search on the PostgreSQL backend | Sitewide search overlay with no extra service |
| Filters | django-filter, with filters kept in the URL query string | Linkable filtered views |
| Map | Leaflet with OpenStreetMap tiles (Mapbox optional) | Where We Work map |
| Auth (public) | django-allauth: email + password, email verification, optional Google login | Supporter accounts |
| Payments | Paystack (NGN, one-time and subscriptions), Stripe (USD, Checkout and Billing) | Spec recommendation |
| Jobs and queues | Celery + Redis + Celery Beat | Receipts, scheduled e-cards, newsletter sync, reminders |
| Email | Transactional email through Brevo SMTP/API; django-templated-email | Receipts, e-cards, account mail |
| Media | django-storages to S3 with a CDN; Wagtail renditions in **AVIF/WebP** | Fast images |
| PDFs | ReportLab (WeasyPrint needs GTK, which is awkward on Windows) | Donation receipts and annual giving statements |
| Spam | Honeypot fields plus Cloudflare Turnstile (or reCAPTCHA) on public forms; rate limiting with django-ratelimit | Mirrors the reference's honeypot plus reCAPTCHA |
| Observability | Sentry, structured logging | Payment and webhook failures surface immediately |
| Deploy | Docker Compose (web, worker, beat, db, redis, nginx/caddy) | As the user's other apps |
| Tests | pytest, pytest-django, factory_boy, Playwright for end-to-end checks | Verified by running the app, not only unit tests |

---

## 4. Project structure (Django apps)

```
hospital/
├─ config/                 settings (base/dev/prod), urls, celery, wsgi/asgi
├─ apps/
│  ├─ core/                site settings, design blocks (StreamField), base page, menus, SEO mixin, cookie consent, search
│  ├─ taxonomy/            Region, Country(*), Program(*), Emergency(*), Topic   (*) = page models, see below
│  ├─ pages/               HomePage, StandardPage, hub pages (WhoWeAre, WhatWeDo, WhereWeWork, GetInvolved), FAQPage, ContactPage
│  ├─ about/               HistoryPage + TimelineEntry, LeadershipPage + Person, FinancialReportsPage + Report
│  ├─ programs/            ProgramPage, FocusArea
│  ├─ emergencies/         EmergencyIndexPage, EmergencyPage, SituationReport, MediaAlert, past-emergency rows
│  ├─ countries/           WhereWeWorkPage (map), CountryPage, Challenge, ResponseSector, ImpactStat
│  ├─ stories/             StoriesIndexPage (filters), StoryPage (type: story/update/video/press release/supporter)
│  ├─ resources/           Resource (PDF/external), linked to the four tags
│  ├─ newsletter/          Subscriber, signup endpoints, Brevo sync
│  ├─ giving/              Donation, RecurringGift, Appeal, Tribute/ECard, GiftItem, GiftOrder, Receipt
│  ├─ payments/            provider adapters (Paystack, Stripe), checkout, webhooks, WebhookEvent
│  ├─ fundraising/         Fundraiser, FundraiserUpdate, moderation
│  ├─ involvement/         Event, Tender (+documents), Job
│  ├─ accounts/            custom User (email login), SupporterProfile, frontend account area
│  └─ dashboard/           custom Wagtail admin views: donation dashboards, exports, moderation queues, e-card queue
├─ templates/              base, components (header, mega menu, footer, cards, donate box…), pages, account, emails
├─ static/                 tailwind src, alpine components, icons (SVG line icons)
├─ plans/                  this plan + tasks.md
├─ docker-compose.yml, Dockerfile, .env.example, README.md
```

---

## 5. Data model

Page models (editable as pages in the Wagtail tree, with URLs, previews and revisions) are
marked **[P]**. Snippets and plain models (managed in admin listings) are marked **[S]**.

### 5.1 Taxonomy and content

| Model | Key fields | Links |
|---|---|---|
| Region [S] | name, order | Country |
| CountryPage [P] `/country/<slug>/` | name, region, hero, intro, work-started year, population, life expectancy, infant mortality, status (current/past), lat/lng, featured emergency, award feature, challenges (inline), response sectors (inline), impact stats (inline, year) | Region, Program, Emergency |
| ProgramPage [P] `/program/<slug>/` | name, hero, intro, 3 icon stats, achievements (list), focus areas (inline, 4 tabs), featured resources, featured story | Story, Resource |
| FocusArea (inline) | program, title, overview, read-more page, key stats (2–3) | Program |
| EmergencyPage [P] `/emergency-response/<slug>/` | title, status (active/ongoing/past), year range, countries (M2M), summary, hero, anchor-nav sections (StreamField), key facts, per-country response blocks, history, expertise, FAQ (inline), **appeal code**, donate form settings, featured stories | Country, Story, SitRep, MediaAlert |
| PastEmergencyRow [S] | country, emergency name, year, optional page link, optional expand paragraph, order | Emergencies list |
| StoryPage [P] `/story/`, `/updates/`, `/video/`, `/press-release/`, `/supporter/` | type, title, dek, body (StreamField), date, author, location tag, photo credit, hero, video URL, featured flag, highlighted flag | Program, Country, Emergency, Topic (M2M) |
| Topic [S] | name, slug | Story |
| Resource [S] | title, date, file or external URL, kind (capability statement, assessment, toolkit, webinar, press release) | Program, Country, Emergency |
| SituationReport [S] | title, number, date, PDF | Emergency, Country |
| MediaAlert [S] | date, outlet, headline, URL or video page | Emergency |
| ImpactStat [S/inline] | label, value, year, icon, image, link, order | HomePage, CountryPage |
| TimelineEntry (inline) | year, title/place, text, photo, order | HistoryPage |
| Person [S] | name, title, bio, photo, group (founder, CEO, board, council, ambassador, executive, affiliate board), company, city, order | LeadershipPage |
| Report [S] | type (annual, impact, audit, tax form), year, title, summary, cover, PDF | FinancialReportsPage |
| FAQ (inline) | question, answer, order | FAQPage, EmergencyPage, GiftsCatalog |
| Office [S] | name, address, phone, fax, emails | ContactPage, FAQ side box |
| Event [S] | title, date, place, description, ticket link, image | Events page |
| Tender [S] | title, country, reference, deadline, description, documents (inline), status (open/closed, derived from deadline) | Open Tenders page |
| Job [S] | title, location, type, deadline, description, apply link | Work With Us |

### 5.2 Supporters, giving and payments

| Model | Key fields | Notes |
|---|---|---|
| User | email (login), names, phone, is_staff, groups | Custom user from day one. Staff and supporters share one table and differ by role. |
| SupporterProfile | user, address, country, preferred currency, communication preferences, gift-aid style tax info if needed | Edited by the supporter on the frontend |
| Subscriber | first name, last name, email, phone (optional), consent timestamp, consent text version, source page, status (subscribed/unsubscribed), Brevo sync status, user (nullable) | |
| Appeal [S] | code, name, description, linked emergency (optional), active, goal (optional) | Codes travel on every donate button. Unknown codes are stored but flagged. |
| Donation | amount, currency, frequency (one-time/monthly), appeal code, appeal (FK), donor name/email, user (nullable), emergency, fundraiser, tribute, gift order, status (pending/succeeded/failed/refunded), provider, provider reference, source URL, created/paid at | Guest donations allowed. They link to an account when the email is verified. |
| RecurringGift | user/donor email, amount, currency, provider, provider subscription id, status (active/paused/cancelled/past_due), next charge date, appeal | Paystack subscription or Stripe subscription |
| Receipt | donation, number (sequential), PDF, sent at | Tax-language receipt |
| Tribute / ECard | donation or gift order, honoree name, type (honor/memory), sender name, recipient name/email, message, design, send date, sent flag, sent at, failure reason | **Never anonymous**, as the gifts catalog FAQ says |
| GiftItem [S] | title, price (per currency), image, blurb, order, active | About 12 items |
| GiftOrder / GiftOrderLine | buyer, lines (item, qty, price), total, currency, status, donation | Session cart → checkout |
| Fundraiser | owner (User), title, slug, goal, currency, story, photo, end date, linked emergency/appeal, status (draft/pending review/live/ended/hidden), raised (computed) | `/fundraise/<slug>/` |
| FundraiserUpdate | fundraiser, text, photo, date | Owner posts updates |
| WebhookEvent | provider, event id (unique), type, payload, processed at, error | Idempotency and audit |
| BankAccount [S] | bank name, account name, account number, currency (NGN/USD/GBP/EUR), sort code / SWIFT / IBAN / routing (optional), branch, instructions, show on (donate modal, donate page, emergency pages, footer, contact), linked emergency (optional, for a dedicated relief account), active, order | **Added and edited by the owner in the admin.** Shown to visitors with a Copy button. |
| BankTransferNotice | donor name, email, phone, amount, currency, bank account (FK), transfer date, bank reference, proof of payment (image/PDF upload), appeal code, emergency, message, status (pending/confirmed/rejected), confirmed by, confirmed at, donation (FK once confirmed) | Donor submits "I've sent a transfer"; the owner confirms it in the admin, which creates the Donation and sends the receipt |

---

## 6. Public site: templates and components

Everything in the PDF's "Page by page breakdown" is built as described. Summary and build notes:

### 6.1 Global (shared components)
- **Header:** logo; 5 mega-menu items; search icon → full-screen overlay; social icons; bright
  Donate Now button; sticky on scroll; hamburger with accordion menu on mobile.
- **Mega menu:** link list on the left, promo cards on the right. *Menu content is managed in
  admin* (Menus snippet), and the dynamic parts are queried live: the 3 current emergencies,
  the 4 latest stories, and countries by region tab.
- **Page hero:** full-width image, eyebrow, H1, H2 intro.
- **Pre-footer:** "Stay up to speed" newsletter form (first name, last name and email all
  required, consent text linking the privacy policy, honeypot, Turnstile) plus section sibling
  badges.
- **Footer:** Donate Today block, 4 link columns, legal links, copyright, tax-exempt status and
  ID, licence note, all from Site Settings.
- **Cookie consent banner:** analytics and Pixel scripts load **only after Accept**.
- **SEO:** Open Graph and Twitter cards, canonical URLs, sitemap.xml, robots.txt, JSON-LD
  (Organization, NGO, Article).
- **Donate modal:** any link with `?form=donate&appeal=CODE` (or a `data-donate` button)
  opens the donation modal with the appeal code preset. A full-page `/donate/` fallback
  carries the same form.

### 6.2 StreamField block library (shared by all pages)
Hero, rich text, image with caption, pull quote, video embed, icon stat row, big number
counters, alternating image/text rows, tabs, accordion (FAQ), card grid (story, emergency,
program, country), resource list, sitrep list, media alert list, timeline, people list,
donate box, newsletter form, CTA band, link cards, sibling badges, quote/celebrity block,
embed/widget (for crypto and stock widgets later).

### 6.3 Templates
1. Homepage
2. Who We Are hub
3. Our History (timeline of about 50 entries)
4. Leadership
5. Standard page (Mission, Values, Approach, Training, Research, Partnerships, Ethics, Fraud Alert, legal, Other Ways to Give and its sub-pages, Media Center, Global Ambassadors)
6. Accountability and Financial Reports
7. FAQ
8. Contact (no contact form, as on the reference)
9. What We Do hub / Our Work
10. Program page
11. Emergencies list (active blocks, ongoing cards, past table of about 70 rows with expandable rows and a "See all" toggle)
12. Emergency hub (sticky anchor nav, emergency-specific donate form, the most complex template)
13. Where We Work (lists of current and past countries plus an interactive Leaflet map with clickable markers and region tabs)
14. Country page (including previous/next and "Other countries")
15. Stories and News list (featured hero, 3 highlighted, 5-facet filter in the URL, numbered pagination through HTMX)
16. Story page (sticky share bar; also used for updates, videos, press releases and supporters)
17. Get Involved hub (tabs: gifts, tribute, planned giving, stocks)
18. Gifts catalog, gift detail and cart
19. Open Tenders, Events, Work With Us (list pages fed by snippets)
20. Fundraiser public page plus "Start a fundraiser" landing
21. Search results
22. 404 and 500 pages

---

## 7. Admin side (staff): Wagtail admin at `/admin/`

### 7.0 Owner login
- The admin lives at `/admin/` (the path is configurable, so it can be moved somewhere less
  guessable). Visitors who open it see **only a login page**.
- The owner signs in with an **email and password, plus a 6-digit code** from an
  authenticator app (2FA). The account is created at setup (`createsuperuser`). The owner can
  then add more staff accounts, reset passwords and remove access from the admin.
- "Forgot password" works by email. Failed logins are rate-limited and logged.
- The owner is a **Super Admin**: they can see and change everything listed below. Other
  roles (7.3) are optional and only needed if the owner adds staff.

**Principle:** staff manage *everything* from the branded Wagtail admin. The raw Django admin
is mounted at a hidden path for superuser emergencies only, and no routine task depends on it.

### 7.1 What staff can manage
| Area | In admin |
|---|---|
| Pages | Every page in the tree: create, edit with blocks, reorder, preview (desktop and mobile), schedule publish/unpublish, revision history and rollback, copy, move, delete |
| Content snippets | Regions, topics, resources, situation reports, media alerts, people, reports, offices, past emergencies, gift items, appeals, events, tenders, jobs |
| Media | Image library (focal point, alt text required, photo credit and consent fields), document library (PDFs) |
| Menus | Mega-menu items, promo cards, footer columns, legal links |
| Site Settings | Organisation name, logo, tagline, tax ID and status text, hotline numbers, HQ address, social links, default appeal code, cookie banner text, analytics/Pixel IDs, sitewide emergency alert banner (on/off, text, link) |
| **Bank accounts for donations** | Add, edit, reorder, hide or delete bank accounts (bank, account name, account number, currency, SWIFT/IBAN, instructions); choose where each is shown; link one to an emergency appeal. Changes appear on the site immediately. |
| **Bank transfer confirmations** | Queue of "I've sent a transfer" notices with the proof attachment; confirm (creates the donation and sends a receipt), reject (with a reason, emailed to the donor) |
| **Donation settings** | Preset amounts per currency, minimum amount, which payment methods show (card/Paystack, card/Stripe, bank transfer), thank-you message, receipt tax wording. API secret keys stay in server env vars for security; the admin only toggles methods on and off. |
| Redirects | Manage old URL → new URL redirects |
| SEO | Per-page SEO title, description and share image; search promotions |

### 7.2 Custom admin dashboards (`apps/dashboard`)
Built as Wagtail admin views and viewsets, so they sit in the same UI with the same login:

- **Home dashboard panels:** today/7-day/30-day donation totals by currency; new monthly
  donors; top appeals; active emergencies' fund totals; newsletter signups; pages awaiting
  approval; fundraisers awaiting review; failed e-cards and webhooks.
- **Donations:** searchable, filterable list (date range, currency, status, appeal,
  emergency, fundraiser, provider, one-time/monthly); detail view with the provider link;
  resend receipt; mark refunded (syncs with the provider where its API allows); CSV/XLSX export.
- **Recurring gifts:** list, status, next charge, cancel on a donor's behalf.
- **Appeals report:** totals per appeal code and per emergency over a date range, so each
  button's performance is visible.
- **Gift orders and e-cards:** order list; e-card queue (scheduled/sent/failed); resend;
  edit the send date.
- **Fundraisers:** moderation queue (approve, request changes, hide), totals, and featuring
  a fundraiser.
- **Subscribers:** list, search, export, Brevo sync status, manual unsubscribe.
- **Tenders/Jobs/Events:** auto-close past deadline, with a clear open/closed view.
- **Webhook log:** events received, processing errors, and a retry button.

### 7.3 Roles and permissions (Wagtail groups)
| Role | Can do |
|---|---|
| Super Admin | Everything, including users, roles and settings |
| Content Editor | Create and edit pages and snippets in their sections; submit for approval; cannot publish |
| Publisher / Moderator | Approve and publish pages; manage menus and redirects |
| Communications | Stories, updates, press releases, media alerts, sitreps, subscribers |
| Fundraising / Finance | Donations, recurring gifts, appeals, gift items and orders, e-cards, fundraisers, reports (financial PDFs); exports. **Read-only on page content.** |
| HR | Jobs |
| Procurement | Tenders |
| Events | Events |

Page-level permissions are set per section of the page tree (for example, Communications
owns Stories and News). Finance data (donor emails, amounts) is visible only to Finance and
Super Admin.

### 7.4 Workflow, safety and audit
- Wagtail **workflow**: Draft → In Review → Published, with comments on the edit screen and
  email notifications to approvers.
- **Scheduled publishing** (go-live and expiry dates), for example to retire an emergency
  banner.
- **Revisions** with compare and rollback; **page locking** while someone edits.
- **Audit log** of every admin action (who changed what and when). Donation status changes
  are logged with the reason.
- Staff sign-in: strong passwords, **two-factor authentication** (wagtail-2fa or
  django-otp), session timeout, login rate limiting.

---

## 8. Frontend: what users can update themselves

### 8.1 Who uses it
- **Anyone** can donate, buy gifts and subscribe *without* an account (guest checkout stays
  the fastest path, as on the reference).
- **Supporters** can optionally create an account (or are invited after their first gift)
  to manage everything below. Donations made as a guest attach to the account once its email
  is verified.

### 8.2 Account area `/account/`
| Section | What the user can see and do |
|---|---|
| Profile | Update name, email (with re-verification), phone, address, password; delete the account (anonymises personal data while keeping financial records) |
| My donations | Full history (date, amount, appeal/emergency, status); download each **PDF receipt**; download a **yearly giving statement** |
| Monthly giving | Change the amount, change the date, pause, resume, cancel; update the card via the provider (Stripe customer portal, or the Paystack manage-subscription link) |
| Tributes and e-cards | See scheduled e-cards; **edit the message, recipient or send date until sent**; cancel an unsent card; resend a sent one |
| Gift orders | Order history; resend e-cards |
| My fundraisers | Create a fundraiser (title, story, photo, goal, end date, cause/emergency); edit it at any time; post updates; see donors and the total raised; thank donors by email; share links; end the fundraiser early |
| Email preferences | Subscribe/unsubscribe and update the name/email on the newsletter. **One-click unsubscribe links work without logging in** (signed token). |

### 8.3 Rules
- Fundraiser pages: the first publish of a page goes to **moderation** (Fundraising role
  approves). Later edits of an approved page go live immediately but are flagged in a
  review log, and staff can hide a page at any time. A **Report this page** link on every
  fundraiser feeds the moderation queue.
- Uploaded images are size-limited, resized and stripped of EXIF location data.
- Money is never edited by users. Amount changes on monthly gifts go through the provider
  API, and the change only shows after the provider confirms it by webhook.

### 8.4 Staff editing from the frontend
- When a staff member is logged in, the **Wagtail userbar** appears on every public page:
  Edit this page, Add child page, View in admin, and accessibility check.
- Preview shows unpublished changes in the real site layout before publishing.
- True click-to-edit inline editing on the live page is **out of scope**. Wagtail's live
  side-by-side preview gives the same result with less risk.

---

## 9. Donations and payments

Visitors can give in three ways, all from the same donate modal and `/donate/` page:
**card online via Paystack (NGN)**, **card online via Stripe (USD)**, and **bank transfer**
to an account the owner has entered in the admin.

### 9.1 Bank transfer donations
- The donate modal and `/donate/` page have a **"Bank transfer"** tab. It lists the active
  bank accounts for the chosen currency: bank name, account name, account number (large, with
  a **Copy** button), SWIFT/IBAN where set, and the owner's instructions. It also shows a
  suggested reference (for example `GIFT-<appeal>-<short id>`) so the transfer can be matched.
- Emergency pages show that emergency's dedicated account if the owner has linked one, and
  the general account otherwise.
- Below the details: an optional **"I've made a transfer"** form (name, email, amount, date,
  bank reference, proof upload, consent). Submitting it creates a *pending* BankTransferNotice
  and emails the donor "we've received your notice".
- The owner sees the notice in the admin queue, checks the bank statement, and clicks
  **Confirm**. This records a succeeded Donation (provider = bank transfer, with the appeal code
  and emergency kept), sends the receipt, and counts the gift in all dashboards and totals.
  **Reject** emails the donor with the reason.
- Account numbers are shown only from the admin-managed BankAccount records. Nothing is
  hard-coded, so the owner can change banks without a developer.
- Safety: any change to bank details is written to the audit log and emails the owner, since
  swapped account numbers are a common fraud. The Fraud Alert page tells visitors that the
  only valid accounts are the ones shown on the site.

### 9.2 Card payments, gifts, receipts and other giving
- **Provider adapter pattern** (`apps/payments/providers/{paystack,stripe}.py`) with one
  interface: `create_one_time()`, `create_recurring()`, `cancel_recurring()`,
  `update_recurring()`, `refund()`, `verify_webhook()`, `parse_event()`. The currency chosen
  in the form picks the provider (NGN → Paystack, USD → Stripe).
- **Donation modal:** frequency toggle (one-time/monthly), preset amounts per currency plus a
  custom amount, optional "dedicate this gift" (tribute fields), donor details, and an
  optional "create an account" tickbox. Appeal code, emergency, fundraiser and source URL
  are carried as hidden fields.
- The **emergency-specific form** fixes the emergency and its appeal code, so the money goes to
  that emergency's fund.
- **Server creates a pending Donation first**, then redirects to Paystack checkout or Stripe
  Checkout. The return page shows "processing" until the webhook confirms.
- **Webhooks are the source of truth:** signature verified, stored in WebhookEvent (unique
  event id, so retries are harmless), status updated in one transaction, then Celery sends
  the receipt (and schedules any e-card).
- **Recurring:** Paystack plans and subscriptions, or Stripe Billing subscriptions. Each
  renewal charge creates a new Donation row linked to the RecurringGift.
- **Gifts catalog:** session cart (HTMX), checkout into one GiftOrder plus one Donation, with
  e-card instructions and scheduling. The buyer cannot pick a country (as the spec says).
- **Receipts:** sequential numbers, a PDF with tax language from Site Settings, emailed on
  success, and downloadable from the account area.
- **Give by mail or phone:** a downloadable PDF form plus the hotline, both from Site Settings.
- **Crypto, stock, DAF, legacy and employee matching:** content pages first, with an embed
  block for a third-party widget later.

---

## 10. Background jobs (Celery)

| Task | Trigger |
|---|---|
| Send receipt email + PDF | Donation succeeded |
| Send e-card | Celery Beat runs every 5 minutes and picks cards due now (meets the "within 2 hours" promise) |
| Retry failed e-cards and emails | Backoff, then flag in the admin queue |
| Sync subscriber to Brevo | Signup, unsubscribe or profile change |
| Close tenders and jobs past deadline | Daily |
| End fundraisers past their end date | Daily |
| Yearly giving statements | January, on request |
| Dunning notice for failed recurring charges | Provider webhook |

---

## 11. Cross-cutting

- **Search:** header overlay with live results (HTMX) plus a full results page; indexes pages,
  stories, resources and countries.
- **Analytics:** GA4 and Facebook Pixel, gated by cookie consent. Donation-complete events
  carry the appeal code.
- **Performance:** AVIF/WebP renditions with `srcset`, lazy loading, a CDN for media and static
  files, template fragment caching for the mega menu and footer (cleared on publish), and
  database indexes on the tag M2Ms. Lighthouse target ≥ 90 on mobile.
- **Accessibility:** WCAG 2.1 AA. Keyboard-operable mega menu, tabs and accordions; focus
  traps in the modal and overlays; alt text required in the image library.
- **Security:** CSRF everywhere, HTTPS/HSTS, secure cookies, CSP, rate limits on forms and
  login, webhook signature checks, no card data touches our server (PCI scope stays with the
  providers), and least-privilege roles.
- **Privacy:** consent text version stored with each subscriber; data export and account
  deletion in the account area; Privacy and Cookie policy pages.
- **Content seeding:** a management command `seed_demo` creates realistic placeholder content
  (written fresh, not copied) for all templates, so every page can be seen and tested before
  real content arrives.

---

## 12. Design system (own brand, same style)

- White pages with generous whitespace; a Foundation-like grid with breakpoints at about
  480 / 768 / 1024 / 1200 / 1440 px (the same as the reference).
- **Tokens:** `brand-dark` (deep navy, for headings and text), `brand` (medium blue for
  links), `brand-light` (cyan for highlights), `accent` (bright orange-red, **donate buttons
  only**), plus green, yellow and red for icons and stats. Exact values are ours, chosen in
  Phase 1.
- **Fonts:** a free sans-serif in place of the reference's paid Proxima Nova (for example
  *Montserrat* or *Source Sans 3*), plus *Noto Serif* for eyebrows and quotes.
- Big bold headings, short paragraphs, big impact numbers, simple SVG line icons, and
  photo-label-title-text-link cards everywhere.
- Mobile-first, with a sticky header and a sticky donate button on mobile.

---

## 13. Build phases

The PDF's 11 steps are kept in order, with the admin and account work inserted where it belongs.

| Phase | Scope | Done when |
|---|---|---|
| 0 | Project setup: Docker Compose, settings, custom User, Wagtail, Tailwind build, Celery, CI, README | `docker compose up` serves a page, and the admin login works |
| 1 | Design tokens, base layout, header + mega menu, hero, pre-footer, footer, cookie banner, search overlay, Site Settings, Menus | Every global component renders at all breakpoints from admin-managed data |
| 2 | Core models and admin: Region, Country, Program, Emergency, Story, Topic, Resource; block library; **roles, workflow, 2FA** | Editors can create every core type; roles are enforced |
| 3 | Stories list with URL filters and pagination; Story page with share bar | Filtered URLs are linkable; related stories are correct |
| 4 | Program, Country and Emergency templates; resources, sitreps and media alerts; Emergencies list; past-emergency table | All three templates match the spec section by section |
| 5 | Homepage with live stats, emergencies and stories | Homepage is fully admin-driven |
| 6 | Payments: Paystack + Stripe, **bank transfer with admin-managed account numbers and a confirmation queue**, donate modal, appeal codes, emergency forms, recurring, webhooks, receipts; **donation admin dashboards and exports** | Test-mode donations in both currencies reach "succeeded" through webhooks; an account number added in the admin shows on the donate modal; a transfer notice confirmed in the admin becomes a donation with a receipt; admin totals match |
| 7 | **Supporter accounts:** sign-up, verification, profile, donation history, receipts, monthly-gift management, email preferences | A donor can do every action in §8.2 except fundraisers and e-cards |
| 8 | Who We Are pages: History, Leadership, Reports, FAQ, Contact, standard pages | All Who We Are pages are live |
| 9 | Tribute giving, gifts catalog, cart, e-cards (scheduled), account e-card editing, e-card admin queue | An e-card scheduled for +10 minutes arrives; it can be edited before sending |
| 10 | Where We Work map | Markers are clickable, and region tabs filter them |
| 11 | Peer fundraising (create/edit/moderate/donate), events, tenders, jobs | A fundraiser goes from draft → approved → receives a donation → progress bar updates |
| 12 | Newsletter: Subscriber model, Brevo sync, unsubscribe tokens | A signup appears in Brevo; unsubscribe works without login |
| 13 | SEO, sitemap, analytics + Pixel behind consent, performance, accessibility, security hardening | Lighthouse ≥ 90, axe has no serious issues, security checklist passes |
| 14 | Seed content, end-to-end test pass, deploy, editor handbook | Every flow run through in the browser; README and handbook written |

---

## 14. Verification

The rule is that nothing is "done" until it has been run in the browser.

- **Unit and integration tests:** models, filters, appeal-code capture, webhook idempotency
  (the same event sent twice gives one donation), permission checks per role, and edit
  windows for fundraisers and e-cards.
- **Payments:** Paystack and Stripe **test mode** end to end, including a failed card, a
  refund, a renewal and a cancellation, with the Stripe CLI and Paystack webhook forwarding
  to the local server.
- **Playwright end-to-end runs:** guest donation; monthly sign-up → change amount → cancel;
  gift cart → e-card; create fundraiser → admin approve → donate; editor drafts →
  publisher approves → page live; stories filter URLs.
- **Manual pass of every template** at 375 px, 768 px and 1440 px against the spec checklist.
- **Lighthouse and axe** runs on the homepage, story, country and emergency pages.
- **README** covers setup, env vars, seeding, running tests and test-mode payments.

---

## 15. Risks and notes

- **Brand lookalike risk:** the site must not be confusable with the reference charity. Use
  our own name, logo, colours, copy and photos.
- **Paystack subscription limits:** amount changes on a Paystack subscription mean cancel
  and re-create. The adapter hides this from the user.
- **Content volume:** about 50 history entries, about 70 past emergencies, about 30 countries
  and hundreds of stories need real content. Import scripts (CSV → snippets/pages) are
  included in Phase 14 if the content arrives in spreadsheets.
- **Photo consent:** the image library has required "consent obtained" and "credit" fields.

---

## 16. Build notes (14 October 2026)

- Built on Wagtail 8.0 / Django 6.1. Local development uses SQLite, offline test payments,
  file-saved emails and eager background jobs (see README).
- The desktop mega menu shows from 1280px; below that the hamburger menu is used (measured:
  the full menu needs about 1,213px of content width).
- Due e-cards are sent the moment payment is confirmed; future-dated ones by the 5-minute scheduler.
- Email sending after payment runs as a robust after-commit step, so an email failure can
  never mark a payment as failed.
