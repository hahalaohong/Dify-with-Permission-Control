# Dify with Permission Control

> **This is a fork of [Dify](https://github.com/langgenius/dify) for learning purposes only.** It adds a Permission Management Center on top of the open-source Dify Community Edition while keeping all original features intact.

## What is Dify?

[Dify](https://dify.ai) is an open-source platform for developing LLM applications. Its intuitive interface combines agentic AI workflows, RAG pipelines, agent capabilities, model management, observability features, and more — allowing you to quickly move from prototype to production.

## What This Fork Adds

This project extends Dify with a **centralized Permission Management Center**, enabling fine-grained access control for both **Apps** and **Knowledge Bases** at the member level.

### Permission Model

A three-tier permission model (consistent with Dify's existing Knowledge Base permissions) is applied to Apps:

| Mode | Description |
|------|-------------|
| **Only Creator** | Only the resource creator can access it |
| **All Team Members** | All members in the workspace can access it |
| **Partial Members** | Only the creator and explicitly authorized members can access it |

### Key Features

- **App-Level Permission Control**: Apps now support the same three-tier permission model as Knowledge Bases. Admins can control which members can see and access each app.
- **Centralized Permission Management Page**: A new "Permissions" tab in Account Settings allows admins to manage all resource access from a single, member-centric view with search and batch authorization.
- **Role-Based Visibility**: Owners and Admins can access all resources regardless of permission settings. Editors and Normal users only see resources they are authorized to access.
- **Minimal Invasiveness**: Implemented via a new `app_permissions` table and `AppPermissionService`, with minimal changes to existing Dify code.

### Changed Files

**Backend (api/)**

| File | Change |
|------|--------|
| `migrations/versions/..._add_app_permissions.py` | New Alembic migration: `app_permissions` table + `apps.permission` column |
| `models/dataset.py` | Added `AppPermissionEnum` and `AppPermission` model |
| `models/model.py` | Added `permission` field to `App` model |
| `services/app_permission_service.py` | New permission service layer |
| `controllers/console/workspace/permissions.py` | New permission management API endpoints |
| `services/app_service.py` | Added permission filtering to `get_paginate_apps()` |

**Frontend (web/)**

| File | Change |
|------|--------|
| `models/permission.ts` | New TypeScript type definitions |
| `service/permission.ts` | New API service functions |
| `app/components/header/account-setting/permission-page/index.tsx` | New permission management page component |
| `app/components/header/account-setting/index.tsx` | Added Permissions tab entry |
| `app/components/header/account-setting/constants.ts` | Added `PERMISSIONS` tab constant |
| `i18n/en-US/common.json` | English translations |
| `i18n/zh-Hans/common.json` | Chinese translations |

## Quick Start

> Minimum requirements: CPU >= 2 Core, RAM >= 4 GiB, Docker 24.0+, Docker Compose v2.20+

```bash
git clone https://github.com/hahalaohong/Dify-with-Permission-Control.git
cd Dify-with-Permission-Control/docker
cp .env.example .env
docker compose up -d
```

After running, access the Dify dashboard at [http://localhost/install](http://localhost/install) to start the initialization process.

## Original Dify Features

All original Dify features are fully preserved:

1. **Workflow** — Build and test AI workflows on a visual canvas
2. **Comprehensive Model Support** — Integration with hundreds of LLMs (GPT, Mistral, Llama3, etc.)
3. **Prompt IDE** — Intuitive prompt crafting and model comparison
4. **RAG Pipeline** — Document ingestion to retrieval with PDF/PPT support
5. **Agent Capabilities** — LLM Function Calling / ReAct with 50+ built-in tools
6. **LLMOps** — Log monitoring, performance analysis, and continuous optimization
7. **Backend-as-a-Service** — Full API access for all features

## Disclaimer

This project is intended **for learning and educational purposes only**. It demonstrates how to extend Dify's open-source Community Edition with enterprise-level permission management capabilities. For production use, please refer to the [official Dify repository](https://github.com/langgenius/dify).

## License

This project follows the same license as the original Dify project. See [LICENSE](./LICENSE) for details.
