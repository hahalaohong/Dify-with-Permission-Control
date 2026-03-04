from flask import request
from flask_restx import Resource
from pydantic import BaseModel, Field

from controllers.console import console_ns
from controllers.console.wraps import (
    account_initialization_required,
    is_admin_or_owner_required,
    setup_required,
)
from extensions.ext_database import db
from libs.login import current_account_with_tenant, login_required
from models.account import Account, TenantAccountJoin
from models.dataset import AppPermissionEnum, Dataset, DatasetPermissionEnum
from models.model import App
from services.account_service import TenantService
from services.app_permission_service import AppPermissionService


DEFAULT_REF_TEMPLATE_SWAGGER_2_0 = "#/definitions/{model}"


class MemberPermissionUpdatePayload(BaseModel):
    dataset_ids: list[str] = Field(default_factory=list)
    app_ids: list[str] = Field(default_factory=list)


class ResourcePermissionModePayload(BaseModel):
    permission: str = Field(description="Permission mode: only_me, all_team_members, partial_members")


def reg(cls: type[BaseModel]):
    console_ns.schema_model(cls.__name__, cls.model_json_schema(ref_template=DEFAULT_REF_TEMPLATE_SWAGGER_2_0))


reg(MemberPermissionUpdatePayload)
reg(ResourcePermissionModePayload)


@console_ns.route("/workspaces/current/permissions")
class PermissionOverviewApi(Resource):
    """Get permission overview for all members."""

    @setup_required
    @login_required
    @account_initialization_required
    @is_admin_or_owner_required
    def get(self):
        current_user, current_tenant_id = current_account_with_tenant()
        if not current_user.current_tenant:
            raise ValueError("No current tenant")

        # 获取所有成员
        members = TenantService.get_tenant_members(current_user.current_tenant)

        # 获取所有知识库和应用
        datasets = db.session.query(Dataset).filter(
            Dataset.tenant_id == current_tenant_id
        ).all()

        apps = db.session.query(App).filter(
            App.tenant_id == current_tenant_id,
            App.status == "normal",
        ).all()

        # 构建成员权限摘要
        member_list = []
        for member in members:
            # 获取该成员的权限摘要
            permission_summary = AppPermissionService.get_user_permission_summary(
                str(current_tenant_id), str(member.id)
            )

            # 计算可访问的知识库数量
            dataset_count = 0
            for dataset in datasets:
                if _can_user_access_dataset(member, dataset, permission_summary["dataset_ids"]):
                    dataset_count += 1

            # 计算可访问的应用数量
            app_count = 0
            for app in apps:
                if _can_user_access_app(member, app, permission_summary["app_ids"]):
                    app_count += 1

            member_list.append({
                "id": str(member.id),
                "name": member.name,
                "email": member.email,
                "avatar": member.avatar,
                "role": member.role,
                "dataset_count": dataset_count,
                "app_count": app_count,
            })

        return {
            "members": member_list,
            "total_datasets": len(datasets),
            "total_apps": len(apps),
        }, 200


@console_ns.route("/workspaces/current/permissions/members/<string:member_id>")
class MemberPermissionApi(Resource):
    """Get or update permission for a specific member."""

    @setup_required
    @login_required
    @account_initialization_required
    @is_admin_or_owner_required
    def get(self, member_id: str):
        """Get permission details for a specific member."""
        current_user, current_tenant_id = current_account_with_tenant()
        if not current_user.current_tenant:
            raise ValueError("No current tenant")

        # 验证成员存在并加载角色
        result = (
            db.session.query(Account, TenantAccountJoin.role)
            .join(TenantAccountJoin, Account.id == TenantAccountJoin.account_id)
            .filter(Account.id == member_id, TenantAccountJoin.tenant_id == current_tenant_id)
            .first()
        )
        if not result:
            return {"error": "Member not found"}, 404
        member, role = result
        member.role = role

        # 获取所有知识库和应用
        datasets = db.session.query(Dataset).filter(
            Dataset.tenant_id == current_tenant_id
        ).all()

        apps = db.session.query(App).filter(
            App.tenant_id == current_tenant_id,
            App.status == "normal",
        ).all()

        # 获取该成员的权限
        permission_summary = AppPermissionService.get_user_permission_summary(
            str(current_tenant_id), member_id
        )

        # 构建知识库列表（包含权限状态）
        dataset_list = []
        for dataset in datasets:
            has_access = _can_user_access_dataset(member, dataset, permission_summary["dataset_ids"])
            dataset_list.append({
                "id": str(dataset.id),
                "name": dataset.name,
                "permission": dataset.permission or DatasetPermissionEnum.ONLY_ME,
                "created_by": str(dataset.created_by) if dataset.created_by else None,
                "has_access": has_access,
                "is_partial": dataset.permission == DatasetPermissionEnum.PARTIAL_TEAM,
            })

        # 构建应用列表（包含权限状态）
        app_list = []
        for app in apps:
            has_access = _can_user_access_app(member, app, permission_summary["app_ids"])
            app_list.append({
                "id": str(app.id),
                "name": app.name,
                "permission": app.permission or AppPermissionEnum.ALL_TEAM,
                "created_by": str(app.created_by) if app.created_by else None,
                "has_access": has_access,
                "is_partial": app.permission == AppPermissionEnum.PARTIAL_TEAM,
            })

        return {
            "member": {
                "id": str(member.id),
                "name": member.name,
                "email": member.email,
                "avatar": member.avatar,
            },
            "datasets": dataset_list,
            "apps": app_list,
            "accessible_dataset_ids": permission_summary["dataset_ids"],
            "accessible_app_ids": permission_summary["app_ids"],
        }, 200

    @setup_required
    @login_required
    @account_initialization_required
    @is_admin_or_owner_required
    @console_ns.expect(console_ns.models[MemberPermissionUpdatePayload.__name__])
    def put(self, member_id: str):
        """Update permission for a specific member."""
        current_user, current_tenant_id = current_account_with_tenant()
        if not current_user.current_tenant:
            raise ValueError("No current tenant")

        # 验证成员存在并加载角色
        result = (
            db.session.query(Account, TenantAccountJoin.role)
            .join(TenantAccountJoin, Account.id == TenantAccountJoin.account_id)
            .filter(Account.id == member_id, TenantAccountJoin.tenant_id == current_tenant_id)
            .first()
        )
        if not result:
            return {"error": "Member not found"}, 404
        member, role = result
        member.role = role

        # Owner 不能被限制权限
        if member.role == "owner":
            return {"error": "Cannot modify owner's permissions"}, 400

        # 解析请求体
        payload = MemberPermissionUpdatePayload.model_validate(request.json)

        # 更新权限
        AppPermissionService.update_user_permissions(
            tenant_id=str(current_tenant_id),
            user_id=member_id,
            dataset_ids=payload.dataset_ids,
            app_ids=payload.app_ids,
        )

        return {"message": "Permissions updated successfully"}, 200


@console_ns.route("/workspaces/current/permissions/resources")
class PermissionResourcesApi(Resource):
    """Get all resources (datasets and apps) for permission management."""

    @setup_required
    @login_required
    @account_initialization_required
    @is_admin_or_owner_required
    def get(self):
        """Get all datasets and apps."""
        current_user, current_tenant_id = current_account_with_tenant()
        if not current_user.current_tenant:
            raise ValueError("No current tenant")

        # 获取所有知识库
        datasets = db.session.query(Dataset).filter(
            Dataset.tenant_id == current_tenant_id
        ).all()

        # 获取所有应用
        apps = db.session.query(App).filter(
            App.tenant_id == current_tenant_id,
            App.status == "normal",
        ).all()

        dataset_list = [
            {
                "id": str(dataset.id),
                "name": dataset.name,
                "permission": dataset.permission or DatasetPermissionEnum.ONLY_ME,
            }
            for dataset in datasets
        ]

        app_list = [
            {
                "id": str(app.id),
                "name": app.name,
                "permission": app.permission or AppPermissionEnum.ALL_TEAM,
            }
            for app in apps
        ]

        return {
            "datasets": dataset_list,
            "apps": app_list,
        }, 200


VALID_PERMISSION_MODES = {"only_me", "all_team_members", "partial_members"}


@console_ns.route("/workspaces/current/permissions/resources/<string:resource_type>/<string:resource_id>")
class ResourcePermissionModeApi(Resource):
    """Update permission mode for a specific resource (dataset or app)."""

    @setup_required
    @login_required
    @account_initialization_required
    @is_admin_or_owner_required
    @console_ns.expect(console_ns.models[ResourcePermissionModePayload.__name__])
    def put(self, resource_type: str, resource_id: str):
        """Update permission mode for a dataset or app."""
        current_user, current_tenant_id = current_account_with_tenant()
        if not current_user.current_tenant:
            raise ValueError("No current tenant")

        payload = ResourcePermissionModePayload.model_validate(request.json)
        if payload.permission not in VALID_PERMISSION_MODES:
            return {"error": f"Invalid permission mode: {payload.permission}"}, 400

        try:
            if resource_type == "dataset":
                dataset = db.session.query(Dataset).filter(
                    Dataset.id == resource_id,
                    Dataset.tenant_id == current_tenant_id,
                ).first()
                if not dataset:
                    return {"error": "Dataset not found"}, 404
                dataset.permission = payload.permission
                db.session.commit()
            elif resource_type == "app":
                app = db.session.query(App).filter(
                    App.id == resource_id,
                    App.tenant_id == current_tenant_id,
                ).first()
                if not app:
                    return {"error": "App not found"}, 404
                app.permission = payload.permission
                db.session.commit()
            else:
                return {"error": "Invalid resource type, must be 'dataset' or 'app'"}, 400
        except Exception as e:
            db.session.rollback()
            raise e

        return {"message": "Permission mode updated successfully"}, 200


def _can_user_access_dataset(member: Account, dataset: Dataset, accessible_dataset_ids: list[str]) -> bool:
    """检查用户是否可以访问知识库"""
    # Owner/Admin 可以访问所有
    if member.role in ["owner", "admin"]:
        return True

    permission = dataset.permission or DatasetPermissionEnum.ONLY_ME

    if permission == DatasetPermissionEnum.ONLY_ME:
        return str(dataset.created_by) == str(member.id)
    elif permission == DatasetPermissionEnum.ALL_TEAM:
        return True
    elif permission == DatasetPermissionEnum.PARTIAL_TEAM:
        if str(dataset.created_by) == str(member.id):
            return True
        return str(dataset.id) in accessible_dataset_ids

    return False


def _can_user_access_app(member: Account, app: App, accessible_app_ids: list[str]) -> bool:
    """检查用户是否可以访问应用"""
    # Owner/Admin 可以访问所有
    if member.role in ["owner", "admin"]:
        return True

    permission = app.permission or AppPermissionEnum.ALL_TEAM

    if permission == AppPermissionEnum.ONLY_ME:
        return str(app.created_by) == str(member.id)
    elif permission == AppPermissionEnum.ALL_TEAM:
        return True
    elif permission == AppPermissionEnum.PARTIAL_TEAM:
        if str(app.created_by) == str(member.id):
            return True
        return str(app.id) in accessible_app_ids

    return False
