from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("herd", "0001_initial")]
    operations = [
        migrations.AddField(
            model_name="inventory", name="feed_unit",
            field=models.CharField(max_length=12, blank=True, default=""),
        ),
    ]
