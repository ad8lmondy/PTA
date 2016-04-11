import arrow
import api

def get_url(origins, destinations, mode, time):
    units = "metric"
    apikey=api.apikey

    url = "https://maps.googleapis.com/maps/api/distancematrix/json?" \
          "&units={units}" \
          "&origins={origins}" \
          "&destinations={destinations}" \
          "&mode={mode}" \
          "&departure_time={time}" \
          "&{apikey}".format(units=units,
                             origins=origins,
                             destinations=destinations,
                             mode=mode,
                             time=time,
                             apikey=apikey)

    return url


def convert_hour_to_epoch(hour):
    """
    We always need to look up times in the future, so the time is always set
    for tomorrow. Time is floored to the hour, and then set
    :param time:
    :return:
    """
    return arrow.now()\
                .floor('hour')\
                .replace(days=+1, hour=hour)\
                .to('utc')\
                .timestamp


def get_urls(origins, destinations):
    modes = ["transit", "driving"]
    hours = [6, 8, 12, 17, 21]

    urls = []

    for mode in modes:
        for hour in hours:
            epochtime = convert_hour_to_epoch(hour)
            urls.append(get_url(origins, destinations, mode, epochtime))

    return urls