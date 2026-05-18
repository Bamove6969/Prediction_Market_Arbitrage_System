import requests
import re
import logging
from typing import List, Dict, Any, Tuple, Optional
from datetime import datetime

logger = logging.getLogger(__name__)

# Basic city-to-coordinate mapping for common weather markets
CITY_COORDS = {
    "NYC": (40.7128, -74.0060),
    "NEW YORK": (40.7128, -74.0060),
    "LONDON": (51.5074, -0.1278),
    "CHICAGO": (41.8781, -87.6298),
    "LA": (34.0522, -118.2437),
    "LOS ANGELES": (34.0522, -118.2437),
    "MIAMI": (25.7617, -80.1918),
    "DC": (38.9072, -77.0369),
    "WASHINGTON": (38.9072, -77.0369),
    "SF": (37.7749, -122.4194),
    "SAN FRANCISCO": (37.7749, -122.4194),
    "ATL": (33.7490, -84.3880),
    "ATLANTA": (33.7490, -84.3880),
    "DALLAS": (32.7767, -96.7970),
    "AUSTIN": (30.2672, -97.7431),
    "HOUSTON": (29.7604, -95.3698),
    "PHOENIX": (33.4484, -112.0740),
    "DENVER": (39.7392, -104.9903),
    "SEATTLE": (47.6062, -122.3321),
    "BOSTON": (42.3601, -71.0589),
}

OPEN_METEO_ENSEMBLE_URL = "https://ensemble-api.open-meteo.com/v1/ensemble"

def extract_threshold(title: str) -> Optional[Tuple[str, float, str]]:
    """
    Extracts weather type (Temp, Rain), threshold value, and comparison (Above/Below) from title.
    Example: "Will NYC be above 80°F on July 4th?" -> ("temperature", 80.0, "above")
    """
    title = title.upper()
    
    # Temperature patterns
    temp_match = re.search(r'(\d+)\s*(?:°|DEGREES)?\s*(F|C)?', title)
    if temp_match:
        val = float(temp_match.group(1))
        # Determine comparison
        comp = "above" if "ABOVE" in title or "OVER" in title or "HIGHER" in title else "below"
        return ("temperature", val, comp)
    
    return None

def fetch_gfs_probability(lat: float, lon: float, weather_type: str, threshold: float, comparison: str, target_date: str) -> float:
    """
    Calls Open-Meteo GFS ensemble and calculates the probability of the threshold being met.
    Returns a value between 0 and 1.
    """
    try:
        params = {
            "latitude": lat,
            "longitude": lon,
            "hourly": "temperature_2m" if weather_type == "temperature" else "precipitation",
            "models": "gfs_seamless",
            "forecast_days": 16
        }
        resp = requests.get(OPEN_METEO_ENSEMBLE_URL, params=params, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        
        hourly = data.get("hourly", {})
        times = hourly.get("time", [])
        
        # Find indices for the target date
        # For simplicity, we'll check the full 24h window of that date
        target_indices = [i for i, t in enumerate(times) if target_date in t]
        if not target_indices:
            return 0.5 # Neutral if out of range
            
        # Extract ensemble members
        # Open-Meteo returns members as temperature_2m_member00, member01...
        members = [k for k in hourly.keys() if "_member" in k]
        
        hits = 0
        total_checks = 0
        
        for idx in target_indices:
            for m in members:
                val = hourly[m][idx]
                if comparison == "above" and val > threshold:
                    hits += 1
                elif comparison == "below" and val < threshold:
                    hits += 1
                total_checks += 1
        
        if total_checks == 0: return 0.5
        return hits / total_checks
        
    except Exception as e:
        logger.error(f"Weather Edge Error: {e}")
        return 0.5

def analyze_weather_market(market: Dict[str, Any]) -> Dict[str, Any]:
    """
    Analyzes a single weather market for an edge.
    """
    title = market.get("title", "")
    
    # 1. Identify City
    city = None
    for c in CITY_COORDS:
        if c in title.upper():
            city = c
            break
            
    if not city:
        return {"edge": 0, "confidence": 0, "recommendation": "neutral"}
        
    lat, lon = CITY_COORDS[city]
    
    # 2. Extract Threshold
    params = extract_threshold(title)
    if not params:
        return {"edge": 0, "confidence": 0, "recommendation": "neutral"}
        
    w_type, threshold, comp = params
    
    # 3. Get Model Probability
    # For now, we assume today or near future if target date not found
    target_date = datetime.now().strftime("%Y-%m-%d")
    model_prob = fetch_gfs_probability(lat, lon, w_type, threshold, comp, target_date)
    
    # 4. Compare with Market Price
    market_prob = market.get("yesPrice", 0.5)
    edge = model_prob - market_prob
    
    return {
        "modelProb": round(model_prob * 100, 1),
        "marketProb": round(market_prob * 100, 1),
        "edge": round(edge * 100, 1),
        "recommendation": "buy_yes" if edge > 0.05 else "buy_no" if edge < -0.05 else "hold",
        "city": city,
        "type": w_type
    }
