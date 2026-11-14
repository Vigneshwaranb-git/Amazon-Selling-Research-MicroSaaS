# CLAUDE.md - AmzScoutIQ Project Rules

> Project-specific rules for Claude Code. This file is read automatically.

---

## Project Overview

**Project Name:** AmzScoutIQ
**Description:** Automated intelligence platform that tracks Amazon best-sellers, predicts emerging product trends, and calculates true FBA margins for private-label sellers.
**Tech Stack:**
- Backend: FastAPI + Python 3.11+
- Frontend: React + Vite + TypeScript
- Database: PostgreSQL + SQLAlchemy
- Auth: JWT + Google OAuth (email/password also supported)
- UI: Tailwind + shadcn/ui + Framer Motion
- Payments: Dodo Payments

---

## Project Structure

```
amzscoutiq/
├── backend/
│   ├── app/
│   │   ├── main.py, config.py, database.py
│   │   ├── models/
│   │   │   ├── user.py, refresh_token.py
│   │   │   ├── product.py, bsr_snapshot.py, tracking_list.py
│   │   │   ├── cost_model.py
│   │   │   ├── review_log.py, review_summary.py
│   │   │   └── subscription.py
│   │   ├── schemas/, routers/, services/, auth/
│   ├── alembic/
│   ├── tests/
│   └── requirements.txt
├── frontend/
│   └── src/
│       ├── components/, pages/, hooks/, services/, context/, types/
├── .claude/commands/
├── skills/
├── agents/
└── PRPs/
```

---

## Code Standards

### Python (Backend)
```python
# ALWAYS use type hints and docstrings for public functions
def get_product(db: Session, asin: str) -> Product:
    """Return the product with the given ASIN."""
    pass

@router.get("/products/{asin}")
async def read_product(asin: str, db: Session = Depends(get_db)):
    pass
```

### TypeScript (Frontend)
```typescript
// ALWAYS define interfaces; NO any types
interface Product {
  asin: string;
  title: string;
  bsr: number;
  estimatedMonthlySales: number;
}

const fetchProduct = async (asin: string): Promise<Product> => { /* ... */ };
```

---

## Forbidden Patterns

### Backend
- ❌ Never use `print()` - use `logging`
- ❌ Never store plain-text passwords - use bcrypt
- ❌ Never hardcode secrets - use environment variables
- ❌ Never use `SELECT *` - specify columns
- ❌ Never skip input validation
- ❌ Never trust Dodo webhooks without verifying the signature

### Frontend
- ❌ Never use `any`
- ❌ Never leave `console.log` in production
- ❌ Never skip error handling in async operations
- ❌ Never use inline styles - use Tailwind / shadcn/ui

---

## Module-Specific Rules

### Product Tracker
- ASIN is unique and uppercase 10-char alphanumeric; validate on input
- Tracking lists and tracked products belong to a user (`user_id`)
- BSR snapshots are append-only; never update historical rows
- Saturation and trend scores are 0-100

### Profit Calculator
- Use `Decimal` for all money math on the backend; never floats
- Calculation must be deterministic and unit-tested
- CostModel belongs to a user; `asin` is optional
- net_profit = selling_price - (unit_cost + shipping + referral + FBA + storage + VAT)

### Review & Sentiment
- sentiment_label must be one of: positive, neutral, negative
- rating is 1-5; review_id is unique per product
- Do not send user personal data to the LLM provider

### Billing
- Subscription status comes only from verified Dodo webhooks, never the client

---

## API Conventions

- All endpoints prefixed with `/api/v1/`
- Plural nouns for resources: `/products`, `/tracking-lists`, `/scenarios`
- Status codes: 200 Success, 201 Created, 400 Bad Request, 401 Unauthorized, 403 Forbidden, 404 Not Found, 409 Conflict

---

## Authentication

### JWT Configuration
- Access token expires: 30 minutes
- Refresh token expires: 7 days
- Algorithm: HS256

### OAuth Providers
- Google OAuth 2.0 enabled
- Always verify state parameter for CSRF protection

---

## Environment Variables

```env
# Database
DATABASE_URL=postgresql://user:password@localhost:5432/amzscoutiq

# Auth
SECRET_KEY=your-secret-key-change-in-production
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=30

# Google OAuth
GOOGLE_CLIENT_ID=your-client-id
GOOGLE_CLIENT_SECRET=your-client-secret

# Dodo Payments
DODO_API_KEY=your-dodo-api-key
DODO_WEBHOOK_SECRET=your-dodo-webhook-secret

# Email
SMTP_HOST=smtp.example.com
SMTP_USER=your-user
SMTP_PASSWORD=your-password

# Amazon data / LLM
AMAZON_DATA_API_KEY=your-data-provider-key
LLM_API_KEY=your-llm-key

# Frontend
VITE_API_URL=http://localhost:8000
```

---

## Development Commands

```bash
# Backend
cd backend
pip install -r requirements.txt
alembic upgrade head
uvicorn app.main:app --reload

# Frontend
cd frontend
npm install
npm run dev

# Docker
docker-compose up -d

# Tests
pytest backend/tests -v
cd frontend && npm test

# Linting / validation
ruff check backend/ && pytest
cd frontend && npm run lint && npm run type-check
docker-compose build
```

---

## Commit Message Format

```
feat([module]): add [feature]
fix([module]): fix [bug]
refactor([module]): refactor [component]
test([module]): add tests for [feature]
docs: update [documentation]
```

---

## Skills Reference

| Task | Skill to Read |
|------|---------------|
| Database models | skills/DATABASE.md |
| API + Auth | skills/BACKEND.md |
| React + UI | skills/FRONTEND.md |
| Testing | skills/TESTING.md |
| Deployment | skills/DEPLOYMENT.md |

---

## Agent Coordination

For complex tasks, the ORCHESTRATOR coordinates:
- DATABASE-AGENT → Models + migrations
- BACKEND-AGENT → API development
- FRONTEND-AGENT → UI components
- TEST-AGENT → Testing
- REVIEW-AGENT → Code review
- DEVOPS-AGENT → Deployment

Read agent definitions in `/agents/` folder.
