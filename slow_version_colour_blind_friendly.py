import os
import base64
import pandas as pd
import dask.dataframe as dd
import plotly
from dash import Dash, dcc, html, Input, Output, State
from plotly.subplots import make_subplots
import plotly.graph_objects as go
from math import ceil
import time

# Base directory containing all dungeon folders
base_folder = "Dungeons"

# Dynamically discover all dungeon folders
dungeon_folders = [os.path.join(base_folder, folder) for folder in os.listdir(base_folder) if os.path.isdir(os.path.join(base_folder, folder))]

def extract_region(file_name):
    return file_name.split('_')[0]

dfs = []
for dungeon_folder in dungeon_folders:
    dungeon_name = os.path.basename(dungeon_folder)
    files = [file for file in os.listdir(dungeon_folder) if file.endswith(".csv")]
    for file in files:
        region = extract_region(file)
        df = dd.read_csv(
            os.path.join(dungeon_folder, file),
            dtype={'score': 'float64'}
        )
        df = df.assign(region=region, dungeon=dungeon_name)
        dfs.append(df)

dask_df = dd.concat(dfs)

required_columns = ['region', 'dungeon', 'mythic_level', 'player_role', 'player_class', 'player_spec']
if not all(col in dask_df.columns for col in required_columns):
    raise ValueError(f"One or more required columns are missing: {required_columns}")

region_mapping = {
    'world': 'World',
    'eu': 'Europe',
    'us': 'North America',
    'kr': 'Korea',
    'tw': 'Taiwan',
    'cn': 'China'
}

all_dungeons = dask_df['dungeon'].drop_duplicates().compute().tolist()
all_dungeons.insert(0, 'All Dungeons')

classes = ['Warrior', 'Paladin', 'Hunter', 'Rogue', 'Priest', 'Death Knight', 'Shaman', 'Mage', 'Warlock', 'Monk', 'Druid', 'Demon Hunter', 'Evoker']
colours = ['#C69B6D', '#F48CBA', '#AAD372', '#FFF468', '#FFFFFF', '#C41E3A', '#0070DD', '#3FC7EB', '#8788EE', '#00FF98', '#FF7C0A', '#A330C9', '#33937F']
class_colours = dict(zip(classes, colours))

all_mythic_levels = sorted(dask_df['mythic_level'].drop_duplicates().compute())

precomputed_data = dask_df.groupby(['region', 'dungeon', 'mythic_level', 'player_role', 'player_class', 'player_spec']).size().compute().reset_index(name='count')

app = Dash(__name__)
#Dropdowns
app.layout = html.Div([
    dcc.Store(id='hover-store', data={'last_update': None, 'hovered_class': None}),
    dcc.Interval(id='hover-checker', interval=500, n_intervals=0),

    dcc.Dropdown(
        id='dungeon-dropdown',
        options=[{'label': dungeon, 'value': dungeon} for dungeon in all_dungeons],
        value='All Dungeons',
        clearable=False,
        style={'width': '50%'}
    ),
    dcc.Dropdown(
        id='region-dropdown',
        options=[{'label': region_mapping[region], 'value': region} for region in region_mapping],
        value='world',
        clearable=False,
        style={'width': '50%'}
    ),
    dcc.Dropdown(
        id='role-dropdown',
        options=[{'label': role.capitalize(), 'value': role} for role in precomputed_data['player_role'].unique()],
        value='dps',
        clearable=False,
        style={'width': '50%'}
    ),
    dcc.Dropdown(
        id='hover-mode-dropdown',
        options=[
            {'label': 'Highlight All', 'value': 'all'},
            {'label': 'Highlight Specific', 'value': 'specific'}
        ],
        value='all',
        clearable=False,
        style={'width': '50%'}
    ),
    dcc.Graph(id='distribution-graph'),
    html.Hr(),
    html.Div(
        style={
            'display': 'flex',
            'flexDirection': 'row',
            'alignItems': 'flex-start'
        },
        children=[
            html.Div(
                children=[dcc.Graph(id='class-histogram')],
                style={'flex': '1', 'marginRight': '20px'}
            ),
            html.Div(
                id='custom-legend',
                style={
                    "display": "flex",
                    "flexDirection": "column",
                    "alignItems": "flex-start",
                    "gap": "10px",
                    "marginRight": "20px"
                }
            )
        ]
    )
])

def format_class_name(class_name):
    return class_name.lower().replace(" ", "")

def encode_image(image_path):
    try:
        with open(image_path, "rb") as img_file:
            return f"data:image/jpeg;base64,{base64.b64encode(img_file.read()).decode()}"
    except Exception as e:
        print(f"Error encoding image: {image_path} - {e}")
        return None

def hex_to_rgba(hex_color, alpha=1.0):
    """Convert hex color (#RRGGBB) to rgba(R,G,B,A)."""
    hex_color = hex_color.lstrip('#')
    r, g, b = tuple(int(hex_color[i:i+2], 16) for i in (0,2,4))
    return f'rgba({r},{g},{b},{alpha})'

def reorder_classes(dfs, classes):
    reordered_dfs = []
    previous_order = classes
    for df in dfs:
        df = df.set_index('player_class').reindex(classes, fill_value=0).reset_index()
        df['order'] = df['player_class'].apply(lambda cls: previous_order.index(cls))
        df = df.sort_values('order').drop(columns=['order'])
        reordered_dfs.append(df)
        previous_order = list(df['player_class'])
    return reordered_dfs

@app.callback(
    Output('hover-store', 'data'),
    Input('distribution-graph', 'hoverData'),
    State('hover-store', 'data')
)
def update_hover_store(hoverData, store):
    if hoverData and 'points' in hoverData and hoverData['points']:
        hovered_class = hoverData['points'][0].get('customdata', None)
        return {'last_update': time.time(), 'hovered_class': hovered_class}
    else:
        # If no points, just keep last_update (no actual update)
        # We can set hovered_class to None here if desired.
        return {'last_update': store.get('last_update', None), 'hovered_class': None}

#Stacked bar chart in the update_graph
@app.callback(
    Output('distribution-graph', 'figure'),
    [Input('dungeon-dropdown', 'value'),
     Input('region-dropdown', 'value'),
     Input('role-dropdown', 'value'),
     Input('hover-checker', 'n_intervals')],  # interval to check inactivity
    State('hover-store', 'data')
)
def update_graph(selected_dungeon, selected_region, selected_role, n_intervals, store):
    fig = go.Figure()

    # Determine if we should clear hovered_class after inactivity
    last_update = store.get('last_update', None)
    hovered_class = store.get('hovered_class', None)

    # If last_update is set and more than 2s have passed since, reset hovered_class
    if last_update is not None and (time.time() - last_update > 2.0):
        hovered_class = None

    if selected_dungeon == 'All Dungeons':
        role_data = precomputed_data[precomputed_data['player_role'] == selected_role]
    else:
        role_data = precomputed_data[
            (precomputed_data['dungeon'] == selected_dungeon) & 
            (precomputed_data['player_role'] == selected_role)
        ]

    if selected_region != 'world':
        role_data = role_data[role_data['region'] == selected_region]

    dfs = []
    no_data_range = []
    level_labels = []
    added_no_data_legend = False

    for mythic_level in all_mythic_levels:
        level_data = role_data[role_data['mythic_level'] == mythic_level]

        if level_data.empty:
            no_data_range.append(mythic_level)
        else:
            if no_data_range:
                range_label = (f'{no_data_range[0]}' if len(no_data_range) == 1 else f'{no_data_range[0]}-{no_data_range[-1]}')
                dfs.append(pd.DataFrame({
                    'player_class': classes,
                    'percentage': [0]*len(classes),
                    'mythic_level': range_label,
                    'no_data_available': True
                }))
                level_labels.append(f'{range_label}')
                no_data_range = []

            class_counts = level_data.groupby('player_class')['count'].sum().reset_index()
            class_counts['percentage'] = (class_counts['count'] / class_counts['count'].sum()) * 100
            class_counts = class_counts.set_index('player_class').reindex(classes, fill_value=0).reset_index()
            class_counts['mythic_level'] = mythic_level
            class_counts['no_data_available'] = False
            dfs.append(class_counts)
            level_labels.append(f'{mythic_level}')

    if no_data_range:
        range_label = (f'{no_data_range[0]}' if len(no_data_range) == 1 else f'{no_data_range[0]}-{no_data_range[-1]}')
        dfs.append(pd.DataFrame({
            'player_class': classes,
            'percentage': [0]*len(classes),
            'mythic_level': range_label,
            'no_data_available': True
        }))
        level_labels.append(f'{range_label}')

    reordered_dfs = reorder_classes(dfs, classes)
    classes_seen = set()

    for df in reordered_dfs:
        mythic_level = df['mythic_level'].iloc[0]
        no_data_available = df['no_data_available'].iloc[0]

        if no_data_available:
            fig.add_trace(go.Bar(
                y=[f'{mythic_level}'],
                x=[100],
                name='No Data Available',
                hovertext=["No data available"],
                hoverinfo='text',
                text="No data available",
                textposition='inside',
                insidetextanchor='middle',
                orientation='h',
                marker=dict(color='lightgrey', line=dict(width=0)),
                width=1,
                showlegend=not added_no_data_legend
            ))
            added_no_data_legend = True
        else:
            for cls, pct in zip(df['player_class'], df['percentage']):
                color = class_colours.get(cls, '#CCCCCC')
                if hovered_class is not None:
                    if cls == hovered_class:
                        bar_color = hex_to_rgba(color, 1.0)
                    else:
                        bar_color = hex_to_rgba(color, 0.3)
                else:
                    bar_color = hex_to_rgba(color, 1.0)

                fig.add_trace(go.Bar(
                    y=[f'{mythic_level}'],
                    x=[pct],
                    name=cls if cls not in classes_seen else None,
                    customdata=[cls],
                    hovertext=[f"{cls}: {pct:.2f}%"],
                    hoverinfo='text',
                    text=f"{pct:.2f}%",
                    textposition='inside',
                    orientation='h',
                    marker=dict(color=bar_color, line=dict(width=0)),
                    showlegend=cls not in classes_seen
                ))
                classes_seen.add(cls)

    fig.update_layout(
        title=f'{selected_role.upper()} Class Distribution by Mythic Level ({region_mapping[selected_region]})',
        xaxis=dict(
            showticklabels=False,
            tickvals=[],
            range=[0,100]
        ),
        yaxis=dict(
            title="Level",
            categoryorder='array',
            categoryarray=level_labels[::-1],
            autorange='reversed',
            ticks="",
            showline=False,
            tickfont=dict(size=10)
        ),
        barmode='stack',
        bargap=0,
        height=400 + len(level_labels)*20,
        showlegend=True
    )
    return fig

@app.callback(
    [Output('class-histogram', 'figure'),
     Output('custom-legend', 'children')],
    [Input('distribution-graph', 'clickData'),
     Input('role-dropdown', 'value'),
     Input('region-dropdown', 'value'),
     Input('class-histogram', 'hoverData'),
     Input('hover-mode-dropdown', 'value'),
     Input('distribution-graph', 'hoverData')] 
)
#Histograms
def update_class_histogram(clickData, selected_role, selected_region, hist_hoverData, hover_mode, top_hoverData):
    if not clickData:
        print("No clickData received")
        return go.Figure(), []

    print("ClickData received:", clickData)
    try:
        selected_class = clickData['points'][0]['customdata']
        print("Selected class:", selected_class)
    except KeyError as e:
        print(f"Error extracting selected class: {e}")
        return go.Figure(), []

    if not selected_role:
        print("No role selected!")
        return go.Figure(), []

    # Filter data
    filtered_by_class = precomputed_data[
        (precomputed_data['player_class'] == selected_class) &
        (precomputed_data['player_role'] == selected_role)
    ]
    if selected_region != 'world':
        filtered_by_class = filtered_by_class[filtered_by_class['region'] == selected_region]

    if filtered_by_class.empty:
        print("No data found after filtering for class, role, and region.")
        return go.Figure(), []

    if selected_region != 'world':
        total_dungeon_data = precomputed_data[
            (precomputed_data['region'] == selected_region) &
            (precomputed_data['player_role'] == selected_role)
        ]
    else:
        total_dungeon_data = precomputed_data[precomputed_data['player_role'] == selected_role]

    total_dungeon_data = (
        total_dungeon_data
        .groupby(['dungeon', 'mythic_level'])['count']
        .sum()
        .reset_index()
        .rename(columns={'count': 'total_dungeon_count'})
    )

    specialization_data = (
        filtered_by_class.groupby(['dungeon', 'mythic_level', 'player_spec'])['count']
        .sum()
        .reset_index()
    )

    specialization_data = pd.merge(
        specialization_data, total_dungeon_data, on=['dungeon', 'mythic_level'], how='inner'
    )

    if specialization_data.empty:
        print("No specialization data available after merging.")
        return go.Figure(), []

    specialization_data['percentage'] = (
        specialization_data['count'] / specialization_data['total_dungeon_count'] * 100
    )

    dungeons = specialization_data['dungeon'].unique()
    num_dungeons = len(dungeons)
    num_cols = 4
    num_rows = max(1, ceil(num_dungeons / num_cols))

    fig = make_subplots(
        rows=num_rows,
        cols=num_cols,
        subplot_titles=[f"{dungeon}" for dungeon in dungeons],
        shared_xaxes=False,
        vertical_spacing=0.15,
        horizontal_spacing=0.1
    )

    specialization_data = specialization_data.sort_values('player_spec')
    specialization_data['cumulative_percentage'] = specialization_data.groupby(['dungeon', 'mythic_level'])['percentage'].cumsum()
    specialization_data['midpoint'] = specialization_data['cumulative_percentage'] - (specialization_data['percentage'] / 2)

    specs = specialization_data['player_spec'].unique()

    # Determine hovered spec/level from histogram hover
    hovered_spec = None
    hovered_level = None
    if hist_hoverData and 'points' in hist_hoverData and hist_hoverData['points']:
        hovered_spec = hist_hoverData['points'][0].get('customdata', None)
        hovered_level = hist_hoverData['points'][0].get('x', None)
        print("Hovered spec:", hovered_spec, "Hovered level:", hovered_level)

    # Determine hovered class from top graph
    hovered_class = None
    if top_hoverData and 'points' in top_hoverData and top_hoverData['points']:
        hovered_class = top_hoverData['points'][0].get('customdata', None)
        print("Hovered class from top:", hovered_class)

    base_hex_color = class_colours.get(selected_class, '#CCCCCC')
    bar_width = 0.8

    for i, dungeon in enumerate(dungeons):
        row = (i // num_cols) + 1
        col = (i % num_cols) + 1
        dungeon_data = specialization_data[specialization_data['dungeon'] == dungeon]

        for spec in dungeon_data['player_spec'].unique():
            spec_data = dungeon_data[dungeon_data['player_spec'] == spec]
            x_values = spec_data['mythic_level'].values
            y_values = spec_data['percentage'].values

            # Only show spec name in hover
            hovertemplate = f"{spec}<extra></extra>"

            bar_colors = []
            line_colors = []
            for lvl, val in zip(x_values, y_values):
                is_hist_hover = (hovered_spec is not None and spec == hovered_spec and lvl == hovered_level)

                # Determine opacity logic:
                # Priority: hist hover > top hover > no hover
                if hovered_spec is not None:
                    # Hist hover scenario
                    if hover_mode == 'all':
                        if spec == hovered_spec:
                            bar_colors.append(hex_to_rgba(base_hex_color, 1.0))
                        else:
                            bar_colors.append(hex_to_rgba(base_hex_color, 0.3))
                    else:  # hover_mode == 'specific'
                        if is_hist_hover:
                            bar_colors.append(hex_to_rgba(base_hex_color, 1.0))
                        else:
                            bar_colors.append(hex_to_rgba(base_hex_color, 0.3))
                else:
                    # No hist hover, check top hover
                    if hovered_class is not None:
                        # Highlight hovered_class
                        if spec == hovered_class:
                            bar_colors.append(hex_to_rgba(base_hex_color, 1.0))
                        else:
                            bar_colors.append(hex_to_rgba(base_hex_color, 0.3))
                    else:
                        # No hover at all: all full opacity
                        bar_colors.append(hex_to_rgba(base_hex_color, 1.0))

                line_colors.append('black')

            fig.add_trace(
                go.Bar(
                    x=x_values,
                    y=y_values,
                    name=None,
                    customdata=[spec]*len(x_values),
                    hovertemplate=hovertemplate,
                    marker=dict(
                        color=bar_colors,
                        line=dict(color=line_colors, width=1)
                    ),
                    showlegend=False
                ),
                row=row,
                col=col
            )

            # Icons and annotation logic
            for _, row_data in spec_data.iterrows():
                segment_height = row_data['percentage']
                current_level = row_data['mythic_level']
                val = row_data['percentage']
                top_of_segment = row_data['cumulative_percentage']
                is_hist_hover = (hovered_spec is not None and spec == hovered_spec and current_level == hovered_level)

                # Icons logic
                add_icon = False
                if segment_height >= bar_width:
                    if hovered_spec is None:
                        add_icon = True
                    else:
                        if is_hist_hover:
                            add_icon = True

                    if add_icon:
                        xref = f"x{num_cols*(row-1)+col}"
                        yref = f"y{num_cols*(row-1)+col}"
                        spec_icon_name = f"{selected_class.replace(' ', '').lower()}_{spec.replace(' ', '').lower()}.jpg"
                        spec_icon_url = f"/assets/spec_icons/{spec_icon_name}"

                        fig.add_layout_image(
                            dict(
                                source=spec_icon_url,
                                x=current_level,
                                y=row_data['midpoint'],
                                xref=xref,
                                yref=yref,
                                sizex=bar_width,
                                sizey=segment_height,
                                xanchor="center",
                                yanchor="middle",
                                layer="above"
                            )
                        )

                # Annotation only if hist hover is present and this bar is hovered
                if is_hist_hover:
                    xref = f"x{num_cols*(row-1)+col}"
                    yref = f"y{num_cols*(row-1)+col}"
                    fig.add_annotation(
                        x=current_level,
                        y=top_of_segment + 0.5,
                        xref=xref,
                        yref=yref,
                        text=f"{val:.2f}%",
                        showarrow=False,
                        font=dict(color='white', size=10),
                        align='center',
                        bordercolor='white',
                        borderwidth=1,
                        borderpad=4,
                        bgcolor='rgba(0,0,0,0.8)',
                        xanchor='center',
                        yanchor='bottom'
                    )

    fig.update_layout(
        title=f'Distribution of {selected_class} Specializations by Dungeon ({selected_role.capitalize()} Role)',
        height=300 * num_rows,
        barmode='stack',
        showlegend=False
    )

    legend_children = []
    for spec in specs:
        spec_icon_name = f"{selected_class.replace(' ', '').lower()}_{spec.replace(' ', '').lower()}.jpg"
        spec_icon_url = f"/assets/spec_icons/{spec_icon_name}"
        legend_children.append(
            html.Div([
                html.Img(src=spec_icon_url, style={"width":"20px","height":"20px"}),
                html.Span(" " + spec)
            ], style={"display":"flex","alignItems":"center"})
        )

    return fig, legend_children



if __name__ == '__main__':
    app.run_server(debug=True)
