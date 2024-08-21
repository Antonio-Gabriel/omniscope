import logging
from datetime import datetime
from typing import List

import pandas as pd
import numpy as np

from models.base.cache import cache
from models.base.powerdataframe import SummarizablePowerDataFrame
from models.datasets.omni_dataset import OmniDataset
from models.helpers.weeks import Weeks
from models.omnimodels import OmniModels
from models.domain import ProductOrService


class TimesheetDataset(OmniDataset):
    def __init__(self, models: OmniModels = None):
        self.models = models or OmniModels()
        self.logger = logging.getLogger(self.__class__.__name__)

    def get_treemap_path(self):
        return 'TimeInHs', ['Kind', 'ClientName', 'WorkerName']

    def get_filterable_fields(self):
        return ['Kind', 'AccountManagerName', 'ClientName', 'CaseTitle', 'Sponsor', 'WorkerName']

    @cache
    def get(self, after: datetime, before: datetime) -> SummarizablePowerDataFrame:
        raw = self.models.tracker.get_appointments(after, before)
        ps_repo = self.models.products_or_services
        data = [
            ap.to_dict()
            for ap in raw
        ]
        df = pd.DataFrame(data)

        def enrich_row(row):
            try:
                row['date'] = row['date'].date()
                row['day_of_week'] = row['date'].strftime('%A')
                row['n_day_of_week'] = (row['date'].weekday() + 1) % 7
                row['month'] = row['date'].strftime('%B')
                row['year'] = row['date'].strftime('%Y')
                row['year_month'] = row['date'].strftime('%Y-%m')

                worker = self.models.workers.get_by_everhour_id(row['user_id'])
                row['worker_name'] = worker.name if worker else None
                row['worker_slug'] = worker.slug if worker else None
                row['worker_omni_url'] = worker.omni_url if worker else None
                row['worker'] = f"<a href='{worker.omni_url}'>{worker.name}</a>" if worker else None

                case = self.models.cases.get_by_everhour_project_id(row['project_id'])
                row['case_id'] = case.id
                row['case_title'] = case.title
                row['sponsor'] = case.sponsor
                row['case'] = f"<a href='{case.omni_url}'>{case.title}</a>"
                # row['case_omni_url'] = case.omni_url if case else None

                products_or_services: List[ProductOrService] = [
                    ps_repo.get_by_id(offer).name
                    for offer in case.offers_ids
                ]

                row['products_or_services'] = ';'.join(products_or_services)

                client = self.models.clients.get_by_id(case.client_id) if case.client_id else None
                row['client_id'] = client.id if client else "N/A"
                row['client_name'] = client.name if client else "N/A"
                row['client_omni_url'] = client.omni_url if client else "N/A"
                row['client'] = f"<a href='{client.omni_url}'>{client.name}</a>" if client else None

                if client and client.account_manager:
                    row['account_manager_name'] = client.account_manager.name
                    row['account_manager_slug'] = client.account_manager.slug
                else:
                    row['account_manager_name'] = "N/A"
                    row['account_manager_slug'] = "N/A"
            except Exception as e:
                self.logger.error(f'Failed to enrich row for case: {case.title}')

            return row

        df = df.apply(enrich_row, axis=1)

        return SummarizablePowerDataFrame(df)

    def get_common_fields(self):
        return ['Kind', 'ClientName', 'Sponsor', 'WorkerName', 'TimeInHs', 'Date', 'Week', 'IsLte']

    def get_all_fields(self):
        return ['Id',
                'CreatedAt',
                'Date',
                'DayOfWeek',
                'Month',
                'Year',
                'YearMonth',
                'UserId',
                'Time',
                'ProjectId',
                'IsSquad',
                'IsEximiaco',
                'Week',
                'TimeInHs',
                'Kind',
                'CreatedAtWeek',
                'Correctness',
                'IsLte',
                'WorkerName',
                'WorkerSlug',
                'WorkerOmniUrl',
                'Worker',
                'CaseId',
                'CaseTitle',
                'Sponsor',
                'Case',
                'ClientId',
                'ClientName',
                'ClientOmniUrl',
                'ProductsOrServices',
                'Client',
                'AccountManagerName',
                'AccountManagerSlug'
                ]

    def get_last_four_weeks_ltes(self) -> SummarizablePowerDataFrame:
        data = self.get_last_six_weeks()

        previous5 = Weeks.get_previous_string(5)
        previous6 = Weeks.get_previous_string(6)

        data = (data
                .filter_by(by='Correctness', not_equals_to='OK')
                .filter_by(by='Correctness', not_equals_to='Acceptable (1)')
                .filter_by(by='Correctness', not_starts_with='WTF -')
                .filter_by(by='CreatedAtWeek', not_equals_to=previous5)
                .filter_by(by='CreatedAtWeek', not_equals_to=previous6)
                )

        return data


def get_six_weeks_allocation_analysis(
        df: pd.DataFrame,
        date_of_interest: datetime
):
    week_day = (date_of_interest.weekday() + 1) % 7
    week = Weeks.get_week_string(date_of_interest)

    df = df[df['NDayOfWeek'] <= week_day]
    df_left = df[df['Week'] != week]
    df_right = df[df['Week'] == week]

    summary_left = df_left.groupby(['WorkerName', 'Week'])['TimeInHs'].sum().reset_index()
    summary_left = summary_left.groupby('WorkerName')['TimeInHs'].mean().reset_index()
    summary_left.rename(columns={'TimeInHs': 'Mean'}, inplace=True)

    summary_right = df_right.groupby('WorkerName')['TimeInHs'].sum().reset_index()
    summary_right.rename(columns={'TimeInHs': 'Current'}, inplace=True)
    merged_summary = pd.merge(summary_left, summary_right, on='WorkerName', how='outer').fillna(0)
    merged_summary.rename(columns={'WorkerName': 'Worker'}, inplace=True)

    merged_summary['Total'] = merged_summary['Current'] + merged_summary['Mean']
    merged_summary = merged_summary.sort_values(by='Total', ascending=False).reset_index(drop=True)
    merged_summary.drop(columns=['Total'], inplace=True)

    conditions = [
        merged_summary['Current'] > merged_summary['Mean'],
        merged_summary['Current'] < merged_summary['Mean'],
        merged_summary['Current'] == merged_summary['Mean']
    ]
    choices = [1, -1, 0]

    merged_summary['Status'] = np.select(conditions, choices, default=0)

    cols = ['Status', 'Worker', 'Mean', 'Current']
    return merged_summary[cols]


class TimesheetDateAnalysis:
    def __init__(self, df, date_of_interest: datetime):
        day_of_week = date_of_interest.strftime('%A')

        ds = df[df['Date'] == date_of_interest.date()]
        self.total_hours = ds['TimeInHs'].sum()

        ds = df[df['Date'] != date_of_interest.date()]
        ds = ds[ds['DayOfWeek'] == day_of_week]

        ds = ds.groupby('Date')['TimeInHs'].sum()

        if len(ds) > 0:
            self.best_day = ds.idxmax()
            self.best_day_hours = ds.max()

            self.worst_day = ds.idxmin()
            self.worst_day_hours = ds.min()

            self.average_hours = ds.mean()
        else:
            self.best_day = '-'
            self.best_day_hours = 0

            self.worst_day = '-'
            self.worst_day_hours = 0

            self.average_hours = 0


class TimeSheetFieldSummary:
    def __init__(self, df: pd.DataFrame, field: str):
        self.total_hours = df['TimeInHs'].sum()

        self.grouped_total_hours = df.groupby([field, 'Kind'])['TimeInHs'].sum().unstack().fillna(0)
        self.grouped_total_hours['Total'] = self.grouped_total_hours.sum(axis=1)
        self.grouped_total_hours = self.grouped_total_hours.sort_values('Total', ascending=False)

        self.unique = df[field].nunique()
        self.avg_hours = self.total_hours / self.unique
        self.std_hours = df.groupby([field])['TimeInHs'].sum().std()

        cumulative_hours = self.grouped_total_hours['Total'].cumsum()
        cumulative_hours_80 = cumulative_hours[cumulative_hours <= cumulative_hours.iloc[-1] * 0.80]
        if len(cumulative_hours_80) == 0:
            self.allocation_80 = 0
        else:
            self.allocation_80 = \
                cumulative_hours[cumulative_hours <= cumulative_hours.iloc[-1] * 0.80].index[-1]
