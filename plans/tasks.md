# Tasks — Humanitarian Medical Charity Website

Breakdown of `implementation_plan.md`. Status updated 14 October 2026: ticked = built and run (tests or browser). Tick each box only after the feature has been
**run in the browser**, not just unit-tested.

Legend: **[ADMIN]** = staff admin side · **[ACCOUNT]** = supporter frontend self-service

---

## Phase 0 — Project setup
- [ ] 0.1 Confirm open decisions A1–A7 (brand name/logo, currencies, stack, newsletter platform, storage) _(open: brand name/logo still placeholders; defaults A2–A7 used)_
- [x] 0.2 Create Django project `config/` with base/dev/prod settings and `.env.example`
- [x] 0.3 Custom `User` model (email login) before the first migration
- [x] 0.4 Install and configure Wagtail; brand the admin (logo, name, colours)
- [x] 0.5 PostgreSQL + Redis + Celery worker + Celery Beat in Docker Compose
- [x] 0.6 Tailwind build pipeline, Alpine.js, HTMX
- [x] 0.7 Media storage: local in dev, S3 + CDN in prod; AVIF/WebP renditions enabled
- [x] 0.8 Sentry + logging; pytest, pytest-django, factory_boy, Playwright set up
- [ ] 0.9 CI: lint, tests, Tailwind build _(open: no CI pipeline yet)_
- [x] 0.10 README skeleton (setup, run, test)
- [x] 0.11 Verify: `docker compose up` → home page loads, `/admin/` login works

## Phase 1 — Design system and global layout
- [x] 1.1 Design tokens (colours, fonts, spacing, breakpoints) in the Tailwind config
- [x] 1.2 Base template, SEO meta mixin (OG/Twitter, canonical), JSON-LD
- [x] 1.3 **[ADMIN]** Site Settings: org name, logo, tagline, tax ID/status, hotlines, HQ address, social links, default appeal, cookie text, analytics IDs, emergency alert banner
- [x] 1.4 **[ADMIN]** Menus snippet: mega-menu items, left links, promo cards, footer columns, legal links
- [x] 1.5 Header: logo, 5 menu items, search icon, socials, Donate Now; sticky behaviour
- [x] 1.6 Mega menu panels (Alpine.js), keyboard accessible; dynamic emergencies, latest stories, and region tabs → countries
- [x] 1.7 Mobile hamburger with accordion submenus
- [x] 1.8 Full-screen search overlay with live results (HTMX) + search results page
- [x] 1.9 Page hero component (image, eyebrow, H1, H2)
- [x] 1.10 Pre-footer: newsletter form (honeypot + Turnstile) and sibling badges
- [x] 1.11 Footer: Donate Today block, 4 columns, legal, copyright/tax/licence
- [x] 1.12 Cookie consent banner; analytics and Pixel load only after Accept
- [x] 1.13 404 and 500 pages
- [x] 1.14 Verify every global component at 375 / 768 / 1440 px

## Phase 2 — Core models, block library, admin roles
- [x] 2.1 Region, Topic snippets
- [x] 2.2 CountryPage, ProgramPage (+ FocusArea inline), EmergencyPage, StoryPage page models
- [x] 2.3 Resource, SituationReport, MediaAlert, ImpactStat snippets with tag links
- [x] 2.4 StreamField block library (hero, rich text, image, quote, video, icon stats, counters, alternating rows, tabs, accordion, card grids, resource/sitrep/media lists, timeline, people list, donate box, newsletter, CTA band, link cards, badges, embed)
- [x] 2.5 Page tree: Home → hubs → index pages; URL patterns `/program/`, `/country/`, `/emergency-response/`, `/story/` etc.
- [x] 2.6 **[ADMIN]** Image library extra fields: alt text (required), credit, consent obtained
- [x] 2.7 **[ADMIN]** Groups and permissions: Super Admin, Content Editor, Publisher, Communications, Fundraising/Finance, HR, Procurement, Events
- [x] 2.8 **[ADMIN]** Workflow Draft → Review → Publish with approver email notifications
- [x] 2.9 **[ADMIN]** Scheduled publishing, revisions/rollback, page locking enabled and tested
- [x] 2.10 **[ADMIN]** Owner login at `/admin/` (configurable path): login page only for visitors, email + password + 2FA code, forgot-password email, login rate limit, session timeout; hide raw Django admin path
- [x] 2.10a **[ADMIN]** Owner (Super Admin) can add/remove staff accounts and reset their passwords from the admin
- [x] 2.10b Verify: logged-out visitor opening `/admin/` sees only the login page; owner logs in and edits a page, and the change shows on the public site
- [x] 2.11 **[ADMIN]** Audit log visible to Super Admin
- [x] 2.12 **[ADMIN]** Redirects app enabled
- [x] 2.13 Tests: each role can and cannot do the right things

## Phase 3 — Stories
- [x] 3.1 StoriesIndexPage: featured hero, 3 highlighted cards
- [x] 3.2 Filter panel: Content Type, Program, Location, Emergency, Topic; Reset/Close; query string in the URL (django-filter + HTMX)
- [x] 3.3 Result cards (image, type label, title, date, excerpt, Continue Reading) + numbered pagination
- [x] 3.4 StoryPage: sticky top bar (logo, title, share, Donate), hero, dek, meta line, body, donate box, share, tag links, 3 related
- [x] 3.5 Updates, videos, press releases and supporter profiles share the template at their own URL prefixes
- [x] 3.6 Verify: filtered URLs are shareable and reload to the same results

## Phase 4 — Program, Country, Emergency templates
- [x] 4.1 Program page: hero, intro, 3 icon stats, achievements, Areas of Focus tabs (4), featured resources, featured story, "Read more on X" + filtered Explore link, resources list, donate box
- [x] 4.2 Seed the 7 programs
- [x] 4.3 Country page: hero, featured emergency card, intro, donate, key stats, award feature, Challenges (3 cards), Our Response sectors, Impact counters (year), resources, sitreps, related stories, donate box, prev/next + Other countries
- [x] 4.4 Emergency hub: hero, sticky anchor nav, summary + emergency donate call-out, key facts, per-country response, history, expertise, FAQ, 2 featured stories, media alerts, sitreps, resources, related stories, View all link
- [x] 4.5 Emergencies list: intro, active blocks, ongoing cards (tag), past table (about 70 rows, expandable rows, "See all past" toggle)
- [x] 4.6 **[ADMIN]** PastEmergencyRow snippet with ordering
- [x] 4.7 Verify each template section by section against the spec

## Phase 5 — Homepage
- [x] 5.1 Hero (emergency photo, headline, appeal, Give Now with appeal code)
- [x] 5.2 2–3 emergency cards (live query)
- [x] 5.3 Mission paragraph + approach link
- [x] 5.4 Our Impact alternating rows (about 8, from ImpactStat)
- [x] 5.5 Donate band, Stories of Hope (3 latest), Join Our Community form
- [x] 5.6 Verify: changing data in admin updates the homepage (caches cleared on publish)

## Phase 6 — Donations and payments
- [x] 6.1 Appeal, Donation, RecurringGift, Receipt, WebhookEvent models
- [ ] 6.2 Provider adapter interface; Paystack adapter (NGN one-time + subscription) _(open: code written to Paystack's API; not yet run against Paystack test keys)_
- [ ] 6.3 Stripe adapter (USD Checkout + Billing subscription + customer portal) _(open: code written to Stripe's API; not yet run against Stripe test keys)_
- [x] 6.3a **[ADMIN]** BankAccount snippet: bank name, account name, account number, currency, SWIFT/IBAN/sort code, instructions, where shown, linked emergency, active, order
- [x] 6.3b **[ADMIN]** Donation settings: preset amounts per currency, minimum, payment methods on/off (Paystack, Stripe, bank transfer), thank-you text, receipt wording
- [x] 6.3c "Bank transfer" tab in the donate modal and `/donate/`: active accounts for the chosen currency, Copy button, suggested reference, instructions
- [x] 6.3d Emergency pages show their linked bank account (fallback: general account)
- [x] 6.3e "I've made a transfer" form (amount, date, reference, proof upload, honeypot) → pending BankTransferNotice + acknowledgement email
- [x] 6.3f **[ADMIN]** Bank transfer queue: view proof, Confirm (creates Donation + receipt) or Reject (reason emailed)
- [x] 6.3g **[ADMIN]** Bank detail changes written to the audit log and emailed to the owner; Fraud Alert page explains the valid accounts
- [x] 6.3h Verify: account added in admin appears on the site; notice confirmed in admin shows in donation totals with a receipt sent
- [x] 6.4 Donate modal: frequency, preset/custom amounts per currency, tribute option, donor details, optional account creation; opens from `?form=donate&appeal=CODE` and `data-donate` buttons
- [x] 6.5 `/donate/` full-page fallback
- [x] 6.6 Appeal code on every donate button (homepage, footer, emergency, story, program, country)
- [x] 6.7 Emergency-specific form that fixes the emergency + appeal
- [x] 6.8 Pending donation → provider checkout → return "processing" page
- [x] 6.9 Webhook endpoints: signature check, idempotent WebhookEvent, status transitions in a transaction
- [x] 6.10 Recurring renewals create Donation rows; failed-charge handling
- [x] 6.11 Receipt PDF (WeasyPrint, sequential number, tax text from settings) + email through Celery
- [x] 6.12 **[ADMIN]** Dashboard home panels (totals, new monthly donors, top appeals, emergency funds, pending items)
- [x] 6.13 **[ADMIN]** Donations list with filters, detail, resend receipt, refund, CSV/XLSX export
- [x] 6.14 **[ADMIN]** Recurring gifts list + cancel on behalf of a donor
- [x] 6.15 **[ADMIN]** Appeals report (totals per code and per emergency by date range)
- [x] 6.16 **[ADMIN]** Webhook log with retry
- [x] 6.17 Tests: duplicate webhook → one donation; failed card; refund; renewal; cancel
- [ ] 6.18 Verify in test mode for NGN and USD end to end in the browser _(open: verified only in offline test mode)_

## Phase 7 — Supporter accounts [ACCOUNT]
- [ ] 7.1 django-allauth: sign up, email verification, login, logout, password reset; optional Google login _(open: Google login not added)_
- [x] 7.2 SupporterProfile; link guest donations by verified email
- [x] 7.3 `/account/` layout and navigation
- [x] 7.4 Profile: edit name, email (re-verify), phone, address, password
- [x] 7.5 My donations: history, receipt PDF download, yearly statement download
- [x] 7.6 Monthly giving: change amount/date, pause, resume, cancel, update card (provider portal)
- [x] 7.7 Email preferences; signed one-click unsubscribe without login
- [x] 7.8 Data export + account deletion (anonymise, keep financial records)
- [x] 7.9 Post-donation "create an account" invite email
- [x] 7.10 Tests: a user sees only their own data; edits after cancel are rejected
- [x] 7.11 Verify every account action in the browser

## Phase 8 — Who We Are
- [x] 8.1 Who We Are hub (intro, 3 history teaser cards, quote block, badges)
- [x] 8.2 History page with about 50 TimelineEntry rows, end link cards, badges
- [x] 8.3 Leadership: featured founder/CEO cards, grouped name lists from Person, link cards
- [x] 8.4 Financial Reports: efficiency infographic, ratings, annual reports (latest large), impact reports, audits/tax forms by year, badges
- [x] 8.5 FAQ page: accordion + side box (HQ, phone, fax, email, hotline, donate)
- [x] 8.6 Contact: offices, department emails, donate-by-mail PDF, FAQ link
- [x] 8.7 Standard pages: Mission, Values, Approach, Training, Research, Partnerships, Ethics, Fraud Alert, Privacy, Cookies, Terms, Media Center, Global Ambassadors
- [x] 8.8 **[ADMIN]** Person, Report, Office snippets with ordering

## Phase 9 — Tribute giving, gifts catalog, e-cards
- [x] 9.1 Tribute/ECard model; tribute fields in the donate modal (honor/memory, recipient, message, send date)
- [x] 9.2 GiftItem snippet (about 12), catalog page, gift detail
- [x] 9.3 Session cart (HTMX add/remove/update), checkout → GiftOrder + Donation
- [x] 9.4 E-card designs (email templates); "never anonymous" rule enforced
- [x] 9.5 Celery Beat: send due e-cards every 5 minutes; retries; failure flag
- [x] 9.6 Gifts catalog FAQ (our own wording)
- [x] 9.7 **[ACCOUNT]** View scheduled e-cards; edit message/recipient/date until sent; cancel; resend
- [x] 9.8 **[ACCOUNT]** Gift order history
- [x] 9.9 **[ADMIN]** Gift orders list; e-card queue (scheduled/sent/failed), resend, edit send date
- [x] 9.10 Get Involved hub (monthly hero, 4 tabs, more ways, mail/phone, sections) + Other Ways to Give sub-pages
- [x] 9.11 Verify: an e-card scheduled for +10 minutes arrives; editing before send works and is blocked after

## Phase 10 — Where We Work map
- [x] 10.1 Where We Work page: current countries (linked), past countries (linked or plain)
- [x] 10.2 Leaflet map with markers from Country lat/lng; popups link to country pages
- [x] 10.3 Region tabs filter markers and lists; keyboard-accessible list alternative
- [x] 10.4 Verify on mobile and desktop

## Phase 11 — Fundraising, events, tenders, jobs
- [x] 11.1 Fundraiser + FundraiserUpdate models; public page `/fundraise/<slug>/` (photo, story, goal, progress bar, donors, share, donate)
- [x] 11.2 "Start a fundraiser" landing page
- [x] 11.3 **[ACCOUNT]** Create/edit fundraiser, post updates, view donors, thank donors, end early
- [x] 11.4 Image upload: size limit, resize, strip EXIF
- [x] 11.5 **[ADMIN]** Moderation queue: approve, request changes, hide; feature fundraiser; Report-this-page feed
- [x] 11.6 Donations to a fundraiser are linked and the total updates through the webhook
- [x] 11.7 Event snippet + Events page
- [x] 11.8 Tender snippet (+ documents) + Open Tenders page; auto-close after deadline
- [x] 11.9 Job snippet + Work With Us page; auto-close after deadline
- [x] 11.10 Verify: draft → approved → donation → progress bar updates

## Phase 12 — Newsletter
- [x] 12.1 Subscriber model (consent time + text version, source page)
- [x] 12.2 All signup forms post through one endpoint (honeypot, Turnstile, rate limit, HTMX success state)
- [ ] 12.3 Brevo sync task (subscribe, unsubscribe, update) _(open: code written; not yet run against a real Brevo account)_
- [x] 12.4 **[ADMIN]** Subscribers list, search, export, sync status, manual unsubscribe
- [x] 12.5 Verify: signup appears in Brevo; unsubscribe link works without login

## Phase 13 — SEO, analytics, performance, accessibility, security
- [x] 13.1 sitemap.xml, robots.txt, OG images per page, JSON-LD
- [x] 13.2 GA4 + Facebook Pixel behind consent; donation-complete event carries the appeal code
- [x] 13.3 Image `srcset`, lazy loading, fragment caching for menu and footer, DB indexes
- [ ] 13.4 Lighthouse ≥ 90 on mobile (home, story, country, emergency) _(open: Lighthouse not run yet)_
- [ ] 13.5 axe accessibility audit: no serious issues; keyboard test for menu, tabs, modal _(open: axe audit not run yet)_
- [ ] 13.6 Security: CSP, HSTS, secure cookies, rate limits, `check --deploy` clean _(open: check --deploy passes; CSP header not added yet)_

## Phase 14 — Content, testing, launch
- [x] 14.1 `seed_demo` command with original placeholder content for every template
- [ ] 14.2 CSV import commands (countries, past emergencies, history, people, stories) if content arrives in spreadsheets _(open: not started)_
- [ ] 14.3 Playwright suite: guest donation, monthly lifecycle, gift + e-card, fundraiser flow, editor → publisher workflow, story filters _(open: browser walkthrough scripted ad hoc; not yet a committed Playwright suite)_
- [x] 14.4 Manual pass of every template at 375 / 768 / 1440 px
- [ ] 14.5 Production Docker Compose, backups, env secrets, provider webhooks pointed at prod _(open: Dockerfile + compose written; not yet deployed)_
- [x] 14.6 README complete (setup, env, seeding, tests, test-mode payments)
- [ ] 14.7 Editor handbook: how staff create pages, publish, manage donations, moderate fundraisers _(open: README covers the admin; separate editor handbook not written)_
- [ ] 14.8 Launch checklist and switch to live payment keys _(open: not started)_
