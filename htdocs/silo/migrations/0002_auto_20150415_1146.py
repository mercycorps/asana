# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('silo', '0001_initial'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='valuestore',
            name='text_store',
        ),
        migrations.AlterField(
            model_name='valuestore',
            name='char_store',
            field=models.CharField(max_length=3000, null=True, blank=True),
            preserve_default=True,
        ),
    ]