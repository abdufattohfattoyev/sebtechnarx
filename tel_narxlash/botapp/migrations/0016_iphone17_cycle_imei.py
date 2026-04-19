from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('botapp', '0015_alter_replacedpart_part_type'),
    ]

    operations = [
        migrations.AddField(
            model_name='iphonemodel',
            name='uses_cycle_count',
            field=models.BooleanField(
                default=False,
                help_text="iPhone 17+ uchun. 100% batareyada sikl soni so'raladi.",
                verbose_name='Sikl soni ishlatadi'
            ),
        ),
        migrations.AddField(
            model_name='iphonemodel',
            name='dual_imei_price_difference',
            field=models.DecimalField(
                decimal_places=2,
                default=0,
                max_digits=15,
                help_text='2 IMEI modelga nisbatan 1 IMEI qancha arzon (masalan: -30)',
                verbose_name='2 IMEI farqi ($)'
            ),
        ),
        migrations.AddField(
            model_name='batteryrange',
            name='is_cycle_range',
            field=models.BooleanField(
                default=False,
                help_text="Foiz o'rniga sikl soni bo'lsa belgilang (masalan: 0-100 sikl)",
                verbose_name="Sikl oralig'i"
            ),
        ),
        migrations.AlterField(
            model_name='batteryrange',
            name='min_percent',
            field=models.PositiveIntegerField(blank=True, null=True, verbose_name='Minimal foiz'),
        ),
        migrations.AlterField(
            model_name='batteryrange',
            name='max_percent',
            field=models.PositiveIntegerField(blank=True, null=True, verbose_name='Maksimal foiz'),
        ),
    ]
