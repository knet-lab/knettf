from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('autotf', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='terraformtool',
            name='cmd',
            field=models.CharField(default='', max_length=500),
        ),
        migrations.AddField(
            model_name='terraformtool',
            name='init_cmd',
            field=models.CharField(blank=True, default='', max_length=500),
        ),
        migrations.AddField(
            model_name='terraformtool',
            name='output_format',
            field=models.CharField(
                choices=[('json', 'JSON'), ('sarif', 'SARIF'), ('kubesec', 'Kubesec')],
                default='json',
                max_length=10,
            ),
        ),
        migrations.AddField(
            model_name='terraformtool',
            name='items_path',
            field=models.CharField(blank=True, default='', max_length=255),
        ),
        migrations.AddField(
            model_name='terraformtool',
            name='severity_field',
            field=models.CharField(blank=True, default='', max_length=100),
        ),
        migrations.AddField(
            model_name='terraformtool',
            name='severity_map',
            field=models.JSONField(blank=True, default=dict),
        ),
        migrations.AddField(
            model_name='terraformtool',
            name='rule_id_field',
            field=models.CharField(blank=True, default='', max_length=100),
        ),
        migrations.AddField(
            model_name='terraformtool',
            name='description_field',
            field=models.CharField(blank=True, default='', max_length=100),
        ),
        migrations.AddField(
            model_name='terraformtool',
            name='location_file_field',
            field=models.CharField(blank=True, default='', max_length=100),
        ),
        migrations.AddField(
            model_name='terraformtool',
            name='location_line_field',
            field=models.CharField(blank=True, default='', max_length=100),
        ),
    ]
