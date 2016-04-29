import pony.orm as pny
from flask import Flask, render_template
from flask_restful import Resource, Api

import numpy as np
from scipy.spatial import Voronoi
import geojson
import os

from public_transport_analyser.database.database import Origin, init
from public_transport_analyser.rest_backend.utils import voronoi_finite_polygons_2d

pta = Flask(__name__)
api = Api(pta)


@pta.route("/")
def index():
    return pta.send_static_file("origins.html")


class FetchAllOrigins(Resource):
    def get(self):
        lonlats = []

        with pny.db_session:
            origins = pny.select(o for o in Origin)[:]

            for o in origins:
                lat, lon = map(float, o.location.split(","))
                lonlats.append((lon, lat, len(o.destinations)))

        features = []
        for lat, lon, num_dest in lonlats:
            properties = {"num_dest": num_dest}  # ""{}".format(origin),}
            features.append(geojson.Feature(geometry=geojson.Point((lat, lon)), properties=properties))

        fc = geojson.FeatureCollection(features)
        return fc


class FetchOrigin(Resource):
    def get(self, origin):
        destinations = []

        with pny.db_session:
            if Origin.exists(location=origin):
                o = Origin.get(location=origin)
            else:
                raise ValueError("No such origin.")

            for d in o.destinations:
                dlat, dlon = map(float, d.location.split(","))
                destinations.append((dlon, dlat, len(d.trips)))

        features = []
        for dlat, dlon, num_trips in destinations:
            properties = {"trips": num_trips}  # ""{}".format(origin),}
            features.append(geojson.Feature(geometry=geojson.Point((dlon, dlat)), properties=properties))

        fc = geojson.FeatureCollection(features)

        return fc


def make_json(origin):

    regions, vertices = get_data(origin)

    features = []
    properties = {"color": "blue",
                  "strokeWeight": "1",}

    for r in regions:
        points = [(lon, lat) for lat, lon in vertices[r]]
        points.append(points[0])  # close off the polygon

        features.append(geojson.Feature(geometry=geojson.Polygon([points]),
                                        properties=properties,))

    fc = geojson.FeatureCollection(features)
    return geojson.dumps(fc, sort_keys=True)


def get_data(origin):

    with pny.db_session:
        if Origin.exists(location=origin):
            o = Origin.get(location=origin)
        else:
            raise ValueError("No such origin.")

        points = []
        lat, lon = o.location.split(",")

        for d in o.destinations:
            dlat, dlon = d.location.split(",")

            points.append((dlon, dlat))
        points = np.array(points)

        if points.shape[0] > 4:
            vor = Voronoi(points)
        else:
            raise ValueError("Not enough points to construct map. "
                             "Points = {}, need >4.".format(points.shape))

        return voronoi_finite_polygons_2d(vor, 0.05)


api.add_resource(FetchAllOrigins, '/api/origins')
api.add_resource(FetchOrigin, '/api/origin/<string:origin>')


if __name__ == "__main__":
    init()
    pta.debug = True
    pta.run()