# Step 3: Make public_uuid unique and set default
from django.db import migrations, models
import uuid


class Migration(migrations.Migration):

    dependencies = [
        ('register', '0011_populate_users_public_uuid'),
    ]

    operations = [
        migrations.AlterField(
            model_name='users',
            name='public_uuid',
            field=models.UUIDField(
                default=uuid.uuid4,
                editable=False,
                unique=True,
                db_index=True,
                null=True,  # 모델과 일치
            ),
        ),
    ]
