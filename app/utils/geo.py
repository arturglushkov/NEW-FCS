import math
from typing import Tuple


def haversine(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Расстояние в метрах между двумя точками."""
    R = 6_371_000
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * R * math.asin(math.sqrt(a))


def check_location(user_lat: float, user_lon: float,
                   site_lat: float, site_lon: float,
                   radius: int) -> Tuple[bool, int]:
    """Возвращает (в_радиусе, расстояние_метров)."""
    dist = int(haversine(user_lat, user_lon, site_lat, site_lon))
    return dist <= radius, dist
