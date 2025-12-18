# Generated manually

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('book', '0008_alter_books_genres'),
    ]

    operations = [
        # 1. Content에 book 필드 추가 (nullable로)
        migrations.AddField(
            model_name='content',
            name='book',
            field=models.ForeignKey(null=True, blank=True, on_delete=django.db.models.deletion.CASCADE, related_name='contents', to='book.books'),
        ),

        # 2. Content에 text 필드 추가
        migrations.AddField(
            model_name='content',
            name='text',
            field=models.TextField(blank=True, null=True),
        ),

        # 3. 기존 Content의 book 필드를 chapter의 book으로 채우기
        migrations.RunSQL(
            sql='UPDATE content SET book_id = (SELECT book_id FROM chapter WHERE chapter.id = content.chapter_id)',
            reverse_sql=migrations.RunSQL.noop,
        ),

        # 4. Content의 book 필드를 NOT NULL로 변경
        migrations.AlterField(
            model_name='content',
            name='book',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='contents', to='book.books'),
        ),

        # 5. Content의 chapter 필드 제거
        migrations.RemoveField(
            model_name='content',
            name='chapter',
        ),

        # 6. Chapter 모델 삭제
        migrations.DeleteModel(
            name='Chapter',
        ),
    ]
