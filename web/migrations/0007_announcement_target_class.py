# 1) 혼잡한 상황 => 다음반 담임에게 공지 자동 등록
# 2) Announcement.is_auto: 사람이 직접 쓴 공지인지, 혼잡 상황을 감지한 시스템이 자동으로 만든 공지인지 구분한다.

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('web', '0006_congestion_number_order'),
    ]

    operations = [
        migrations.AddField(
            model_name='announcement',
            name='target_class',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name='announcements',
                to='web.class',
            ),
        ),
        migrations.AddField(
            model_name='announcement',
            name='is_auto',
            field=models.BooleanField(default=False),
        ),
    ]
