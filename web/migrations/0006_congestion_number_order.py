#   1) Student.is_absent : 결석 체크 필드 추가
#   2) ClassMealOrde : 월별 홀수반/짝수반 배식 순서 저장
#   3) WaitLog.own_class_ahead_count : 같은 반 안에서 내 앞 번호 대기인원
#      WaitLog.other_class_ahead_count : 나보다 먼저 먹는 반들의 대기인원 합
#      WaitLog.is_line_cut : 새치기 여부
#      WaitLog.skipped_student_numbers : 새치기당한 학생 번호 목록

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('web', '0005_student_user'),
    ]

    operations = [
        migrations.AddField(
            model_name='student',
            name='is_absent',
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name='waitlog',
            name='own_class_ahead_count',
            field=models.IntegerField(default=0),
        ),
        migrations.AddField(
            model_name='waitlog',
            name='other_class_ahead_count',
            field=models.IntegerField(default=0),
        ),
        migrations.AddField(
            model_name='waitlog',
            name='scanned_student_number',
            field=models.IntegerField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='waitlog',
            name='is_line_cut',
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name='waitlog',
            name='skipped_student_numbers',
            field=models.CharField(blank=True, default='', max_length=200),
        ),
        migrations.CreateModel(
            name='ClassMealOrder',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('year', models.IntegerField()),
                ('month', models.IntegerField()),
                ('group', models.CharField(choices=[('odd', '홀수반'), ('even', '짝수반')], max_length=10)),
                ('order_no', models.IntegerField()),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('cls', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='meal_orders', to='web.class')),
            ],
            options={
                'ordering': ['year', 'month', 'group', 'order_no'],
            },
        ),
        migrations.AlterUniqueTogether(
            name='classmealorder',
            unique_together={('cls', 'year', 'month')},
        ),
    ]
