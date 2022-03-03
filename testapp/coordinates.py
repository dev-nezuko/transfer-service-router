import math


def parse_coordinates(latitude, longitude):
    if latitude is None or longitude is None or latitude == '' or longitude == '':
        raise ValueError("'lat' and 'lng' are required")
    try:
        lat, lng = float(latitude), float(longitude)
    except (TypeError, ValueError):
        raise ValueError("'lat' and 'lng' must be valid numbers") from None
    if not math.isfinite(lat) or not math.isfinite(lng) or not -90 <= lat <= 90 or not -180 <= lng <= 180:
        raise ValueError('Coordinates must be finite with latitude −90..90 and longitude −180..180')
    return lat, lng
