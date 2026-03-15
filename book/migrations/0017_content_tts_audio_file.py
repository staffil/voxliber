from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('book', '0016_books_block_draft'),
    ]

    operations = [
        migrations.AddField(
            model_name='content',
            name='tts_audio_file',
            field=models.FileField(
                blank=True,
                help_text='믹싱 전 원본 TTS 오디오 (re-mix 시 base)',
                max_length=1000,
                null=True,
                upload_to='uploads/audio/tts_original/',
            ),
        ),
    ]
