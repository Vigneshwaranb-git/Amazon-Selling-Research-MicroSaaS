# INITIAL.md - AmzScoutIQ Product Definition

> An automated intelligence platform that tracks Amazon best-sellers, predicts emerging product trends, and calculates true FBA margins to help sellers launch winning private-label products.

---

## PRODUCT

### Name
AmzScoutIQ (alt. name: ASINPulse)

### Description
AmzScoutIQ gives Amazon sellers data-backed validation before they invest in inventory. It tracks best-seller rankings and historical BSR, surfaces emerging product trends, calculates true FBA profit margins, and mines customer reviews for recurring complaints and market gaps.

### Target User
Amazon FBA private-label sellers, aggregator brands, and product researchers who need data-backed validation before investing inventory capital.

### Type
- [x] SaaS (Software as a Service)

---

## TECH STACK

### Backend
- [x] FastAPI + Python 3.11+

### Frontend
- [x] React + Vite + TypeScript

### Database
- [x] PostgreSQL (SQLAlchemy + Alembic)

### Authentication
- [x] Email/Password + Google OAuth (JWT)

### UI Framework
- [x] Tailwind + shadcn/ui (Framer Motion for animations)

### Payments
- [x] Dodo Payments

---

## MODULES

### Module 1: Authentication (Required)

**Description:** User authentication and authorization

**Models:**
- User: id, email, hashed_password, full_name, is_active, is_verified, is_admin, oauth_provider, created_at
- RefreshToken: id, user_id, token, expires_at, revoked

**API Endpoints:**
- POST /api/v1/auth/register - Create new account
- POST /api/v1/auth/login - Login with email/password
- POST /api/v1/auth/refresh - Refresh access token
- POST /api/v1/auth/logout - Revoke refresh token
- GET /api/v1/auth/me - Get current user profile
- PUT /api/v1/auth/me - Update profile
- GET /api/v1/auth/google - Start Google OAuth flow
- GET /api/v1/auth/google/callback - Google OAuth callback
- POST /api/v1/auth/forgot-password, POST /api/v1/auth/reset-password

**Frontend Pages:**
- /login, /register, /forgot-password
- /profile (protected)

---

### Module 2: Product Tracker & Trend Discovery

**Description:** Discover trending Amazon best-sellers and track chosen ASINs over time.

**Models:**
- Product: id, asin (unique), title, category, image_url, bsr, estimated_monthly_sales, estimated_monthly_revenue, price, rating, review_count, saturation_score, trend_score, updated_at
- BsrSnapshot: id, product_id, bsr, price, estimated_sales, rating, review_count, captured_at
- TrackingList: id, user_id, name, created_at
- TrackedProduct: id, tracking_list_id, product_id, added_at

**API Endpoints:**
- GET /api/v1/products - Search/filter top 100 best-sellers (category, margin, saturation, trend)
- GET /api/v1/products/{asin} - Product detail
- GET /api/v1/products/{asin}/history - Historical BSR/sales snapshots
- GET/POST /api/v1/tracking-lists, PUT/DELETE /api/v1/tracking-lists/{id}
- POST /api/v1/tracking-lists/{id}/products - Add ASIN to list
- DELETE /api/v1/tracking-lists/{id}/products/{asin} - Remove ASIN
- GET /api/v1/products/export - Export research data to CSV

**Frontend Pages:**
- /dashboard - Discovery dashboard: trending products feed with filters
- /products/:asin - Tracker detail with historical BSR and sales charts (Framer Motion animations)
- /tracking-lists - Manage custom tracking lists

---

### Module 3: Profit & FBA Fee Calculator

**Description:** Calculate true per-unit profit, ROI and break-even for a product.

**Models:**
- CostModel: id, user_id, asin (nullable), name, unit_cost, shipping_cost, referral_fee, fba_fulfillment_fee, storage_fee, vat_tax, selling_price, target_roi, target_margin, net_profit, roi, margin, created_at

**API Endpoints:**
- POST /api/v1/calculator/calculate - Stateless real-time calculation
- POST /api/v1/calculator/simulate - Compare pricing strategies, break-even and ROI
- GET/POST /api/v1/scenarios, GET/PUT/DELETE /api/v1/scenarios/{id} - Saved scenarios (linkable to tracked ASINs)

**Frontend Pages:**
- /calculator - Interactive profit margin and fee breakdown calculator
- /calculator/saved - Saved scenarios linked to tracked ASINs

---

### Module 4: Review & Sentiment Monitor

**Description:** Analyze competitor reviews to find recurring flaws and market gaps.

**Models:**
- ReviewLog: id, product_id, review_id (unique), rating, review_text, sentiment_score, sentiment_label (positive/neutral/negative), pain_points (JSON), reviewed_at
- ReviewSummary: id, product_id, pros, cons, opportunities, generated_at

**API Endpoints:**
- GET /api/v1/reviews/{asin} - List reviews (filter by star rating and keyword)
- GET /api/v1/reviews/{asin}/summary - AI-generated summary: pros, cons, improvement opportunities
- POST /api/v1/reviews/{asin}/analyze - Trigger sentiment analysis
- GET /api/v1/reviews/{asin}/pain-points - Aggregated recurring complaints

**Frontend Pages:**
- /reviews/:asin - Sentiment analytics with AI summary, pros, cons, and opportunities

---

### Module 5: Dashboard & Analytics

**Description:** Usage metrics, charts and reports plus user settings.

**Frontend Pages:**
- /dashboard - Overview widgets (shared with Discovery dashboard)
- /analytics - Usage metrics, charts, reports
- /settings - User settings, billing and preferences

---

### Module 6: Billing (Dodo Payments)

**Models:**
- Subscription: id, user_id, plan, status, dodo_customer_id, dodo_subscription_id, current_period_end

**API Endpoints:**
- POST /api/v1/billing/checkout - Create Dodo checkout session
- POST /api/v1/billing/webhook - Dodo webhook (signature verified)
- GET /api/v1/billing/subscription - Current plan

**Frontend Pages:**
- /pricing, /settings/billing

---

### Module 7: Admin Panel

**Description:** Admin-only management interface.

**API Endpoints:**
- GET /api/v1/admin/users - List all users
- PUT /api/v1/admin/users/{id} - Update user status
- GET /api/v1/admin/stats - Platform statistics

**Frontend Pages:**
- /admin - Admin dashboard (admin only)
- /admin/users - User management

---

### Supporting Features

- **Email Notifications:** welcome, verify email, password reset, BSR-change alerts for tracked ASINs
- **File Uploads:** import ASIN lists / cost sheets (CSV), user avatar

---

## MVP SCOPE

> Inferred from the modules (no explicit MVP list was provided) - edit as needed.

### Must Have (MVP)
- [x] User registration and login (email/password + Google)
- [x] Discovery dashboard with best-seller filters
- [x] Add ASINs to tracking lists + historical BSR chart
- [x] Profit & FBA fee calculator with saved scenarios
- [x] Dodo Payments subscription

### Nice to Have (Post-MVP)
- [ ] Review & Sentiment Monitor (AI summaries)
- [ ] CSV export and CSV import
- [ ] Email alerts for BSR changes
- [ ] Analytics dashboard
- [ ] Admin panel

---

## ACCEPTANCE CRITERIA

### Authentication
- [ ] User can register and login with email/password
- [ ] User can sign in with Google OAuth
- [ ] JWT tokens work correctly with refresh
- [ ] Protected routes redirect to login

### Product Tracker
- [ ] User can filter best-sellers by category, margin and saturation score
- [ ] User can add/remove ASINs in custom tracking lists
- [ ] Product detail shows historical BSR and sales charts
- [ ] User can export research data to CSV

### Profit Calculator
- [ ] Net profit per unit updates in real time as costs change
- [ ] Break-even and ROI shown for simulated prices
- [ ] Scenarios can be saved and linked to a tracked ASIN

### Review & Sentiment
- [ ] Reviews filterable by star rating and keyword
- [ ] AI summary shows pros, cons and opportunities
- [ ] Recurring pain points aggregated per ASIN

### Billing & Admin
- [ ] User can subscribe via Dodo Payments; webhook updates subscription state
- [ ] Only admins can access /admin routes

### Quality
- [ ] All API endpoints documented in OpenAPI
- [ ] Backend test coverage 80%+
- [ ] Frontend TypeScript strict mode passes
- [ ] Docker builds and runs successfully

---

## SPECIAL REQUIREMENTS

### Security
- [x] Rate limiting on auth endpoints
- [x] Input validation on all endpoints
- [x] SQL injection prevention
- [x] XSS prevention
- [x] CSRF/state protection for OAuth
- [x] Dodo webhook signature verification

### Integrations
- [x] Email service for notifications
- [x] Dodo Payments
- [x] File upload service
- [x] Amazon product data source (to be decided: Keepa / Rainforest API / SP-API)
- [x] LLM API for review sentiment and summaries

---

## AGENTS

> These 6 agents will build your product in parallel:

| Agent | Role | Works On |
|-------|------|----------|
| DATABASE-AGENT | Creates all models and migrations | All database models |
| BACKEND-AGENT | Builds API endpoints and services | All modules' backends |
| FRONTEND-AGENT | Creates UI pages and components | All modules' frontends |
| DEVOPS-AGENT | Sets up Docker, CI/CD, environments | Infrastructure |
| TEST-AGENT | Writes unit and integration tests | All code |
| REVIEW-AGENT | Security and code quality audit | All code |

---

# READY?

```bash
/generate-prp INITIAL.md
```

Then:

```bash
/execute-prp PRPs/amzscoutiq-prp.md
```
