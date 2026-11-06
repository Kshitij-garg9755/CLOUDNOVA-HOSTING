"""Track GitHub revocation without deleting imported project history."""
from alembic import op
import sqlalchemy as sa

revision="0002_github_installation_status"
down_revision="0001_initial"
branch_labels=None
depends_on=None

def upgrade():
    inspector=sa.inspect(op.get_bind())
    installation_columns={c["name"] for c in inspector.get_columns("github_installations")}
    repository_columns={c["name"] for c in inspector.get_columns("github_repositories")}
    if "status" not in installation_columns:
        op.add_column("github_installations",sa.Column("status",sa.String(length=24),nullable=False,server_default="active"))
    if "accessible" not in repository_columns:
        op.add_column("github_repositories",sa.Column("accessible",sa.Boolean(),nullable=False,server_default=sa.true()))

def downgrade():
    inspector=sa.inspect(op.get_bind())
    if "accessible" in {c["name"] for c in inspector.get_columns("github_repositories")}:
        op.drop_column("github_repositories","accessible")
    if "status" in {c["name"] for c in inspector.get_columns("github_installations")}:
        op.drop_column("github_installations","status")
