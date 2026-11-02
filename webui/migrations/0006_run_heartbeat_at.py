# Generated for MLE-1 worker-liveness supervision.
import django.utils.timezone
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("webui", "0005_merge_20261102"),
    ]

    operations = [
        migrations.AddField(
            model_name="run",
            name="heartbeat_at",
            field=models.DateTimeField(default=django.utils.timezone.now),
        ),
    ]
