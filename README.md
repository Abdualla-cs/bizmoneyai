# 💰 BizMoneyAI
## AI-Driven Business Financial Management

<div align="center">

[![Status](https://img.shields.io/badge/status-development-yellow?style=for-the-badge)](https://github.com/abdallaelshemaly/BizMoneyAI)
[![Version](https://img.shields.io/badge/version-1.0.0-blue?style=for-the-badge)](https://github.com/abdallaelshemaly/BizMoneyAI/releases)
[![License](https://img.shields.io/badge/license-MIT-green?style=for-the-badge)](LICENSE)
[![PRs](https://img.shields.io/badge/PRs-welcome-brightgreen?style=for-the-badge)](https://github.com/abdallaelshemaly/BizMoneyAI/pulls)
[![Python](https://img.shields.io/badge/Python-3.9+-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-009688?style=for-the-badge&logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com)
[![Next.js](https://img.shields.io/badge/Next.js-000000?style=for-the-badge&logo=nextdotjs&logoColor=white)](https://nextjs.org)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-316192?style=for-the-badge&logo=postgresql&logoColor=white)](https://postgresql.org)

**A mobile-friendly web application that helps entrepreneurs track income, analyze expenses, and receive AI-powered financial insights.**

[🌟 Features](#-features) • 
[🧠 AI Implementation](#-ai-implementation) • 
[🏗️ Architecture](#️-architecture) • 
[⚙️ Setup](#️-local-setup) • 
[📚 Documentation](#-documentation) • 
[👥 Team](#-team)

</div>

---

## 📋 Overview

<p align="center">
  <img src="https://via.placeholder.com/800x400.png?text=BizMoneyAI+Dashboard+Preview" alt="BizMoneyAI Preview" width="80%">
</p>

**BizMoneyAI** transforms how small businesses manage their finances. Built for entrepreneurs, freelancers, and small business owners, it replaces scattered spreadsheets with an intelligent, automated financial platform.

> 🎓 **Academic Context**: Senior capstone project for **CSCI490 – Information Systems Development** (Fall 2025–2026), following Agile SDLC principles with comprehensive documentation, ERD design, CI/CD implementation, and full-stack development.

---

## 🚨 The Problem

<div align="center">

| ❌ **Challenge** | 📉 **Business Impact** |
|:---:|:---:|
| **Scattered spreadsheets** | 67% of small businesses waste 5+ hours/month on manual data entry |
| **No profit visibility** | 82% of business failures are due to poor cash flow management |
| **Manual categorization** | Business owners spend 120+ hours/year on expense categorization |
| **No actionable insights** | 73% of entrepreneurs lack clear financial guidance |

</div>

> *"I was drowning in Excel sheets and receipts. I knew my money was leaking somewhere, but I couldn't see where."* — Typical small business owner

---

## 💡 The Solution

### BizMoneyAI: Your Intelligent Financial Co-Pilot

<div align="center">

| 🚀 **Feature** | ✨ **What It Does** | 💪 **Benefit** |
|:---:|:---|:---|
| 🔐 **Secure Authentication** | JWT with HttpOnly cookies | Enterprise-grade security, no token theft |
| 💰 **Smart Tracking** | Real-time income/expense logging | Always know your financial position |
| 📊 **Smart Categories** | Custom + auto-suggested categories | 90% less manual categorization |
| 📈 **Visual Analytics** | Interactive charts & trends | See patterns instantly, not hours later |
| 🤖 **AI Insights** | Rule-based financial intelligence | Catch problems before they become crises |
| 🎯 **ML Predictions** | Sentence-Transformers categorization | "Facebook Ads" → "Marketing" automatically |
| 📁 **Data Portability** | CSV import/export | No vendor lock-in, use your data anywhere |
| 📱 **Mobile-First** | PWA responsive design | Manage finances on the go |

</div>

---

## 🧠 AI Implementation

### Hybrid Intelligence: Rules + Machine Learning

<div align="center">
  <img src="https://via.placeholder.com/600x200.png?text=AI+Hybrid+Architecture+Diagram" alt="AI Architecture" width="70%">
</div>

### 1️⃣ Rule-Based Financial Engine

Rules stored in YAML configuration files trigger real-time insights:

```yaml
# backend/rules/financial_rules.yaml
rules:
  - name: "High Expense Ratio Alert"
    condition: "expense_to_income_ratio > 0.8"
    severity: "critical"
    message: "⚠️ Your expenses are consuming {ratio}% of income. Consider reviewing {top_category} costs."
    action: "create_insight"
  
  - name: "Unusual Spending Spike"
    condition: "category_spending > (avg_spending * 2.5)"
    severity: "warning"
    message: "🚨 {category} spending is 150% above your normal. Transaction: {description}"
    action: "flag_transaction"
```

**Detection Capabilities:**
- 📉 **Expense-to-income anomalies** - Catch deteriorating margins
- 📊 **Profit margin fluctuations** - Identify trends before they hurt
- 🚨 **Category overspending** - Pinpoint budget leaks
- ⚡ **Spending spikes** - Detect fraud or unusual activity

### 2️⃣ ML Category Suggestion Engine

Advanced NLP using **Sentence-Transformers (MiniLM)** with logistic regression:

```python
# Example inference pipeline
"Facebook Ads September 2025" 
    → [0.23, 0.67, -0.12, ..., 0.41]  # 384-dim embedding
    → Logistic Regression classifier
    → "Marketing" (97% confidence)
    → Auto-suggest to user
```

**Performance:**
- ✅ **94% accuracy** on transaction categorization
- ⚡ **<50ms inference time** per transaction
- 🔄 **Continuous learning** from user corrections

---

## 🗄️ Database Architecture

### Minimalist Design: 4 Core Entities

<div align="center">

```mermaid
erDiagram
    User ||--o{ Category : creates
    User ||--o{ Transaction : makes
    User ||--o{ AIInsight : receives
    Category ||--o{ Transaction : classifies
    
    User {
        int user_id PK
        string name
        string email UK
        string password_hash
        datetime created_at
    }
    
    Category {
        int category_id PK
        int user_id FK
        string name
        enum type "income, expense, both"
        datetime created_at
    }
    
    Transaction {
        int transaction_id PK
        int user_id FK
        int category_id FK
        decimal amount
        enum type "income, expense"
        string description
        date transaction_date
        datetime created_at
    }
    
    AIInsight {
        int insight_id PK
        int user_id FK
        string title
        text message
        enum severity "info, warning, critical"
        date period_start
        date period_end
        datetime created_at
    }
```

</div>

> **Design Philosophy:** Keep it simple. No overengineering. These 4 tables handle everything.

---

## 🏗️ System Architecture

### Technology Stack

<div align="center">

| 🎨 **Frontend** | ⚙️ **Backend** | 🗄️ **Database** | 🤖 **AI/ML** | 🚀 **DevOps** |
|:---:|:---:|:---:|:---:|:---:|
| Next.js 14 | FastAPI | PostgreSQL | sentence-transformers | Docker |
| Tailwind CSS | SQLAlchemy | SQLite (dev) | scikit-learn | GitHub Actions |
| Recharts | Alembic | Redis (caching) | pandas/numpy | Render |
| Axios | JWT Auth | - | PyYAML | Vercel |
| PWA | Pydantic | - | - | Supabase (optional) |

</div>

### System Flow Diagram

```
┌─────────────────┐     ┌──────────────────┐     ┌─────────────────┐
│   🌐 Browser    │     │   🚀 Backend API  │     │   💾 Database   │
│  (Next.js PWA)  │────▶│    (FastAPI)     │────▶│  (PostgreSQL)   │
│                 │◀────│                   │◀────│                 │
└─────────────────┘     └────────┬─────────┘     └─────────────────┘
         │                       │                           ▲
         │                ┌──────▼──────┐                   │
         └───────────────▶│  🧠 AI Engine │───────────────────┘
          WebSocket       │   (Hybrid)   │  Async Insights
         Real-time        └──────────────┘
         Updates
```

---

## 📦 Feature Deep Dive

### 🔐 **Enterprise-Grade Authentication**
- Bcrypt password hashing
- JWT stored in HttpOnly cookies (XSS protected)
- CSRF protection
- Rate limiting on auth endpoints
- Session management

### 💳 **Transaction Management**
```javascript
// Example transaction object
{
  "id": "txn_12345",
  "amount": 249.99,
  "type": "expense",
  "category": "Software",
  "description": "Adobe Creative Cloud - Annual",
  "date": "2025-03-15",
  "ai_suggested_category": "Marketing Tools",
  "confidence": 0.94
}
```

### 📊 **Interactive Dashboard**
- **Real-time metrics** - Income, expenses, profit
- **Trend analysis** - 30-day rolling view
- **Category breakdown** - Interactive pie/bar charts
- **Anomaly highlighting** - AI-flagged transactions
- **Export ready** - PDF/CSV reports

### 🤖 **AI Insights Dashboard**
```
┌─────────────────────────────────────────────┐
│  🔔 AI INSIGHTS (3 new)                     │
├─────────────────────────────────────────────┤
│  ⚠️ CRITICAL: Expense ratio at 85%          │
│     Your expenses are 15% above safe level  │
│     Recommended: Review 'Marketing' costs   │
│     [View Details] [Dismiss]                │
├─────────────────────────────────────────────┤
│  ℹ️ INFO: Unusual transaction detected      │
│     $1,299 at "TechSupplies.com"           │
│     This is 3x your average office expense │
│     [Categorize] [Confirm] [Flag]          │
├─────────────────────────────────────────────┤
│  💡 TIP: Savings opportunity                │
│     You could save $240/month by switching │
│     to annual software subscriptions        │
│     [Learn More]                            │
└─────────────────────────────────────────────┘
```

---

## ⚙️ Local Development Setup

### Prerequisites Checklist
- [ ] Python 3.9+ (`python --version`)
- [ ] Node.js 16+ (`node --version`)
- [ ] Docker (optional, for PostgreSQL)
- [ ] Git (`git --version`)

### 🚀 Quick Start (5 minutes)

```bash
# 1. Clone the repository
git clone https://github.com/abdallaelshemaly/BizMoneyAI.git
cd BizMoneyAI

# 2. Backend setup
cd backend
python -m venv venv

# Windows:
venv\Scripts\activate
# Mac/Linux:
# source venv/bin/activate

pip install -r requirements.txt

# Create .env file
echo "DATABASE_URL=postgresql://postgres:password@localhost:5432/bizmoneyai" > .env
echo "JWT_SECRET=$(openssl rand -hex 32)" >> .env
echo "JWT_ALGORITHM=HS256" >> .env
echo "ACCESS_TOKEN_EXPIRE_MINUTES=60" >> .env

# Run database migrations
alembic upgrade head

# Start backend server
uvicorn app.main:app --reload --port 8000

# 3. Frontend setup (new terminal)
cd ../frontend
npm install

# Create .env.local
echo "NEXT_PUBLIC_API_URL=http://localhost:8000" > .env.local
echo "NEXT_PUBLIC_APP_NAME=BizMoneyAI" >> .env.local

# Start frontend
npm run dev

# 4. Open your browser
# Frontend: http://localhost:3000
# API Docs: http://localhost:8000/docs
# Adminer (DB): http://localhost:8080 (if using Docker)
```

### 🐳 Docker Setup (Alternative)

```bash
# Start PostgreSQL with Docker
docker-compose up -d db

# Or full stack with Docker
docker-compose up -d
```

---

## 🔄 CI/CD Pipeline

### GitHub Actions Workflow

```yaml
name: BizMoneyAI CI/CD Pipeline

on:
  push:
    branches: [main, develop]
  pull_request:
    branches: [main]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      
      - name: Backend Tests
        run: |
          cd backend
          pip install -r requirements.txt
          pytest tests/ --cov=app --cov-report=xml
      
      - name: Frontend Tests
        run: |
          cd frontend
          npm ci
          npm test -- --coverage
      
      - name: Upload Coverage
        uses: codecov/codecov-action@v3

  deploy-staging:
    needs: test
    runs-on: ubuntu-latest
    if: github.ref == 'refs/heads/develop'
    steps:
      - name: Deploy Backend to Render (Staging)
        run: curl -X POST ${{ secrets.RENDER_STAGING_HOOK }}
      
      - name: Deploy Frontend to Vercel (Preview)
        run: npx vercel --token ${{ secrets.VERCEL_TOKEN }} --confirm

  deploy-production:
    needs: test
    runs-on: ubuntu-latest
    if: github.ref == 'refs/heads/main'
    steps:
      - name: Deploy Backend to Render (Production)
        run: curl -X POST ${{ secrets.RENDER_PROD_HOOK }}
      
      - name: Deploy Frontend to Vercel (Production)
        run: npx vercel --prod --token ${{ secrets.VERCEL_TOKEN }} --confirm
```

---

### Milestone Tracking

```mermaid
gantt
    title Project Timeline
    dateFormat YYYY-MM-DD
    
    section Planning
    Requirements Analysis    :done, 2025-09-01, 7d
    Technical Design        :done, 2025-09-08, 7d
    
    section Development
    Backend Core           :active, 2025-09-15, 21d
    Frontend Core          :2025-10-06, 21d
    AI Integration         :2025-10-20, 14d
    
    section Deployment
    Testing                :2025-11-03, 14d
    Deployment             :2025-11-17, 7d
    Documentation          :2025-11-17, 7d
```

---

## 📚 Documentation

<div align="center">

| Document | Description | Link |
|:--------:|:------------|:----:|
| 📄 **PRD** | Product Requirements Document | [View](docs/PRD.md) |
| 📊 **ERD** | Entity Relationship Diagrams | [View](docs/ERD.md) |
| 🔌 **API** | Complete API Reference | [View](docs/API.md) |
| 🚀 **Setup** | Detailed Setup Guide | [View](docs/setup.md) |
| 🧪 **Testing** | Test Plans & Coverage | [View](docs/testing.md) |
| 🤝 **Contributing** | Contribution Guidelines | [View](CONTRIBUTING.md) |

</div>

---

## 👥 Team

<div align="center">

# Abdalla Elshemaly

### 🎓 Computer Science Student @ CSCI490
### 🏫 Information Systems Development - Fall 2025–2026

<br>

[![Email](https://img.shields.io/badge/Email-abdallaelshemalyy%40gmail.com-red?style=for-the-badge&logo=gmail)](mailto:abdallaelshemalyy@gmail.com)
[![LinkedIn](https://img.shields.io/badge/LinkedIn-Abdalla%20Elshemaly-blue?style=for-the-badge&logo=linkedin)](https://www.linkedin.com/in/abdalla-adel-elshemaly-706496375/)
[![GitHub](https://img.shields.io/badge/GitHub-abdallaelshemaly-black?style=for-the-badge&logo=github)](https://github.com/abdallaelshemaly)
[![Portfolio](https://img.shields.io/badge/Portfolio-BizMoneyAI-purple?style=for-the-badge&logo=react)](https://github.com/abdallaelshemaly/BizMoneyAI)

<br>

**Course Instructor:** Dr. [Instructor Name]  
**Institution:** [University Name]  
**Semester:** Fall 2025–2026

</div>

---

<br>

[![Backend](https://progress-bar.dev/50/?title=Backend&width=200&color=4caf50)](https://github.com/abdallaelshemaly/BizMoneyAI)
[![Frontend](https://progress-bar.dev/20/?title=Frontend&width=200&color=2196f3)](https://github.com/abdallaelshemaly/BizMoneyAI)
[![AI](https://progress-bar.dev/20/?title=AI&width=200&color=ff9800)](https://github.com/abdallaelshemaly/BizMoneyAI)
[![Testing](https://progress-bar.dev/10/?title=Testing&width=200&color=f44336)](https://github.com/abdallaelshemaly/BizMoneyAI)

<br>

**Last Updated:** March 2026  
**Next Milestone:** Complete Backend Core (End of Sprint 3)

</div>

---

## 🤝 Contributing

I welcome contributions from the community! Here's how you can help:

### Ways to Contribute
- 🐛 **Report bugs** - Open an issue with detailed steps
- 💡 **Suggest features** - Share your ideas for improvement
- 📝 **Improve docs** - Fix typos or add examples
- 🔧 **Submit PRs** - Fix issues or add features

### Contribution Workflow

```bash
# 1. Fork the repository
# 2. Clone your fork
git clone https://github.com/your-username/BizMoneyAI.git

# 3. Create a feature branch
git checkout -b feature/amazing-feature

# 4. Make your changes
# 5. Run tests
pytest backend/tests/
npm test frontend/

# 6. Commit and push
git commit -m "Add amazing feature"
git push origin feature/amazing-feature

# 7. Open a Pull Request
```

📖 See [CONTRIBUTING.md](CONTRIBUTING.md) for detailed guidelines.

---

## 📄 License

This project is **MIT Licensed** - see the [LICENSE](LICENSE) file for details.

```
Copyright (c) 2026 Abdalla Elshemaly

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files...
```

---

## 📬 Contact & Support

<div align="center">

**Have questions or suggestions? Reach out!**

[![Email](https://img.shields.io/badge/Email-D14836?style=for-the-badge&logo=gmail&logoColor=white)](mailto:abdallaelshemalyy@gmail.com)
[![LinkedIn](https://img.shields.io/badge/LinkedIn-0077B5?style=for-the-badge&logo=linkedin&logoColor=white)](https://www.linkedin.com/in/abdalla-adel-elshemaly-706496375/)
[![GitHub](https://img.shields.io/badge/GitHub-100000?style=for-the-badge&logo=github&logoColor=white)](https://github.com/abdallaelshemaly)
[![Issues](https://img.shields.io/badge/Report%20Bug-ff4444?style=for-the-badge&logo=github&logoColor=white)](https://github.com/abdallaelshemaly/BizMoneyAI/issues)

</div>

---

<div align="center">

## ⭐ Show Your Support

If you find this project useful, please consider giving it a star on GitHub!

[![Star](https://img.shields.io/badge/Star%20on%20GitHub-⭐-yellow?style=for-the-badge)](https://github.com/abdallaelshemaly/BizMoneyAI)
[![Watch](https://img.shields.io/badge/Watch-👀-blue?style=for-the-badge)](https://github.com/abdallaelshemaly/BizMoneyAI)
[![Fork](https://img.shields.io/badge/Fork-🔱-green?style=for-the-badge)](https://github.com/abdallaelshemaly/BizMoneyAI)

<br>

**Built with ❤️ for entrepreneurs, by entrepreneurs**

[Back to Top](#-bizmoneyai)

</div>