"""add export_logs table

Revision ID: 83ccb5a729a3
Revises: a71ba3c6d0a4
Create Date: 2025-08-20 12:00:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "83ccb5a729a3"
down_revision: Union[str, None] = "a71ba3c6d0a4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create export_logs table
    op.create_table(
        "export_logs",
        sa.Column("id", sa.Text(), nullable=False),
        sa.Column("user_id", sa.Text(), nullable=True),
        sa.Column("email_domain", sa.Text(), nullable=True),
        sa.Column("export_timestamp", sa.BigInteger(), nullable=True),
        sa.Column("file_size", sa.BigInteger(), nullable=True),
        sa.Column("row_count", sa.Integer(), nullable=True),
        sa.Column("date_range_start", sa.BigInteger(), nullable=True),
        sa.Column("date_range_end", sa.BigInteger(), nullable=True),
        sa.Column("created_at", sa.BigInteger(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade() -> None:
    # Drop export_logs table
    op.drop_table("export_logs")
