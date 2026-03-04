from sqlalchemy import select

from extensions.ext_database import db
from models.dataset import AppPermission, AppPermissionEnum
from models.model import App


class AppPermissionService:
    @classmethod
    def get_app_partial_member_list(cls, app_id: str) -> list[str]:
        """获取应用的部分成员列表"""
        user_list_query = db.session.scalars(
            select(AppPermission.account_id).where(AppPermission.app_id == app_id)
        ).all()
        return list(user_list_query)

    @classmethod
    def update_partial_member_list(cls, tenant_id: str, app_id: str, user_list: list[dict]):
        """更新应用的部分成员列表"""
        try:
            db.session.query(AppPermission).where(AppPermission.app_id == app_id).delete()
            permissions = []
            for user in user_list:
                permission = AppPermission(
                    tenant_id=tenant_id,
                    app_id=app_id,
                    account_id=user["user_id"],
                )
                permissions.append(permission)

            db.session.add_all(permissions)
            db.session.commit()
        except Exception as e:
            db.session.rollback()
            raise e

    @classmethod
    def clear_partial_member_list(cls, app_id: str):
        """清空应用的部分成员列表"""
        try:
            db.session.query(AppPermission).where(AppPermission.app_id == app_id).delete()
            db.session.commit()
        except Exception as e:
            db.session.rollback()
            raise e

    @classmethod
    def check_app_permission(cls, user, app: App) -> bool:
        """检查用户是否有权访问应用"""
        # Owner 角色可以访问所有应用
        if user.is_admin_or_owner:
            return True

        # 检查应用的权限设置
        permission = app.permission or AppPermissionEnum.ALL_TEAM

        if permission == AppPermissionEnum.ONLY_ME:
            return str(app.created_by) == str(user.id)
        elif permission == AppPermissionEnum.ALL_TEAM:
            return True
        elif permission == AppPermissionEnum.PARTIAL_TEAM:
            # 创建者始终有权限
            if str(app.created_by) == str(user.id):
                return True
            # 检查是否在部分成员列表中
            member_list = cls.get_app_partial_member_list(str(app.id))
            return str(user.id) in member_list

        return False

    @classmethod
    def get_user_accessible_app_ids(cls, tenant_id: str, user_id: str) -> list[str]:
        """获取用户可访问的所有应用ID（用于 PARTIAL_TEAM 模式）"""
        app_ids = db.session.scalars(
            select(AppPermission.app_id).where(
                AppPermission.tenant_id == tenant_id,
                AppPermission.account_id == user_id,
            )
        ).all()
        return list(app_ids)

    @classmethod
    def get_user_permission_summary(cls, tenant_id: str, user_id: str) -> dict:
        """获取用户的权限摘要（用于权限管理中心）"""
        from models.dataset import Dataset, DatasetPermission, DatasetPermissionEnum

        # 获取用户可访问的知识库
        dataset_ids = db.session.scalars(
            select(DatasetPermission.dataset_id).where(
                DatasetPermission.tenant_id == tenant_id,
                DatasetPermission.account_id == user_id,
            )
        ).all()

        # 获取用户可访问的应用
        app_ids = cls.get_user_accessible_app_ids(tenant_id, user_id)

        return {
            "dataset_ids": list(dataset_ids),
            "app_ids": list(app_ids),
        }

    @classmethod
    def update_user_permissions(
        cls,
        tenant_id: str,
        user_id: str,
        dataset_ids: list[str],
        app_ids: list[str],
    ):
        """更新用户的权限（用于权限管理中心）"""
        from models.dataset import Dataset, DatasetPermission, DatasetPermissionEnum

        try:
            # 更新知识库权限
            # 1. 删除用户现有的知识库权限
            db.session.query(DatasetPermission).where(
                DatasetPermission.tenant_id == tenant_id,
                DatasetPermission.account_id == user_id,
            ).delete()

            # 2. 添加新的知识库权限
            for dataset_id in dataset_ids:
                # 只有 PARTIAL_TEAM 模式的知识库才需要添加权限记录
                dataset = db.session.query(Dataset).filter(
                    Dataset.id == dataset_id,
                    Dataset.tenant_id == tenant_id,
                ).first()
                if dataset and dataset.permission == DatasetPermissionEnum.PARTIAL_TEAM:
                    permission = DatasetPermission(
                        tenant_id=tenant_id,
                        dataset_id=dataset_id,
                        account_id=user_id,
                    )
                    db.session.add(permission)

            # 更新应用权限
            # 1. 删除用户现有的应用权限
            db.session.query(AppPermission).where(
                AppPermission.tenant_id == tenant_id,
                AppPermission.account_id == user_id,
            ).delete()

            # 2. 添加新的应用权限
            for app_id in app_ids:
                # 只有 PARTIAL_TEAM 模式的应用才需要添加权限记录
                app = db.session.query(App).filter(
                    App.id == app_id,
                    App.tenant_id == tenant_id,
                ).first()
                if app and app.permission == AppPermissionEnum.PARTIAL_TEAM:
                    permission = AppPermission(
                        tenant_id=tenant_id,
                        app_id=app_id,
                        account_id=user_id,
                    )
                    db.session.add(permission)

            db.session.commit()
        except Exception as e:
            db.session.rollback()
            raise e
