# Generated by Django 4.2.11 on 2025-02-09 12:32

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('allotmentapp', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='courseallotment',
            name='paper_no',
            field=models.PositiveIntegerField(default=1),
        ),
    ]
