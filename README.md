# 한백 급식 관리 시스템 (정리 버전)

기존에 올려주신 파일들(`web`/`rest` 앱, `views.py`/`views_backup.py` 등)을 바탕으로
중복 코드와 죽은 코드를 정리하고, 빠진 `settings.py` 등 프로젝트 파일을 새로 구성했습니다.

## 원본 대비 정리한 내용
- `views.py`에 뒤섞여 있던 중복 `logout_view`, 안 쓰는 `home`/`status`/`register_student` 등의 죽은 코드 제거
- `rest` 앱(초기 버전, `Classroom`/`MealRecord` 모델)은 제외하고 완성도 높은 `web` 앱(`Class`/`Student`/`MealStatus`) 기준으로 통일
- **관리자 계정 비밀번호 하드코딩 제거** → 환경변수(`INITIAL_ADMIN_PASSWORD`)로 설정하지 않으면 계정을 자동 생성하지 않도록 변경
- 빠져 있던 `hanbaek/settings.py`, `hanbaek/urls.py`, `wsgi.py`, `asgi.py`를 표준 구성으로 새로 작성
- 없던 템플릿(`login.html`, `index.html`, `regist.html`, `announce.html`)을 최소 동작 버전으로 추가
- `mark_absent` 뷰를 `urls.py`에 연결 (전에는 함수만 있고 라우팅이 없었음)

## 실행 방법

1. 이 폴더를 압축 해제 후, 기존에 쓰시던 `cert.pem`, `key.pem`, `db.sqlite3`를 같은 폴더에 복사해주세요.
   (인증서/DB는 민감한 정보라 이 패키지에는 포함하지 않았습니다.)

2. 가상환경 활성화 후 패키지 설치:
   ```
   pip install -r requirements.txt
   ```

3. 관리자 계정을 새로 만들고 싶다면 서버 실행 전에 환경변수 설정 (PowerShell 예시):
   ```
   $env:INITIAL_ADMIN_USERNAME = "hyun_gun"
   $env:INITIAL_ADMIN_PASSWORD = "원하는_새_비밀번호"
   ```
   (설정 안 하면 자동 계정 생성 없이, 기존 db.sqlite3의 계정을 그대로 사용합니다)

4. 마이그레이션 (모델을 그대로 유지했으니 기존 `db.sqlite3`를 재사용하면 이 단계는 생략 가능):
   ```
   python manage.py migrate
   ```

5. 서버 실행:
   - 일반 HTTP: `python manage.py runserver`
   - HTTPS (인증서 필요): `start.bat` 실행 또는
     ```
     python manage.py runserver_plus 0.0.0.0:8000 --cert-file cert.pem --key-file key.pem
     ```

## 외부 공개 (테스트용)
서버를 켜둔 상태에서 별도 터미널 창에서:
```
ngrok http 8000
```
`ALLOWED_HOSTS`와 `CSRF_TRUSTED_ORIGINS`에 ngrok 도메인을 이미 허용해두었으니 바로 접속 가능합니다.

## 남은 보안 숙제
- `SECRET_KEY`를 실제 배포 전에는 환경변수(`DJANGO_SECRET_KEY`)로 반드시 교체하세요.
- 운영 배포 시 `DJANGO_DEBUG=False`로 설정하세요.
- `@csrf_exempt`가 붙은 API들은 외부에 공개하기 전에 인증/CSRF 처리를 다시 검토하는 것을 권장합니다.

## [보완] 수학 교과 연계 기능 추가
학생증을 찍는 순간(배식 체크) 데이터를 활용해 아래 5가지 수학 교과 내용을 실제로 계산·표시하도록 보완했습니다.
**코드와 주석은 중학생이 읽어도 이해할 수 있도록, 어려운 문법(리스트 컴프리헨션, 람다 등) 없이
for문·if문 같은 기본 문법 위주로 작성했습니다.**
코드 내에서 `# [보완: ...]` / `<!-- [보완: ...] -->` 주석으로 어느 부분이 추가/수정되었는지 표시해 두었습니다.

| 교과 단원 | 구현 위치 | 내용 |
|---|---|---|
| 1) 문자와 식 | `web/stats.py`의 `calculate_expected_wait()`, `views.scan_barcode` | 대기인원 x, 1인당 배식시간 t로 `예상 대기시간 = x * t`를 학생증 스캔 즉시 계산 |
| 2) 확률 | `web/stats.py`의 `calculate_congestion_probability()`, `/api/congestion-probability/` | 과거 `WaitLog` 데이터의 상대도수(혼잡 발생 횟수 ÷ 전체 관찰 횟수)로 혼잡 확률 계산 |
| 3) 통계 | `web/stats.py`의 `calculate_hourly_statistics()`, `/api/time-statistics/` | 시간대(0~23시)별 대기인원의 평균·중앙값·최빈값을 계산해 혼잡 시간대 분석 |
| 4) 일차함수 | `web/stats.py`의 `fit_linear_wait_model()` / `predict_actual_wait()`, `/api/linear-wait-model/` | (대기인원, 실제 대기시간) 데이터를 최소제곱법으로 적합해 `y = a*x + b` 형태의 일차함수 도출 |
| 5) 일차부등식 | `web/stats.py`의 `check_congestion()` (상수 `WAIT_TIME_LIMIT_SECONDS`, `WAITING_COUNT_LIMIT`) | `대기시간 > 5분(300초)` 또는 `대기인원 > 50명`일 때 혼잡 경고 발생 |

### 새로 추가된 것들
- 모델: `web/models.py`의 `WaitLog` — 학생증 태그 1건마다 대기인원/예상·실제 대기시간/혼잡 여부를 기록하는 신규 테이블 (마이그레이션 `web/migrations/0002_waitlog.py`)
- 모듈: `web/stats.py` — 위 5가지 계산 로직을 모아둔 신규 파일
- 뷰: `views.scan_barcode`를 확장해 스캔 응답에 `wait_info`(예상 대기시간·혼잡 여부) 포함, `congestion_probability`/`time_statistics`/`linear_wait_model` 3개 뷰 신규 추가
- URL: `/api/congestion-probability/`, `/api/time-statistics/`, `/api/linear-wait-model/`, `/scan-page/` 신규 라우팅
- 템플릿: `web/templates/web/scan.html` 신규 추가(학생증 스캔 키오스크 화면, 예상 대기시간·혼잡 경고 즉시 표시), `announce.html`에 확률/통계/일차함수 대시보드 추가
- 설정: `hanbaek/settings.py`에 `MEAL_SERVICE_TIME_PER_PERSON`(1인당 배식시간 t, 환경변수로 조정 가능) 추가

### 사용 방법
1. `python manage.py migrate` 로 `WaitLog` 테이블 생성 (기존 DB에 이어서 추가되는 마이그레이션입니다)
2. 로그인 후 `/scan-page/` 에서 바코드를 스캔하면 예상 대기시간과 혼잡 경고가 즉시 표시됩니다.
3. `/announce/` 페이지에서 누적된 데이터를 바탕으로 혼잡 확률, 시간대별 통계, 일차함수 회귀식을 확인할 수 있습니다.
4. 필요시 1인당 배식시간을 조정: `$env:MEAL_SERVICE_TIME_PER_PERSON = "4"` (기본값 3초)

---

## [보완] 상시 사이드바 메뉴 + 관리자/학생 계정 분리

### 1) 상시 표시 사이드바
- `web/templates/web/base.html`을 새로 만들어 모든 화면이 이 레이아웃을 상속받도록 했습니다.
- 왼쪽에 항상 고정된 메뉴(`position: sticky`)가 표시되며, 로그인 여부·계정 종류에 따라 보이는 메뉴가 달라집니다.
- 적용된 화면: `index.html`, `login.html`, `signup.html`, `regist.html`, `scan.html`, `status.html`, `announce.html`, `403.html`

### 2) 관리자 계정 / 학생 계정 분리
- 모델: `web/models.py`의 `UserProfile` — Django의 `User`와 1:1로 연결되어 `role`(`admin` 또는 `student`)을 저장 (마이그레이션 `web/migrations/0003_userprofile.py`). `User`가 새로 만들어질 때마다 자동으로 `role='student'` 기본값을 가진 `UserProfile`이 생성됩니다.
- 회원가입: `/signup/` (신규) — 계정 종류를 "관리자"로 선택하면 `ADMIN_SIGNUP_CODE`(설정값, 환경변수로 조정 가능)를 입력해야 가입됩니다. "학생"은 코드 없이 바로 가입됩니다.
- 권한 검사: `web/decorators.py`의 `admin_required` — 관리자(또는 `createsuperuser`로 만든 최고관리자)가 아니면 페이지 요청은 `403.html`을, API 요청은 JSON 403 응답을 돌려줍니다.
- 접근 범위:

| 화면/기능 | 관리자 | 학생 |
|---|---|---|
| 반/학생 등록 (`/regist/`) | ✅ | ❌ (403) |
| 학생증 스캔 (`/scan-page/`) | ✅ | ❌ (403) |
| 급식 현황 (`/status-page/`, 신규) | ✅ | ❌ (403) |
| 공지 및 혼잡도 분석 (`/announce/`) | ✅ | ✅ |

- 기존에 `createsuperuser`로 만든 계정(예: `hyun_gun`)은 `is_superuser=True`이므로 별도 설정 없이 그대로 관리자 권한을 유지합니다.
- 관리자 가입 코드 변경: `$env:ADMIN_SIGNUP_CODE = "우리학교전용코드"` (기본값 `HANBAEK-ADMIN-2026`이므로 실제 운영 전에 반드시 변경하세요)

### 3) 공지사항 작성 (관리자 전용)
- 모델: `web/models.py`의 `Announcement` — 제목, 내용, 작성자, 작성 시각을 저장 (마이그레이션 `web/migrations/0004_announcement.py`)
- API:

| 기능 | 주소 | 접근 권한 |
|---|---|---|
| 공지 목록 조회 | `GET /api/announcements/` | 관리자, 학생 모두 |
| 공지 작성 | `POST /api/announcements/create/` | 관리자만 |
| 공지 삭제 | `POST /api/announcements/<id>/delete/` | 관리자만 |

- `/announce/` 화면에서 관리자로 로그인하면 화면 위쪽에 "공지 작성" 폼과 각 공지 옆에 "삭제" 버튼이 보입니다. 학생 계정으로 로그인하면 이 폼과 버튼은 아예 나타나지 않고, 공지 목록만 읽을 수 있습니다.
- Django 관리자 화면(`/admin/`)에서도 `Announcement`를 등록해 두어 필요하면 그쪽에서도 공지를 관리할 수 있습니다.

---

## [보완] 1) 혼잡한 상황 => 다음반 담임에게 공지 자동 등록

학생증 스캔 결과 "혼잡"(`is_congested=True`)으로 판정되면, 그 순간 별도 조작 없이도
**이번 달 배식 순서상 다음 차례인 반**을 대상으로 하는 공지가 자동으로 등록되도록 보완했습니다.
코드 내에서 `# [보완: 신규 기능] 1) 혼잡한 상황 => 다음반 담임에게 공지 자동 등록` 주석으로
관련 부분을 표시해 두었습니다.

### 무엇이 바뀌었나
- 모델: `web/models.py`의 `Announcement`에 두 필드 추가 (마이그레이션 `0007_announcement_target_class.py`)
  - `target_class` : 이 공지가 "전체 공지"인지, "특정 반만을 위한 공지"인지 표시 (비어 있으면 전체 공지)
  - `is_auto` : 사람이 직접 쓴 공지인지, 시스템이 혼잡 상황을 감지해서 자동으로 만든 공지인지 구분
- 함수: `web/stats.py`의 `find_next_class_in_queue()` — 이번 달 홀수반/짝수반 순서(`ClassMealOrder`) 기준으로
  "지금 반 바로 다음 순서인 반" 1개를 찾음
- 뷰: `web/views.py`의 `notify_next_class_about_congestion()` — 혼잡으로 판정된 순간 `scan_barcode` 안에서 호출되어
  다음 반을 대상으로 하는 공지를 자동 생성 (같은 반에게 5분 안에 중복 알림이 쌓이지 않도록 방지 로직 포함)
- API: `list_announcements`가 계정 종류에 따라 다르게 필터링됨
  - 관리자: 전체 공지 + 모든 반 대상 공지를 다 봄
  - 학생: 전체 공지 + **자기 반**을 대상으로 한 공지만 봄
  - `create_announcement`도 `target_class_id`를 받아, 관리자가 수동으로 특정 반만 대상으로 공지를 쓸 수 있음(선택 사항, 비우면 예전처럼 전체 공지)
- 화면: `scan.html`은 자동 알림이 실제로 전송되면 "🔔 OO반에게 혼잡 알림 공지를 자동으로 보냈습니다"를 바로 보여주고,
  `announce.html`은 각 공지에 "대상 반" 뱃지와 "자동 알림" 뱃지를 붙여 구분해서 보여줍니다.

### 동작 조건
- 이 기능은 관리자가 `/announce/` 화면(또는 그 위쪽에서 안내하는 "배식 순서 설정" 화면)에서
  **이번 달 홀수반/짝수반 배식 순서(`ClassMealOrder`)를 미리 정해 둔 경우에만** 동작합니다.
  아직 순서를 정하지 않았다면 "다음 반"을 알 수 없으므로 자동 알림도 생기지 않습니다.
  (혼잡 판정 자체나 예상 대기시간 계산에는 영향이 없습니다)
- 내가 이번 달 그 그룹(홀수반/짝수반)의 마지막 순서라면 다음 반이 없으므로 알림이 생기지 않습니다.
# liik
