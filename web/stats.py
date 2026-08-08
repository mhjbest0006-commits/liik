WAIT_TIME_LIMIT_SECONDS = 5 * 60   # 5분을 초로 바꾸면 300초다.
WAITING_COUNT_LIMIT = 50           # 50명이다.

from .models import Student, ClassMealOrder


def calculate_own_class_ahead_count(cls, number):
    ahead_count = Student.objects.filter(
        cls=cls,
        number__lt=number,
        has_eaten=False,
        is_absent=False,   # 결석 처리 결석한 학생은 대기줄에 없으므로 뺀다.
    ).count()

    return ahead_count


def detect_line_cut(cls, number):
    skipped_students = Student.objects.filter(
        cls=cls,
        number__lt=number,
        has_eaten=False,
        is_absent=False,
    ).order_by('number')

    skipped_numbers = []
    for s in skipped_students:
        skipped_numbers.append(s.number)

    if len(skipped_numbers) > 0:
        return True, skipped_numbers
    else:
        return False, skipped_numbers


def calculate_other_class_ahead_count(cls, year, month):
    try:
        my_order = ClassMealOrder.objects.get(cls=cls, year=year, month=month)
    except ClassMealOrder.DoesNotExist:
        # 1) 이번 달 배치가 아직 설정되지 않았다면 더하지 않는다.
        return 0

    # 2) 나보다 먼저 먹는(같은 그룹, order_no가 더 작은) 반들을 찾는다.
    earlier_orders = ClassMealOrder.objects.filter(
        year=year,
        month=month,
        group=my_order.group,
        order_no__lt=my_order.order_no,
    )

    # 3) 그 반들에 아직 안 먹고 결석도 아닌 학생 수를 모두 더한다.
    total_count = 0
    for order in earlier_orders:
        count = Student.objects.filter(
            cls=order.cls,
            has_eaten=False,
            is_absent=False,
        ).count()
        total_count = total_count + count

    return total_count


# =====================================================================
# 혼잡한 상황 => 다음반 담임에게 공지 자동 등록
# =====================================================================
def find_next_class_in_queue(cls, year, month):
    try:
        my_order = ClassMealOrder.objects.get(cls=cls, year=year, month=month)
    except ClassMealOrder.DoesNotExist:
        # 1) 이번 달 순서가 아직 없으면 다음 반을 알 수 없다.
        return None

    # 2) 나보다 순서가 뒤인(order_no가 더 큰) 반들 중 가장 가까운 반을 찾는다.
    next_order = ClassMealOrder.objects.filter(
        year=year,
        month=month,
        group=my_order.group,
        order_no__gt=my_order.order_no,
    ).order_by('order_no').first()

    if next_order is None:
        # 3) 내가 이 그룹의 마지막 순서라면 다음 반이 없다.
        return None

    return next_order.cls


def calculate_expected_wait(waiting_count, service_time_per_person):
    x = int(waiting_count)
    if x < 0:
        x = 0                       # 1) 대기인원이 음수면 0으로 바꾼다.

    t = float(service_time_per_person)
    if t < 0:
        t = 0.0                     # 2) 배식시간이 음수면 0으로 바꾼다.

    expected_wait = x * t           # 3) 문자와 식: 예상 대기시간 = x * t
    return expected_wait


def check_congestion(waiting_count, expected_wait_seconds):
    is_time_over = expected_wait_seconds > WAIT_TIME_LIMIT_SECONDS   # 1) 대기시간 부등식
    is_count_over = waiting_count > WAITING_COUNT_LIMIT              # 2) 대기인원 부등식

    if is_time_over or is_count_over:
        return True   # 둘 중 하나라도 참이면 혼잡하다.
    else:
        return False


def calculate_congestion_probability(wait_logs):
    total_count = 0
    congested_count = 0

    for log in wait_logs:              # 1)~2) 기록을 하나씩 확인하면서 개수를 센다.
        total_count = total_count + 1
        if log.is_congested:
            congested_count = congested_count + 1

    if total_count == 0:
        # 아직 데이터가 하나도 없으면 확률을 구할 수 없으니 0으로 돌려준다.
        return {'total_count': 0, 'congested_count': 0, 'probability': 0.0}

    probability = congested_count / total_count   # 3) 확률 = 혼잡 횟수 / 전체 횟수
    probability = round(probability, 4)           

    return {
        'total_count': total_count,
        'congested_count': congested_count,
        'probability': probability,
    }


def calculate_hourly_statistics(wait_logs):
    # 1) 시간대별로 대기인원 값을 모아 담을 빈 사전(딕셔너리)을 만든다.
    hour_to_values = {}
    for log in wait_logs:
        hour = log.scanned_at.hour
        if hour not in hour_to_values:
            hour_to_values[hour] = []
        hour_to_values[hour].append(log.waiting_count)

    hourly_list = []
    hour_list = list(hour_to_values.keys())
    hour_list.sort()   # 시간대를 0시부터 23시 순서로 정렬한다.

    for hour in hour_list:
        values = hour_to_values[hour]
        count = len(values)

        # 2) 평균 구하기 = (다 더한 값) / (자료 개수)
        total_sum = 0
        for v in values:
            total_sum = total_sum + v
        mean_value = round(total_sum / count, 2)

        # 3) 중앙값 구하기 = 크기 순서로 줄 세운 뒤 가운데 값
        sorted_values = sorted(values)
        middle_index = count // 2
        if count % 2 == 1:
            # 자료 개수가 홀수면 가운데 값이 바로 중앙값이다.
            median_value = sorted_values[middle_index]
        else:
            # 자료 개수가 짝수면 가운데 두 값의 평균이 중앙값이다.
            median_value = (sorted_values[middle_index - 1] + sorted_values[middle_index]) / 2

        hourly_list.append({
            'hour': hour,
            'count': count,
            'mean': mean_value,
            'median': median_value,
        })

    # 4) 평균 대기인원이 가장 큰 시간대를 찾는다.
    busiest_hour = None
    busiest_mean = -1
    for item in hourly_list:
        if item['mean'] > busiest_mean:
            busiest_mean = item['mean']
            busiest_hour = item['hour']

    return {'hourly': hourly_list, 'busiest_hour': busiest_hour}


def fit_linear_wait_model(wait_logs):
    # 1) (x, y) 데이터 모으기
    x_list = []
    y_list = []
    for log in wait_logs:
        if log.actual_wait_seconds is not None:
            x_list.append(log.waiting_count)
            y_list.append(log.actual_wait_seconds)

    n = len(x_list)

    if n < 2:
        # 2) 데이터가 너무 적어서 직선을 그릴 수 없는 경우다.
        return {'sample_size': n, 'a': None, 'b': None, 'equation': '데이터가 부족하다 (2건 이상 필요하다)'}

    # 3) x평균, y평균 구하기
    x_sum = 0
    y_sum = 0
    for i in range(n):
        x_sum = x_sum + x_list[i]
        y_sum = y_sum + y_list[i]
    x_mean = x_sum / n
    y_mean = y_sum / n

    # 4) 기울기 a를 구하기 위한 분자와 분모 계산하기
    numerator = 0     # (x 편차) * (y 편차)를 다 더한 값
    denominator = 0   # (x 편차)의 제곱을 다 더한 값
    for i in range(n):
        x_diff = x_list[i] - x_mean
        y_diff = y_list[i] - y_mean
        numerator = numerator + (x_diff * y_diff)
        denominator = denominator + (x_diff * x_diff)

    if denominator == 0:
        # 대기인원이 전부 똑같은 값이면 기울기를 정할 수 없다.
        return {'sample_size': n, 'a': None, 'b': None, 'equation': '대기인원 값이 모두 같아서 계산할 수 없다'}

    a = numerator / denominator     # 4) 기울기 a
    b = y_mean - (a * x_mean)       # 5) y절편 b

    a = round(a, 3)
    b = round(b, 3)

    equation_text = "y = " + str(a) + " * x + " + str(b) + "  (x: 대기인원, y: 실제 대기시간(초))"

    return {
        'sample_size': n,
        'a': a,
        'b': b,
        'equation': equation_text,
    }


def predict_actual_wait(waiting_count, linear_model):
    a = linear_model.get('a')
    b = linear_model.get('b')

    if a is None or b is None:
        return None

    predicted_y = (a * waiting_count) + b
    return round(predicted_y, 1)
