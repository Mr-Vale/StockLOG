from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [("herd", "0001_initial")]

    operations = [
        migrations.RenameField(
            model_name="animal", old_name="estimated_weeks", new_name="age_weeks"
        ),
    ]
