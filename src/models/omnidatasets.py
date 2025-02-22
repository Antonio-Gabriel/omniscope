import calendar
from datetime import datetime

from models.base.powerdataframe import SummarizablePowerDataFrame
from models.datasets.insights_dataset import InsightsDataset
from models.datasets.omni_dataset import OmniDataset
from models.datasets.ontology_entries_dataset import OntologyEntriesDataset
from models.datasets.tasks_dataset import TasksDataset
from models.datasets.timesheet_dataset import TimesheetDataset
from models.helpers.weeks import Weeks
from models.omnimodels import OmniModels

import models.helpers.slug as sl


def get_time_part_from_slug(slug: str) -> str:
    if slug.startswith('ontology-entries'):
        return slug[len('ontology-entries-'):]
    return slug.split('-', 1)[1]


def get_quarter_dates(quarter_slug: str) -> (datetime, datetime):
    q, year = quarter_slug.split('-')
    year = int(year)
    quarter = int(q[1])

    quarter_months = {
        1: (1, 3),
        2: (4, 6),
        3: (7, 9),
        4: (10, 12)
    }

    start_month, end_month = quarter_months[quarter]

    start_date = datetime(year, start_month, 1, 0, 0, 0, 0)
    end_date = datetime(year, end_month, calendar.monthrange(year, end_month)[1], 23, 59, 59, 9999)

    return start_date, end_date

def get_semester_dates(semester_slug: str) -> (datetime, datetime):
    q, year = semester_slug.split('-')
    year = int(year)
    quarter = int(q[1])

    semester_months = {
        1: (1, 6),
        2: (7, 12)
    }

    start_month, end_month = semester_months[quarter]

    start_date = datetime(year, start_month, 1, 0, 0, 0, 0)
    end_date = datetime(year, end_month, calendar.monthrange(year, end_month)[1], 23, 59, 59, 9999)

    return start_date, end_date

class OmniDatasets:
    def __init__(self, models: OmniModels = None):
        self.models = models
        self.timesheets = TimesheetDataset(models)
        self.ontology_entries = OntologyEntriesDataset(models)
        self.insights = InsightsDataset(models)
        self.tasks = TasksDataset(models)

    def get_dataset_source_by_slug(self, slug: str) -> OmniDataset:
        if not slug:
            return None

        if slug.startswith('timesheet'):
            return self.timesheets
        elif slug.startswith('insights'):
            return self.insights
        elif slug.startswith('ontology-entries'):
            return self.ontology_entries
        elif slug.startswith('tasks'):
            return self.tasks
        else:
            return None

    def get_by_slug(self, slug: str) -> SummarizablePowerDataFrame:
        if not slug:
            return None

        source = self.get_dataset_source_by_slug(slug)

        if slug.endswith('last-six-weeks'):
            return source.get_last_six_weeks()
        elif slug.endswith('all-tasks'):
            return source.get()
        elif slug.startswith('timesheet-s'):
            semester_slug = get_time_part_from_slug(slug)
            start, end = get_semester_dates(semester_slug)
            return source.get(start, end)
        elif slug.startswith('timesheet-q'):
            quarter_slug = get_time_part_from_slug(slug)
            start, end = get_quarter_dates(quarter_slug)
            return source.get(start, end)
        elif slug.endswith('this-semester'):
            now = datetime.now()
            slug = f"{('s1' if now.month <= 6 else 's2')}-{now.year}"
            start, end = get_semester_dates(slug)
            return source.get(start, end)
        elif slug.endswith('this-quarter'):
            now = datetime.now()
            current_month = now.month
            if current_month in [1, 2, 3]:
                slug = 'q1'
            elif current_month in [4, 5, 6]:
                slug = 'q2'
            elif current_month in [7, 8, 9]:
                slug = 'q3'
            else:
                slug = 'q4'

            slug = f'{slug}-{now.year}'
            start, end = get_quarter_dates(slug)
            return source.get(start, end)
        elif slug.endswith('this-month'):
            now = datetime.now()
            start = datetime(now.year, now.month, 1, hour=0, minute=0, second=0, microsecond=0)
            end = datetime(
                now.year, now.month, calendar.monthrange(now.year, now.month)[1], hour=23, minute=59, second=59,
                microsecond=9999
            )
            return source.get(start, end)
        elif slug.endswith('this-week'):
            start, end = Weeks.get_current_dates()
            return source.get(start, end)
        elif slug.endswith('previous-week'):
            start, end = Weeks.get_previous_dates(1)
            return source.get(start, end)

        month, year = slug.split('-')[-2:]
        month = list(calendar.month_name).index(month.capitalize())
        year = int(year)
        return source.get_specific_month(year, month)

    def get_datasets(self):
        result = [
            {'kind': 'Timesheet', 'name': 'Last Six Weeks'},
            {'kind': 'Timesheet', 'name': 'This Semester'},
            {'kind': 'Timesheet', 'name': 'This Quarter'},
            {'kind': 'Timesheet', 'name': 'This Month'},
            {'kind': 'Timesheet', 'name': 'This Week'},
            {'kind': 'Timesheet', 'name': 'Previous Week'}
        ]

        now = datetime.now()
        current_year = now.year
        current_month = now.month

        while True:
            current_month -= 1
            if current_month == 0:
                current_month = 12
                current_year -= 1
            if current_year == 2023 and current_month < 7:
                break
            month_name = calendar.month_name[current_month]

            if current_month % 3 == 0:
                result.append({'kind': 'Timesheet', 'name': f'Q{current_month // 3} {current_year}'})

            if current_month % 6 == 0:
                result.append({'kind': 'Timesheet', 'name': f'S{current_month // 6} {current_year}'})

            result.append({'kind': 'Timesheet', 'name': f'{month_name} {current_year}'})

        datasets_copy = result.copy()
        kinds = ['Ontology Entries', 'Insights']
        year_limits = {'Ontology Entries': (2024, 3), 'Insights': (2024, 3)}

        for kind in kinds:
            result.extend(datasets_copy)
            result.append({'kind': kind, 'name': 'Last Six Weeks'})
            result.append({'kind': kind, 'name': 'This Month'})
            result.append({'kind': kind, 'name': 'This Week'})
            result.append({'kind': kind, 'name': 'Previous Week'})

            now = datetime.now()
            current_year = now.year
            current_month = now.month

            while True:
                current_month -= 1
                if current_month == 0:
                    current_month = 12
                    current_year -= 1
                if current_year == year_limits[kind][0] and current_month < year_limits[kind][1]:
                    break
                month_name = calendar.month_name[current_month]
                result.append({'kind': kind, 'name': f'{month_name} {current_year}'})

        result.append({'kind': 'Tasks', 'name': 'All tasks'})

        return result

    def get_dataset_name_by_slug(self, slug):
        names = {
            sl.generate(f"{d['kind']} - {d['name']}"): d['name']
            for d in self.get_datasets()
        }
        return names.get(slug, None)

