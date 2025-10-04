"""Create initial schema manually

Revision ID: ffaf7e5c74e4
Revises: 
Create Date: 2025-10-04 10:42:56.917457

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'ffaf7e5c74e4'
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


from devildex.database.models import Base

def upgrade() -> None:
    """Upgrade schema."""
    Base.metadata.create_all(op.get_bind())


def downgrade() -> None:
    """Downgrade schema."""
    Base.metadata.drop_all(op.get_bind())

