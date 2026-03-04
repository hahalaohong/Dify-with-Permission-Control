# Dify 权限管理中心 - 开发文档

## 1. 项目概述

为 Dify 平台增加一个集中化的权限管理中心，支持管理员按成员维度统一管理知识库和应用的访问权限。该功能位于「账户设置」页面，以用户为中心（选择成员 -> 配置其可访问的资源）。

### 1.1 权限模型

采用三级权限模式（与 Dify 已有的知识库权限模型一致）：

| 权限模式 | 枚举值 | 说明 |
|---------|--------|------|
| 仅创建者 | `only_me` | 仅资源创建者可访问 |
| 全体成员 | `all_team_members` | 租户下所有成员可访问 |
| 部分成员 | `partial_members` | 仅创建者 + 被授权的成员可访问 |

### 1.2 角色与权限

- **Owner / Admin**：可以访问所有资源，不受权限限制；可以管理其他成员的权限
- **Editor / Normal / Dataset Operator**：受权限模式约束，只能看到被授权的资源

---

## 2. 数据库设计

### 2.1 新增表：`app_permissions`

存储应用级别的「部分成员」授权记录（类似已有的 `dataset_permissions` 表）。

```sql
CREATE TABLE app_permissions (
    id          UUID PRIMARY KEY,
    app_id      UUID NOT NULL,
    account_id  UUID NOT NULL,
    tenant_id   UUID NOT NULL,
    has_permission BOOLEAN NOT NULL DEFAULT TRUE,
    created_at  TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_app_permissions_app_id ON app_permissions(app_id);
CREATE INDEX idx_app_permissions_account_id ON app_permissions(account_id);
CREATE INDEX idx_app_permissions_tenant_id ON app_permissions(tenant_id);
```

### 2.2 修改表：`apps`

新增 `permission` 字段：

```sql
ALTER TABLE apps ADD COLUMN permission VARCHAR(255) DEFAULT 'all_team_members';
```

### 2.3 迁移文件

- **文件**: `api/migrations/versions/2026_02_12_1600-a1b2c3d4e5f6_add_app_permissions.py`
- **Revision**: `a1b2c3d4e5f6`
- **Down Revision**: `fce013ca180e`（需根据当前 migration head 调整）

---

## 3. 后端实现

### 3.1 ORM 模型

#### `AppPermissionEnum` (api/models/dataset.py:1229)

```python
class AppPermissionEnum(enum.StrEnum):
    ONLY_ME = "only_me"
    ALL_TEAM = "all_team_members"
    PARTIAL_TEAM = "partial_members"
```

#### `AppPermission` (api/models/dataset.py:1235)

```python
class AppPermission(TypeBase):
    __tablename__ = "app_permissions"
    id: Mapped[str]           # UUID, PK
    app_id: Mapped[str]       # 应用 ID
    account_id: Mapped[str]   # 用户 ID
    tenant_id: Mapped[str]    # 租户 ID
    has_permission: Mapped[bool]  # 默认 True
    created_at: Mapped[datetime]
```

#### `App.permission` 字段 (api/models/model.py:109)

```python
permission: Mapped[str | None] = mapped_column(
    String(255), nullable=True, server_default=sa.text("'all_team_members'")
)
```

### 3.2 服务层

**文件**: `api/services/app_permission_service.py`

`AppPermissionService` 提供以下方法：

| 方法 | 说明 |
|------|------|
| `get_app_partial_member_list(app_id)` | 获取应用的部分成员 ID 列表 |
| `update_partial_member_list(tenant_id, app_id, user_list)` | 更新应用的部分成员列表 |
| `clear_partial_member_list(app_id)` | 清空应用的部分成员列表 |
| `check_app_permission(user, app)` | 检查用户是否有权访问某应用 |
| `get_user_accessible_app_ids(tenant_id, user_id)` | 获取用户可访问的所有应用 ID |
| `get_user_permission_summary(tenant_id, user_id)` | 获取用户的权限摘要（知识库+应用） |
| `update_user_permissions(tenant_id, user_id, dataset_ids, app_ids)` | 更新用户的所有权限 |

### 3.3 API 端点

**文件**: `api/controllers/console/workspace/permissions.py`

| 端点 | 方法 | 说明 |
|------|------|------|
| `/workspaces/current/permissions` | GET | 权限总览：列出所有成员及其可访问资源数量 |
| `/workspaces/current/permissions/members/<id>` | GET | 获取某成员的详细权限（每个知识库/应用的访问状态） |
| `/workspaces/current/permissions/members/<id>` | PUT | 更新某成员的权限（传入 dataset_ids + app_ids） |
| `/workspaces/current/permissions/resources` | GET | 获取所有资源列表（知识库+应用） |
| `/workspaces/current/permissions/resources/<type>/<id>` | PUT | 修改资源的权限模式（only_me/all_team_members/partial_members） |

所有端点均需 `@is_admin_or_owner_required` 权限。

#### 请求/响应示例

**GET /workspaces/current/permissions**
```json
{
  "members": [
    {
      "id": "uuid",
      "name": "hahalaohong",
      "email": "k.sunjie@outlook.com",
      "avatar": null,
      "role": "normal",
      "dataset_count": 1,
      "app_count": 1
    }
  ],
  "total_datasets": 1,
  "total_apps": 2
}
```

**PUT /workspaces/current/permissions/members/<id>**
```json
{
  "dataset_ids": ["dataset-uuid-1"],
  "app_ids": ["app-uuid-1"]
}
```

**PUT /workspaces/current/permissions/resources/app/<id>**
```json
{
  "permission": "partial_members"
}
```

### 3.4 应用列表权限过滤（核心执行逻辑）

**文件**: `api/services/app_service.py` -> `AppService.get_paginate_apps()`

原始代码无权限过滤，所有用户均可看到全部应用。修改后增加了权限过滤逻辑：

```python
# Permission filtering based on App.permission and AppPermission records
user = current_user
if user and hasattr(user, "current_role") and user.current_role not in (
    TenantAccountRole.OWNER,
    TenantAccountRole.ADMIN,
):
    app_permissions = (
        db.session.query(AppPermission.app_id)
        .filter(AppPermission.account_id == user_id, AppPermission.tenant_id == tenant_id)
        .all()
    )
    permitted_app_ids = {str(ap.app_id) for ap in app_permissions}

    if permitted_app_ids:
        filters.append(
            sa.or_(
                App.permission == AppPermissionEnum.ALL_TEAM,
                App.permission.is_(None),
                sa.and_(App.permission == AppPermissionEnum.ONLY_ME, App.created_by == user_id),
                sa.and_(App.permission == AppPermissionEnum.PARTIAL_TEAM, App.id.in_(permitted_app_ids)),
                sa.and_(App.permission == AppPermissionEnum.PARTIAL_TEAM, App.created_by == user_id),
            )
        )
    else:
        filters.append(
            sa.or_(
                App.permission == AppPermissionEnum.ALL_TEAM,
                App.permission.is_(None),
                sa.and_(App.permission == AppPermissionEnum.ONLY_ME, App.created_by == user_id),
                sa.and_(App.permission == AppPermissionEnum.PARTIAL_TEAM, App.created_by == user_id),
            )
        )
```

**注意**：知识库侧的权限过滤已在 `DatasetService.get_datasets()` 中原生实现（使用 `DatasetPermission` 表），无需额外修改。

---

## 4. 前端实现

### 4.1 TypeScript 类型定义

**文件**: `web/models/permission.ts`

```typescript
export interface MemberPermissionSummary {
  id: string; name: string; email: string; avatar: string | null;
  role: string; dataset_count: number; app_count: number;
}

export interface PermissionOverviewResponse {
  members: MemberPermissionSummary[]; total_datasets: number; total_apps: number;
}

export interface ResourcePermission {
  id: string; name: string;
  permission: 'only_me' | 'all_team_members' | 'partial_members';
  created_by: string | null; has_access: boolean; is_partial: boolean;
}

export interface MemberPermissionDetail {
  member: { id: string; name: string; email: string; avatar: string | null; };
  datasets: ResourcePermission[]; apps: ResourcePermission[];
  accessible_dataset_ids: string[]; accessible_app_ids: string[];
}
```

### 4.2 API 服务函数

**文件**: `web/service/permission.ts`

| 函数 | 说明 |
|------|------|
| `fetchPermissionOverview()` | GET 权限总览 |
| `fetchMemberPermissions(memberId)` | GET 成员权限详情 |
| `updateMemberPermissions(memberId, data)` | PUT 更新成员权限 |
| `fetchPermissionResources()` | GET 所有资源列表 |
| `updateResourcePermissionMode(type, id, permission)` | PUT 更新资源权限模式 |

### 4.3 权限管理页面组件

**文件**: `web/app/components/header/account-setting/permission-page/index.tsx`

**布局**：两栏设计
- **左栏（1/3 宽）**：成员列表 + 搜索框，显示每个成员可访问的知识库/应用数量
- **右栏（2/3 宽）**：选中成员的权限编辑面板

**每个资源行的交互**：
```
[Checkbox] [资源名称] [权限模式下拉框] [访问状态图标]
```

- **Checkbox**：仅当权限模式为 `partial_members` 时可交互；勾选/取消勾选控制该成员是否有权访问
- **权限模式下拉框**：使用 `SimpleSelect` 组件（非 Combobox 搜索框），选项为「仅创建者/全体成员/部分成员」，设置 `notClearable` 防止误清空
- **访问状态图标**：绿色圆形勾选表示该成员当前有访问权限
- **保存按钮**：提交 checkbox 的勾选状态

**关键技术点**：
- `permissionModeOptions` 使用 `useMemo` 缓存，避免 SimpleSelect 不必要的重渲染
- 权限模式切换时立即调用 API 更新资源的 `permission` 字段，然后重新加载数据刷新 UI
- checkbox 状态由 `selectedDatasetIds` / `selectedAppIds` 管理，点击保存时批量提交

### 4.4 入口集成

**文件修改列表**：

| 文件 | 修改内容 |
|------|---------|
| `web/app/components/header/account-setting/constants.ts` | 新增 `PERMISSIONS: 'permissions'` 到 `ACCOUNT_SETTING_TAB` |
| `web/app/components/header/account-setting/index.tsx` | 导入 `PermissionPage`、添加 permissions 菜单项（带 RiShieldKeyholeFill/Line 图标）、渲染条件判断 |

### 4.5 i18n 翻译

**文件**: `web/i18n/en-US/common.json` 和 `web/i18n/zh-Hans/common.json`

新增翻译 key（使用 `t('permission.xxx', { ns: 'common' })` 格式）：

| Key | 英文 | 中文 |
|-----|------|------|
| `permission.title` | Permission Management | 权限管理 |
| `permission.description` | Manage resource access... | 管理每个成员的资源访问权限... |
| `permission.datasets` | Knowledge | 知识库 |
| `permission.apps` | Apps | 应用 |
| `permission.datasetAccess` | Knowledge Access | 知识库访问权限 |
| `permission.appAccess` | App Access | 应用访问权限 |
| `permission.onlyMe` | Only creator | 仅创建者 |
| `permission.allTeam` | All team members | 全体成员 |
| `permission.partial` | Partial members | 部分成员 |
| `permission.searchMember` | Search members... | 搜索成员... |
| `permission.selectMember` | Select a member... | 从左侧面板选择一个成员... |
| `permission.noPermission` | You do not have... | 您没有权限访问此页面 |
| `settings.permissions` | Permissions | 权限管理 |

---

## 5. Docker 部署

### 5.1 构建流程

由于 Docker Desktop 内存限制（Next.js Turbopack 编译需要 > 7GB），采用**本地预构建 + Docker 打包**方案：

1. **下载 Node.js 二进制**（`/tmp/node-local/`）
2. **本地执行 `pnpm build:docker`** 生成 `.next/standalone` 和 `.next/static`
3. **使用 `Dockerfile.prebuilt`** 将预构建产物打包为 Docker 镜像
4. API 镜像直接使用标准 `Dockerfile` 构建

### 5.2 Dockerfile.prebuilt

**文件**: `web/Dockerfile.prebuilt`

轻量 Dockerfile，跳过构建阶段，直接复制预构建的 standalone 输出：

```dockerfile
FROM node:24-alpine AS base
RUN apk add --no-cache tzdata && corepack enable

FROM base AS production
ENV NODE_ENV=production
RUN pnpm add -g pm2
WORKDIR /app/web
COPY --chown=dify:dify public ./public
COPY --chown=dify:dify .next/standalone/ ./
COPY --chown=dify:dify .next/static ./.next/static
COPY --chown=dify:dify --chmod=755 docker/entrypoint.sh ./entrypoint.sh
ENTRYPOINT ["/bin/sh", "./entrypoint.sh"]
```

**注意**：构建前需临时注释 `.dockerignore` 中的 `.next` 行，构建完成后恢复。

### 5.3 构建与部署命令

```bash
# 1. 本地构建 Next.js（需要 Node.js）
export PATH="/tmp/node-local/bin:$PATH"
cd web/
NODE_ENV=production EDITION=SELF_HOSTED pnpm build:docker

# 2. 构建 Docker 镜像
# Web（修改 .dockerignore 后）
docker build -f Dockerfile.prebuilt -t dify-web:custom .

# API
docker build -f api/Dockerfile -t dify-api:custom api/

# 3. 启动所有服务
cd docker/
docker compose up -d

# 4. 如果单独重启了 API 容器，需要重启 nginx 刷新上游 IP
docker compose restart nginx
```

---

## 6. 修改文件清单

### 后端（api/）

| 文件路径 | 操作 | 说明 |
|---------|------|------|
| `migrations/versions/2026_02_12_1600-a1b2c3d4e5f6_add_app_permissions.py` | 新增 | Alembic 迁移：创建 app_permissions 表 + apps.permission 列 |
| `models/dataset.py` | 修改 | 新增 AppPermissionEnum、AppPermission 模型 |
| `models/model.py` | 修改 | App 模型新增 permission 字段 |
| `services/app_permission_service.py` | 新增 | 权限服务层 |
| `controllers/console/workspace/permissions.py` | 新增 | 权限管理 API 端点 |
| `services/app_service.py` | 修改 | get_paginate_apps() 加入权限过滤逻辑 |

### 前端（web/）

| 文件路径 | 操作 | 说明 |
|---------|------|------|
| `models/permission.ts` | 新增 | TypeScript 类型定义 |
| `service/permission.ts` | 新增 | API 服务函数 |
| `app/components/header/account-setting/permission-page/index.tsx` | 新增 | 权限管理页面组件 |
| `app/components/header/account-setting/index.tsx` | 修改 | 添加权限管理 Tab 入口 |
| `app/components/header/account-setting/constants.ts` | 修改 | 新增 PERMISSIONS Tab 常量 |
| `i18n/en-US/common.json` | 修改 | 英文翻译 |
| `i18n/zh-Hans/common.json` | 修改 | 中文翻译 |

### Docker

| 文件路径 | 操作 | 说明 |
|---------|------|------|
| `web/Dockerfile.prebuilt` | 新增 | 轻量预构建 Dockerfile |

---

## 7. 开发过程中的问题与解决

### 7.1 i18n 翻译 key 显示为原始字符串

**问题**：页面显示 `common.permission.title` 而非翻译后的文本。

**原因**：Dify 的 i18n 使用 react-i18next 的命名空间机制，key 格式应为 `t('permission.title', { ns: 'common' })` 而非 `t('common.permission.title')`。

**参考**：`members-page` 组件使用 `t('members.owner', { ns: 'common' })` 格式。

### 7.2 Select 组件交互问题

**问题**：权限模式下拉框使用了 `Select`（Combobox 搜索模式），点击后变成文本输入框而非下拉选择。

**解决**：改用 `SimpleSelect`（Listbox 模式），添加 `notClearable` 防止误清空。

### 7.3 Avatar 组件缺少 avatar prop

**问题**：`<Avatar name={member.name} />` 不显示用户头像。

**解决**：改为 `<Avatar name={member.name} avatar={member.avatar} size={36} />`。

### 7.4 成员角色未加载

**问题**：API 返回的成员 role 始终为 null。

**原因**：仅查询 `Account` 表，未 JOIN `TenantAccountJoin` 表。

**解决**：修改查询为 `db.session.query(Account, TenantAccountJoin.role).join(...)`，手动赋值 `member.role = role`。

### 7.5 迁移依赖链冲突

**问题**：`down_revision` 指向旧的 head 导致多 head 冲突。

**解决**：检查 `flask db heads` 找到当前 head（`fce013ca180e`），更新 `down_revision`。

### 7.6 Docker 构建 OOM

**问题**：Next.js 16 Turbopack 在 Docker 内编译时被 OOM kill（需要 > 7GB 内存）。

**解决**：采用宿主机本地预构建方案，使用 `Dockerfile.prebuilt` 打包预编译产物。

### 7.7 Nginx 502 Bad Gateway（重启后）

**问题**：单独重建 API 容器后，nginx 缓存了旧的上游 IP 地址。

**解决**：重建 API 容器后执行 `docker compose restart nginx`。

### 7.8 应用列表未执行权限过滤

**问题**：在权限管理中心设置了某成员无法访问某应用，但该成员仍能看到该应用。

**原因**：`AppService.get_paginate_apps()` 没有任何权限过滤逻辑（知识库的 `DatasetService.get_datasets()` 已有此逻辑）。

**解决**：在 `get_paginate_apps()` 中加入基于 `App.permission` + `AppPermission` 表的过滤，对非 Owner/Admin 用户按权限模式过滤可见应用。

---

## 8. 验证测试

### 8.1 功能验证清单

- [x] 权限管理 Tab 在账户设置中显示（仅 Owner/Admin 可见）
- [x] 成员列表正确显示，包含资源访问计数
- [x] 点击成员显示知识库/应用权限详情
- [x] 权限模式下拉框可切换（仅创建者/全体成员/部分成员）
- [x] 「部分成员」模式下 checkbox 可交互
- [x] 保存权限后数据持久化
- [x] 普通成员登录后看不到未授权的应用
- [x] 知识库权限过滤正常（使用原有 DatasetPermission 机制）
- [x] Docker 全量重启后服务稳定，数据不丢失

### 8.2 稳定性验证

```bash
# 全量停止 + 启动
docker compose down && docker compose up -d

# 验证所有容器运行
docker compose ps

# 验证数据库迁移
docker compose exec api flask db current  # 应显示 a1b2c3d4e5f6 (head)

# 验证数据持久化
docker compose exec db_postgres psql -U postgres -d dify \
  -c "SELECT name, permission FROM apps WHERE status='normal';"
```
