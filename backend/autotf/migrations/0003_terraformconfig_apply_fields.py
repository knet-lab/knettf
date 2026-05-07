from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('autotf', '0002_terraformtool_cmd_fields'),
    ]

    operations = [
        migrations.AddField(
            model_name='terraformconfig',
            name='last_apply_at',
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='terraformconfig',
            name='last_apply_status',
            field=models.CharField(
                blank=True, null=True, max_length=10,
                choices=[('success', 'Success'), ('failed', 'Failed')],
            ),
        ),
        migrations.AddField(
            model_name='terraformconfig',
            name='last_apply_output',
            field=models.TextField(blank=True, default=''),
        ),
    ]
