# Step 1: Add public_uuid field as nullable (no unique constraint yet)
from django.db import migrations, models
import uuid


class Migration(migrations.Migration):

    dependencies = [
        ('register', '0009_rename_a_users_user_img'),  # 실제 이전 마이그레이션
    ]

    operations = [
        migrations.AddField(
            model_name='users',
            name='public_uuid',
            field=models.UUIDField(null=True, blank=True, db_index=True),
        ),
    ]
