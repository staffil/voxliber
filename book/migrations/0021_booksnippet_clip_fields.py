from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('book', '0020_ttsusagelog_ttsalert_bookauthor'),
    ]

    operations = [
        migrations.AddField(
            model_name='booksnippet',
            name='content',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='snippets', to='book.content'),
        ),
        migrations.AddField(
            model_name='booksnippet',
            name='start_time',
            field=models.FloatField(blank=True, help_text='클립 시작(초)', null=True),
        ),
        migrations.AddField(
            model_name='booksnippet',
            name='end_time',
            field=models.FloatField(blank=True, help_text='클립 종료(초)', null=True),
        ),
    ]
