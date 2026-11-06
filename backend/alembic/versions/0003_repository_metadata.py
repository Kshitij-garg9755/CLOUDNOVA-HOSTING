"""Store GitHub repository owner and description metadata."""
from alembic import op
import sqlalchemy as sa

revision = "0003_repository_metadata"
down_revision = "0002_github_installation_status"
branch_labels = None
depends_on = None

def upgrade():
    inspector = sa.inspect(op.get_bind())
    columns = {column["name"] for column in inspector.get_columns("github_repositories")}
    if "owner" not in columns:
        op.add_column("github_repositories", sa.Column("owner", sa.String(length=120), nullable=True))
    if "description" not in columns:
        op.add_column("github_repositories", sa.Column("description", sa.Text(), nullable=True))

def downgrade():
    inspector = sa.inspect(op.get_bind())
    columns = {column["name"] for column in inspector.get_columns("github_repositories")}
    if "description" in columns:
        op.drop_column("github_repositories", "description")
    if "owner" in columns:
        op.drop_column("github_repositories", "owner")
