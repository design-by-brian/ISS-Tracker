from dash import dcc, html
import dash_bootstrap_components as dbc
import dash

from skyfield.api import EarthSatellite, load, wgs84
import plotly.express as px
import pandas as pd
import datetime

import configparser
import requests

class MyError(Exception):
    def __init___(self,args):
        Exception.__init__(self,"my exception was raised with arguments {0}".format(args))
        self.args = args

def _pull_tle():
    # See https://www.space-track.org/documentation for details on REST queries
    # the "Gp_HistISS" retrieves historical gp data for NORAD CAT ID=25544 (ISS) in the year 2023, JSON format.
    uriBase                = "https://www.space-track.org"
    requestLogin           = "/ajaxauth/login"
    requestCmdAction       = "/basicspacedata/query" 
    requestGp_HistISS      = "/class/gp/NORAD_CAT_ID/25544/orderby/TLE_LINE1 ASC/format/tle"

    # Use configparser package to pull in the ini file (pip install configparser)
    config = configparser.ConfigParser()
    config.read("./SLTrack.ini")
    configUsr = config.get("configuration","username")
    configPwd = config.get("configuration","password")
    configOut = config.get("configuration","output")
    siteCred = {'identity': configUsr, 'password': configPwd}

    tle = []

    # use requests package to drive the RESTful session with space-track.org
    with requests.Session() as session:
        print("Getting current tle from space-track.org session...") 
        # run the session in a with block to force session to close if we exit

        # need to log in first. note that we get a 200 to say the web site got the data, not that we are logged in
        resp = session.post(uriBase + requestLogin, data = siteCred)
        if resp.status_code != 200:
            raise MyError(resp, "POST fail on login")

        # this query picks up ISS gp data from 2023. Note - a 401 failure shows you have bad credentials 
        resp = session.get(uriBase + requestCmdAction + requestGp_HistISS)
        if resp.status_code != 200:
            print(resp)
            raise MyError(resp, "GET fail on request for Starlink satellites")

        # use the json package to break the json formatted response text into a Python structure
        line1, line2, _ = str.split(resp.text, '\r\n')
        tle = [line1, line2]
    return tle

def _get_sat_posn(tle):
    positions = {'name': [], 'lat': [], 'lon': [], 'datetime': []}

    ts = load.timescale()
    satellite = EarthSatellite(tle[0], tle[1], 'ISS', ts)
    t=ts.now().utc
    date = datetime.datetime(t[0], t[1], t[2], t[3], t[4], int(t[5]))

    for minute in range(-90, 90):
        newdate = date + datetime.timedelta(minutes=minute)
        positions['datetime'].append(newdate.strftime('%Y-%m-%dT%H:%M:%S%Z'))
        new_t = ts.utc(t[0], t[1], t[2], t[3], t[4]+minute, t[5])
        geocentric = satellite.at(new_t)
        lat, lon = wgs84.latlon_of(geocentric)
        lonDD = _dms_to_dd(lon.dms())
        latDD = _dms_to_dd(lat.dms())
        positions['name'].append('ISS')
        positions['lat'].append(latDD)
        positions['lon'].append(lonDD)

    return pd.DataFrame(positions)

def _dms_to_dd(dms):
    return dms[0] + dms[1]/60 + dms[2]/3600


app = dash.Dash()
app.title = 'ISS Tracker - Brian Smith'
server = app.server

def update_graph():
    tle = _pull_tle()
    positions = _get_sat_posn(tle)

    fig = px.scatter_geo(title='2D Projection of ISS Orbit on Earth',
                    labels={'lat': 'Latitude'},
                    data_frame=positions,
                    lat=positions['lat'],
                    lon=positions['lon'],
                    hover_name="name",
                    hover_data="datetime",
                    animation_frame="datetime",
                    width=1400,
                    height=800)
    citiesDF = pd.read_pickle('cities.pkl')
    fig.add_scattergeo(name='Cities',
                        customdata=citiesDF,
                        hoverinfo='text',
                        hovertext=citiesDF['city'].values,
                        lat=citiesDF['lat'],
                        lon=citiesDF['lng'],
                        mode='markers',
                        opacity=0.5,
                        marker={'size': citiesDF['population'].values}
                        )
    fig.add_scattergeo(name='Historical Path',
                    lat=positions['lat'][0:91],
                    lon=positions['lon'][0:91],
                    mode='lines',
                    opacity=0.5,
                    marker={'size': 10, 'color': 'black'},
                    line={'dash': 'dash'})
    fig.add_scattergeo(name='Future Path',
                    lat=positions['lat'][90:180],
                    lon=positions['lon'][90:180],
                    mode='lines',
                    opacity=0.5,
                    marker={'size': 10, 'color': 'black'})
    fig.add_scattergeo(name='ISS Current Position',
                    lat=[positions['lat'].iloc[90]],
                    lon=[positions['lon'].iloc[90]],
                    marker={'size': 12, 'color': 'blue'})
    return fig

app.layout = html.Div(children=[
    html.H1('ISS Tracker'),
    dcc.Graph(figure=update_graph())
])

if __name__ == '__main__':
    app.run_server(debug=True)