import os
from datetime import timedelta, datetime, date

from django.utils import timezone
from googleapiclient.discovery import build  # pip install google-api-python-client
from oauth2client.service_account import ServiceAccountCredentials  # pip install --upgrade oauth2client

from shortener.models import DailyVisitors
from shrinkers import settings


def visitors():
    SCOPES = ["https://www.googleapis.com/auth/analytics.readonly"]
    KEY_FILE_LOCATION = os.path.join(settings.BASE_DIR, "shrinkers/service_key.json")
    VIEW_ID = "ga:250085819"
    print("Visitor Collected")
    today = datetime.utcnow() + timedelta(hours=9)
    today = date(today.year, today.month, today.day)
    yesterday = date(today.year, today.month, today.day) - timedelta(days=1)
    today_data = DailyVisitors.objects.filter(visit_date=today)
    yesterday_data = DailyVisitors.objects.filter(visit_date=yesterday)
    if not today_data.exists():
        yesterday_total = (
            DailyVisitors.objects.filter(visit_date__gte=today - timedelta(days=7))
            .order_by("-visit_date")[:1]
            .values("totals")
        )
        yesterday_total = yesterday_total[0]["totals"] if len(yesterday_total) > 0 else 0
        DailyVisitors.objects.create(
            visit_date=today, visits=1, totals=yesterday_total + 1, last_updated_on=timezone.now()
        )
    else:
        last_time = today_data.values()[0]["last_updated_on"]

        if last_time + timedelta(minutes=1) < timezone.now():

            def initialize_analytics_reporting():
                credentials = ServiceAccountCredentials.from_json_keyfile_name(KEY_FILE_LOCATION, SCOPES)
                return build("analyticsreporting", "v4", credentials=credentials)

            def get_report(_analytics):
                return (
                    _analytics.reports()
                    .batchGet(
                        body={
                            "reportRequests": [
                                {
                                    "viewId": VIEW_ID,
                                    "dateRanges": [{"startDate": "3daysAgo", "endDate": "today"}],
                                    "metrics": [{"expression": "ga:users"}],
                                    "dimensions": [{"name": "ga:date"}],
                                }
                            ]
                        }
                    )
                    .execute()
                )

            """
            {
                'viewId': VIEW_ID,
                'dateRanges': [{'startDate':  str(dateX) , 'endDate':  str(dateX)}],
                'metrics': [{'expression': 'ga:Transactions'}],
                'dimensions': [{"name": "ga:transactionId"},{"name": "ga:sourceMedium"},
                {"name": "ga:keyword"},{"name": "ga:deviceCategory"},{"name": "ga:campaign"},{"name": "ga:dateHourMinute"}],
                'samplingLevel': 'LARGE',
                "pageSize": 100000
              }
            https://ga-dev-tools.web.app/query-explorer/
            """
            analytics = initialize_analytics_reporting()
            response = get_report(analytics)
            data = response["reports"][0]["data"]["rows"]
            today_str = today.strftime("%Y%m%d")
            yesterday_str = yesterday.strftime("%Y%m%d")
            for i in data:
                get_value = int(i["metrics"][0]["totals"][0])
                if i["dimensions"] == [today_str]:
                    today_datas = today_data.values("visits", "totals")[0]
                    if get_value > today_datas["visits"]:
                        DailyVisitors.objects.filter(visit_date__exact=today).update(
                            visits=get_value,
                            totals=today_datas["totals"] - today_datas["visits"] + get_value,
                            last_updated_on=timezone.now(),
                        )
                elif i["dimensions"] == [yesterday_str]:
                    yesterdays = yesterday_data.values("visits", "totals")[0]
                    if get_value > yesterdays["visits"]:
                        DailyVisitors.objects.filter(visit_date__exact=yesterday).update(
                            visits=get_value,
                            totals=yesterdays["totals"] - yesterdays["visits"] + get_value,
                            last_updated_on=timezone.now(),
                        )
