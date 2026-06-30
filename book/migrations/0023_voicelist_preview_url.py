from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('book', '0022_booksnippet_user'),
    ]

    operations = [
        migrations.AddField(
            model_name='voicelist',
            name='preview_url',
            field=models.URLField(blank=True, max_length=500, null=True),
        ),
    ]
