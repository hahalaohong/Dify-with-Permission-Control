"""add app_permissions table and apps.permission field

Revision ID: a1b2c3d4e5f6
Revises: fce013ca180e
Create Date: 2026-02-12 16:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

import models.types


# revision identifiers, used by Alembic.
revision = 'a1b2c3d4e5f6'
down_revision = 'fce013ca180e'
branch_labels = None
depends_on = None


def upgrade():
    # Create app_permissions table
    op.create_table(
        'app_permissions',
        sa.Column('id', models.types.StringUUID(), nullable=False),
        sa.Column('app_id', models.types.StringUUID(), nullable=False),
        sa.Column('account_id', models.types.StringUUID(), nullable=False),
        sa.Column('tenant_id', models.types.StringUUID(), nullable=False),
        sa.Column('has_permission', sa.Boolean(), nullable=False, server_default=sa.text('true')),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.PrimaryKeyConstraint('id', name='app_permission_pkey')
    )
    
    # Create indexes for app_permissions
    with op.batch_alter_table('app_permissions', schema=None) as batch_op:
        batch_op.create_index('idx_app_permissions_app_id', ['app_id'], unique=False)
        batch_op.create_index('idx_app_permissions_account_id', ['account_id'], unique=False)
        batch_op.create_index('idx_app_permissions_tenant_id', ['tenant_id'], unique=False)
    
    # Add permission column to apps table
    op.add_column('apps', sa.Column('permission', sa.String(length=255), nullable=True, server_default=sa.text("'all_team_members'")))


def downgrade():
    # Remove permission column from apps table
    op.drop_column('apps', 'permission')
    
    # Drop indexes
    with op.batch_alter_table('app_permissions', schema=None) as batch_op:
        batch_op.drop_index('idx_app_permissions_tenant_id')
        batch_op.drop_index('idx_app_permissions_account_id')
        batch_op.drop_index('idx_app_permissions_app_id')
    
    # Drop app_permissions table
    op.drop_table('app_permissions')
