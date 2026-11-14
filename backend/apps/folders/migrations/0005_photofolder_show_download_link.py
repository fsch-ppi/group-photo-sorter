from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("folders", "0004_add_date_day_only_format"),
    ]

    operations = [
        migrations.AddField(
            model_name="photofolder",
            name="show_download_link",
            field=models.BooleanField(
                default=True,
                help_text="Whether to share the Nextcloud download link with uploaders",
            ),
        ),
    ]

