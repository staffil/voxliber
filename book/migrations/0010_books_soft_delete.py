from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('book', '0009_genreplaylist_playlistitem'),
    ]

    operations = [
        migrations.AddField(
            model_name='books',
            name='is_deleted',
            field=models.BooleanField(db_index=True, default=False, help_text='소프트 삭제 여부 (데이터는 보존)'),
        ),
        migrations.AddField(
            model_name='books',
            name='deleted_at',
            field=models.DateTimeField(blank=True, null=True),
        ),
    ]
