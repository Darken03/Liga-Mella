# Generated to switch news video from Facebook to YouTube

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0004_noticia_video_facebook'),
    ]

    operations = [
        migrations.RenameField(
            model_name='noticia',
            old_name='video_facebook',
            new_name='video_youtube',
        ),
        migrations.AlterField(
            model_name='noticia',
            name='video_youtube',
            field=models.URLField(blank=True, default='', max_length=500, verbose_name='Video de YouTube (URL)'),
        ),
    ]
