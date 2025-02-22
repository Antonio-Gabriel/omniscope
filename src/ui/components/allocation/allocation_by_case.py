import pandas as pd
from dash import html, dcc
import dash_bootstrap_components as dbc
import plotly.express as px
import ui.components.base.cards as c


def render(data: pd.DataFrame, include_sponsor: bool = False):

    unique_cases_ids = data['CaseId'].unique().tolist()
    total_hours = data['TimeInHs'].sum()
    std_hours = data.groupby(['CaseId'])['TimeInHs'].sum().std()

    hours_by_case = (data.groupby('CaseId')['TimeInHs'].sum()
                     .reset_index()
                     .sort_values(by='TimeInHs', ascending=False)
                     )
    cases_ids = hours_by_case['CaseId'].tolist()

    # cards = [
    #     cc.render(globals.omni.cases.get_by_id(id))
    #     for id in cases_ids
    # ]

    data['All'] = 'All'

    path = ['All']

    if include_sponsor and data['Sponsor'].nunique() > 1:
        path = path + ['Sponsor']

    path = path + ['CaseTitle']

    if data['WorkerName'].nunique() > 1:
        path = path + ['WorkerName']

    try:
        fig = px.treemap(data, path=path, values='TimeInHs')
        fig.update_traces(textinfo="label+value+percent parent+percent root")
        fig.update_traces(root_color="lightgrey", marker=dict(cornerradius=3))
        fig.update_layout(margin=dict(t=25, l=10, r=10, b=10))
        treemap_area = dcc.Graph(figure=fig)
    except Exception as e:
        treemap_area = html.Div(f'Unable to create a treemap view ({e})', style={'margin-top': '10px'})

    return html.Div(
        [
            dbc.Row(
                [
                    c.create_kpi_card('Unique Cases', len(unique_cases_ids), 4),
                    c.create_kpi_card('Avg. Hours per Case', f'{total_hours / len(unique_cases_ids):.1f} hrs', 4),
                    c.create_kpi_card('Std. Hours per Case', f'{std_hours:.1f}', 4),
                ], style={'marginBottom': '10px'}
            ),
            dbc.Row(
                treemap_area
            )
        ]
    )
