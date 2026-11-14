# PRP: AmzScoutIQ

> Implementation blueprint for parallel agent execution

---

## METADATA

| Field | Value |
|-------|-------|
| **Product** | AmzScoutIQ (alt. ASINPulse) |
| **Type** | SaaS |
| **Version** | 1.0 |
| **Created** | 2026-11-14 |
| **Complexity** | High (external data provider, LLM, billing, charts) |

---

## PRODUCT OVERVIEW

**Description:** An automated intelligence platform that tracks Amazon best-sellers, predicts emerging product trends, and calculates true FBA margins to help sellers launch winning private-label products.

**Value Proposition:** FBA private-label sellers, aggregator brands and product researchers get data-backed validation (trend, true margin, customer pain points) before committing inventory capital.

**MVP Scope:**
- [ ] User registration and login (email/password + Google OAuth)
- [ ] Discovery dashboard with best-seller filters (category, margin, saturation)
- [ ] Tracking lists + historical BSR chart per ASIN
- [ ] Profit & FBA fee calculator with saved scenarios
- [ ] Dodo Payments subscription

**Post-MVP:** Review & Sentiment Monitor, CSV export/import, BSR email alerts, analytics dashboard, admin panel.

> MVP scope was inferred (not supplied by the user). Phases below build MVP items first, then post-MVP modules.

---

## TECH STACK

| Layer | Technology | Skill Reference |
|-------|------------|-----------------|
| Backend | FastAPI + Python 3.11+ | skills/BACKEND.md |
| Frontend | React + TypeScript + Vite | skills/FRONTEND.md |
| Database | PostgreSQL + SQLAlchemy + Alembic | skills/DATABASE.md |
| Auth | JWT + bcrypt + Google OAuth | skills/BACKEND.md |
| UI | Tailwind + shadcn/ui + Framer Motion | skills/FRONTEND.md |
| Payments | Dodo Payments | skills/BACKEND.md |
| Testing | pytest + React Testing Library | skills/TESTING.md |
| Deployment | Docker + GitHub Actions | skills/DEPLOYMENT.md |

**External integrations (decision needed before Phase 2):**
- Amazon product data: Keepa / Rainforest API / SP-API (behind a `ProductDataProvider` interface so it can be swapped; ship a mock provider for dev/tests)
- LLM provider for review sentiment and summaries (behind an `LLMProvider` interface)
- SMTP / transactional email service

---

## DATABASE MODELS

### User
- id, email (unique), hashed_password (nullable for OAuth), full_name, is_active, is_verified, is_admin, oauth_provider, created_at

### RefreshToken
- id, user_id → User, token, expires_at, revoked

### Product
- id, asin (unique, 10-char uppercase), title, category, image_url, bsr, estimated_monthly_sales, estimated_monthly_revenue, price, rating, review_count, saturation_score (0-100), trend_score (0-100), updated_at

### BsrSnapshot (append-only)
- id, product_id → Product, bsr, price, estimated_sales, rating, review_count, captured_at (index on product_id, captured_at)

### TrackingList
- id, user_id → User, name, created_at

### TrackedProduct
- id, tracking_list_id → TrackingList, product_id → Product, added_at (unique on list+product)

### CostModel
- id, user_id → User, asin (nullable), name, unit_cost, shipping_cost, referral_fee, fba_fulfillment_fee, storage_fee, vat_tax, selling_price, target_roi, target_margin, net_profit, roi, margin, created_at (all money as `Numeric`)

### ReviewLog
- id, product_id → Product, review_id (unique per product), rating (1-5), review_text, sentiment_score, sentiment_label (positive/neutral/negative), pain_points (JSON), reviewed_at

### ReviewSummary
- id, product_id → Product, pros, cons, opportunities, generated_at

### Subscription
- id, user_id → User, plan, status, dodo_customer_id, dodo_subscription_id, current_period_end

---

## MODULES

### Module 1: Authentication
**Agents:** DATABASE-AGENT + BACKEND-AGENT + FRONTEND-AGENT

**Backend Endpoints:**
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | /api/v1/auth/register | Create account |
| POST | /api/v1/auth/login | Get tokens |
| POST | /api/v1/auth/refresh | Refresh token |
| POST | /api/v1/auth/logout | Revoke refresh token |
| GET | /api/v1/auth/me | Current user |
| PUT | /api/v1/auth/me | Update profile |
| GET | /api/v1/auth/google | Start Google OAuth |
| GET | /api/v1/auth/google/callback | OAuth callback (state verified) |
| POST | /api/v1/auth/forgot-password | Send reset email |
| POST | /api/v1/auth/reset-password | Reset password |

**Frontend Pages:**
| Route | Page | Components |
|-------|------|------------|
| /login | LoginPage | LoginForm, GoogleButton |
| /register | RegisterPage | RegisterForm |
| /forgot-password | ForgotPasswordPage | ForgotPasswordForm |
| /profile | ProfilePage (protected) | ProfileForm |

---

### Module 2: Product Tracker & Trend Discovery
**Agents:** DATABASE-AGENT + BACKEND-AGENT + FRONTEND-AGENT

**Backend Endpoints:**
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | /api/v1/products | Search/filter best-sellers (category, margin, saturation, trend) |
| GET | /api/v1/products/export | CSV export (post-MVP) |
| GET | /api/v1/products/{asin} | Product detail |
| GET | /api/v1/products/{asin}/history | Historical BSR/sales snapshots |
| GET | /api/v1/tracking-lists | List user's lists |
| POST | /api/v1/tracking-lists | Create list |
| PUT | /api/v1/tracking-lists/{id} | Rename list |
| DELETE | /api/v1/tracking-lists/{id} | Delete list |
| POST | /api/v1/tracking-lists/{id}/products | Add ASIN |
| DELETE | /api/v1/tracking-lists/{id}/products/{asin} | Remove ASIN |

**Services:** ProductDataProvider (Keepa/Rainforest adapter + mock), SnapshotJob (scheduled BSR capture), TrendScorer (saturation/trend scores)

**Frontend Pages:**
| Route | Page | Components |
|-------|------|------------|
| /dashboard | DashboardPage | ProductFeed, FilterBar, ProductCard |
| /products/:asin | ProductDetailPage | BsrChart, SalesChart (Framer Motion), AddToListButton |
| /tracking-lists | TrackingListsPage | ListManager, TrackedProductTable |

---

### Module 3: Profit & FBA Fee Calculator
**Agents:** DATABASE-AGENT + BACKEND-AGENT + FRONTEND-AGENT

**Backend Endpoints:**
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | /api/v1/calculator/calculate | Stateless calculation |
| POST | /api/v1/calculator/simulate | Price strategy comparison, break-even, ROI |
| GET | /api/v1/scenarios | List saved scenarios |
| POST | /api/v1/scenarios | Save scenario |
| GET | /api/v1/scenarios/{id} | Get scenario |
| PUT | /api/v1/scenarios/{id} | Update scenario |
| DELETE | /api/v1/scenarios/{id} | Delete scenario |

**Rules:** `Decimal` math only; net_profit = selling_price − (unit_cost + shipping + referral + FBA + storage + VAT); pure functions with unit tests.

**Frontend Pages:**
| Route | Page | Components |
|-------|------|------------|
| /calculator | CalculatorPage | CostForm, FeeBreakdown, PriceSimulator (real-time via client-side calc, validated by API) |
| /calculator/saved | SavedScenariosPage | ScenarioTable, ScenarioCard |

---

### Module 4: Billing (Dodo Payments)
**Agents:** DATABASE-AGENT + BACKEND-AGENT + FRONTEND-AGENT

**Backend Endpoints:**
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | /api/v1/billing/checkout | Create Dodo checkout session |
| POST | /api/v1/billing/webhook | Dodo webhook (signature verified, idempotent) |
| GET | /api/v1/billing/subscription | Current plan |

**Frontend Pages:**
| Route | Page | Components |
|-------|------|------------|
| /pricing | PricingPage | PlanCard |
| /settings/billing | BillingPage | SubscriptionStatus |

---

### Module 5: Review & Sentiment Monitor (post-MVP)
**Agents:** DATABASE-AGENT + BACKEND-AGENT + FRONTEND-AGENT

**Backend Endpoints:**
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | /api/v1/reviews/{asin} | Reviews, filter by stars/keyword |
| GET | /api/v1/reviews/{asin}/summary | AI summary: pros, cons, opportunities |
| POST | /api/v1/reviews/{asin}/analyze | Trigger sentiment analysis |
| GET | /api/v1/reviews/{asin}/pain-points | Aggregated recurring complaints |

**Services:** LLMProvider interface, SentimentService, PainPointExtractor

**Frontend Pages:**
| Route | Page | Components |
|-------|------|------------|
| /reviews/:asin | ReviewsPage | SentimentSummary, ProsConsList, ReviewFilters, PainPointChart |

---

### Module 6: Analytics & Settings (post-MVP)
**Agents:** BACKEND-AGENT + FRONTEND-AGENT

**Frontend Pages:**
| Route | Page | Components |
|-------|------|------------|
| /analytics | AnalyticsPage | UsageChart, ReportTable |
| /settings | SettingsPage | PreferencesForm |

---

### Module 7: Admin Panel (post-MVP)
**Agents:** BACKEND-AGENT + FRONTEND-AGENT

**Backend Endpoints:**
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | /api/v1/admin/users | List users (admin only) |
| PUT | /api/v1/admin/users/{id} | Update user status |
| GET | /api/v1/admin/stats | Platform statistics |

**Frontend Pages:**
| Route | Page | Components |
|-------|------|------------|
| /admin | AdminDashboardPage | StatsCards |
| /admin/users | AdminUsersPage | UserTable |

---

### Supporting Features (post-MVP)
- **Email Notifications:** welcome, verify email, password reset, BSR-change alerts (EmailService + templates)
- **File Uploads:** CSV import of ASIN lists/cost sheets, avatar upload (validate type and size, store outside web root or in object storage)

---

## PHASE EXECUTION PLAN

**Phase 1: Foundation (4 agents in parallel)**
- DATABASE-AGENT: All 10 models, Alembic migrations, database.py
- BACKEND-AGENT: main.py, config.py, project structure, provider interfaces
- FRONTEND-AGENT: Vite + Tailwind + shadcn/ui setup, folder structure, API client, auth context
- DEVOPS-AGENT: Dockerfiles, docker-compose, CI/CD, .env.example

**Validation Gate 1:** `pip install -r requirements.txt`, `alembic upgrade head`, `npm install`, `docker-compose config`

**Phase 2: Modules (backend + frontend in parallel per module)**
- Auth: JWT + Google OAuth endpoints + Login/Register/Forgot/Profile pages
- Product Tracker: provider adapter, endpoints, snapshot job + Dashboard/Detail/Lists pages
- Profit Calculator: calculation service, scenarios CRUD + Calculator/Saved pages
- Billing: Dodo checkout + webhook + Pricing/Billing pages
- Post-MVP: Review & Sentiment, Analytics/Settings, Admin, Email, Uploads

**Validation Gate 2:** `ruff check backend/`, `mypy backend/app`, `npm run lint`, `npm run type-check`

**Phase 3: Quality (3 agents in parallel)**
- TEST-AGENT: pytest + RTL, 80%+ coverage (calculator math and webhook signature are priority)
- REVIEW-AGENT: security audit (OAuth state, webhook verification, authz on user-owned resources, upload validation), performance review (snapshot queries)
- RESEARCH-AGENT: validate data-provider choice, Amazon FBA fee schedule accuracy, best practices

**Final Validation:** full test suite, docker build, health checks

> Note: `agents/` currently has orchestrator, backend, database and frontend agent definitions only. DEVOPS, TEST, REVIEW and RESEARCH agents have no definition files; the orchestrator should use general-purpose agents with the matching skill files for those roles.

---

## VALIDATION GATES

| Gate | Commands |
|------|----------|
| 1 | `alembic upgrade head`, `npm install`, `docker-compose config` |
| 2 | `ruff check backend/`, `npm run type-check` |
| 3 | `pytest --cov --cov-fail-under=80`, `npm test` |
| Final | `docker-compose up -d`, `curl localhost:8000/health` |

---

## ENVIRONMENT VARIABLES

```env
DATABASE_URL=postgresql://user:password@localhost:5432/amzscoutiq
SECRET_KEY=your-secret-key
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=30
GOOGLE_CLIENT_ID=your-client-id
GOOGLE_CLIENT_SECRET=your-secret
DODO_API_KEY=your-dodo-api-key
DODO_WEBHOOK_SECRET=your-dodo-webhook-secret
SMTP_HOST=smtp.example.com
SMTP_USER=your-user
SMTP_PASSWORD=your-password
AMAZON_DATA_API_KEY=your-data-provider-key
LLM_API_KEY=your-llm-key
VITE_API_URL=http://localhost:8000
```

---

## NEXT STEP

Execute with parallel agents:
/execute-prp PRPs/amzscoutiq-prp.md
