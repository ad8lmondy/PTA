import geojson
import pony.orm as pny
from flask import Flask
from flask.ext.cache import Cache
from flask_restful import Resource, Api
import logging

from public_transport_analyser.database.database import Origin, init
from public_transport_analyser.visualiser.utils import get_voronoi_map


pta = Flask(__name__)
cache = Cache(pta, config={'CACHE_TYPE': 'simple'})
api = Api(pta)

logger = logging.getLogger('PTA.flask')
logger.setLevel(logging.DEBUG)

ch = logging.StreamHandler()
ch.setLevel(logging.INFO)
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
ch.setFormatter(formatter)
logger.addHandler(ch)


@pta.route("/")
def index():
    logger.info("home page")
    return pta.send_static_file("origins.html")


@pta.route("/faq")
def faq():
    logger.info("faq page")
    return pta.send_static_file("faq.html")


class FetchAllOrigins(Resource):
    @cache.cached(timeout=300)
    def get(self):
        logger.info("Get all origins")
        lonlats = []
        try:
            with pny.db_session:
                origins = pny.select(o for o in Origin)[:]

                for o in origins:
                    lat, lon = map(float, o.location.split(","))
                    lonlats.append((lon, lat, len(o.destinations)))

            features = []
            for lon, lat, num_dest in lonlats:
                properties = {"num_dest": num_dest,
                              "isOrigin": True,
                              "location": ",".join(map(str, (lat,lon)))}  # ""{}".format(origin),}
                features.append(geojson.Feature(geometry=geojson.Point((lon, lat)), properties=properties))

            fc = geojson.FeatureCollection(features)

        except ValueError as ve:
            properties = {"num_dest": num_dest,
                          "isOrigin": True,
                          "location": "error! reload page."}
            f = geojson.Feature(geometry=geojson.Point((151.2,-33.9)), properties=properties)
            fc = geojson.FeatureCollection([f,])
        return fc


class FetchOrigin(Resource):
    def get(self, origin):
        destinations = []
        time = 6
        try:
            with pny.db_session:
                if Origin.exists(location=origin):
                    o = Origin.get(location=origin)
                else:
                    # TODO: use response codes
                    raise ValueError("No such origin.")

                num_dest = len(o.destinations)
                for d in o.destinations:
                    dlat, dlon = map(float, d.location.split(","))

                    driving = -1
                    transit = -1
                    for t in d.trips:
                        if t.mode == "driving":
                            driving = t.duration
                        elif t.time == time:
                            transit = t.duration

                    ratio = -1.0
                    if driving > 0 and transit > 0:
                        ratio = float(driving) / float(transit)

                    destinations.append((dlon, dlat, ratio))

            # Build GeoJSON features
            # Plot the origin point
            features = []
            olat, olon = map(float, origin.split(","))
            properties = {"isOrigin": True,
                          "num_dest": num_dest,  # TODO: this is why clicking fails
                          "location": (olat, olon),
                          }
            features.append(geojson.Feature(geometry=geojson.Point((olon, olat)), properties=properties))

            # Plot the destination points
            for details in destinations:
                dlon, dlat, ratio = details
                properties = {"ratio": ratio,
                              "isDestination": True,
                              "location": (dlon, dlat)}
                features.append(geojson.Feature(geometry=geojson.Point((dlon, dlat)), properties=properties))

            # Plot the destination map
            regions, vertices = get_voronoi_map(destinations)

            for i, region in enumerate(regions):
                ratio = destinations[i][2]
                properties = {"isPolygon": True,
                              "ratio": ratio}
                points = [(lon, lat) for lon, lat in vertices[region]]  # TODO: do some rounding to save bandwidth
                points.append(points[0])  # close off the polygon

                features.append(geojson.Feature(geometry=geojson.Polygon([points]),
                                                properties=properties, ))

            fc = geojson.FeatureCollection(features)

        except ValueError as ve:
            properties = {"isOrigin": True,
                          "num_dest": -1,
                          "location": "error! reload page.",
                          }
            f = geojson.Feature(geometry=geojson.Point((151.2,-33.9)), properties=properties)
            fc = geojson.FeatureCollection([f,])
        return fc


api.add_resource(FetchAllOrigins, '/api/origins')
api.add_resource(FetchOrigin, '/api/origin/<string:origin>')

init()  # Start up the DB

if __name__ == "__main__":
    pta.debug = False
    pta.run(host='0.0.0.0')
