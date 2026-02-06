# Step 2: Populate UUID for all existing users
from django.db import migrations
import uuid


def gen_uuid(apps, schema_editor):
    Users = apps.get_model('register', 'Users')
    for user in Users.objects.filter(public_uuid__isnull=True):
        user.public_uuid = uuid.uuid4()
        user.save(update_fields=['public_uuid'])


def reverse_code(apps, schema_editor):
    # Reverse migration: set all to null
    Users = apps.get_model('register', 'Users')
    Users.objects.all().update(public_uuid=None)


class Migration(migrations.Migration):

    dependencies = [
        ('register', '0010_users_public_uuid_nullable'),
    ]

    operations = [
        migrations.RunPython(gen_uuid, reverse_code),
    ]
