# Migration rewritten: character app removed from project.
# Original migration added BookSnap.story FK to character.Story.
# This version records that state without the character dependency.

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('book', '0003_booksnap_story_link'),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            database_operations=[],
            state_operations=[
                migrations.AddField(
                    model_name='booksnap',
                    name='story',
                    field=models.IntegerField(null=True, blank=True),
                ),
            ],
        ),
    ]
