# Student 모델에 user(로그인 계정 연결) 필드를 추가함.
# 학생 회원가입 시 학생증(반/번호/바코드) 정보로 본인 확인을 하고, 확인이 끝나면 이 필드로 로그인 계정과 학생 기록을 서로 연결해 둔다.

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('web', '0004_announcement'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AddField(
            model_name='student',
            name='user',
            field=models.OneToOneField(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='student_profile',
                to=settings.AUTH_USER_MODEL,
            ),
        ),
    ]
