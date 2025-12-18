# Generated manually

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('book', '0007_alter_books_description'),
    ]

    operations = [
        # 1. 먼저 기존 ForeignKey 제거
        migrations.RemoveField(
            model_name='books',
            name='genres',
        ),
        # 2. ManyToMany 필드 추가
        migrations.AddField(
            model_name='books',
            name='genres',
            field=models.ManyToManyField(blank=True, related_name='books', to='book.genres'),
        ),
    ]
