"""
Namma Payana - Core Configuration & Domain Parameters
Trip Reality Engine rules, bounds, and schedule constraints.
"""
from decimal import Decimal
import os
from dotenv import load_dotenv

load_dotenv()  # Load .env file if present

# --- Schedule Constraints ---
DAY_START_HOUR = 8
DAY_END_HOUR = 20

MAX_ACTIVE_HOURS = {
    "relaxed": 7.0,
    "balanced": 9.0,
    "packed": 11.0,
}

MAX_STOPS_PER_DAY = {
    "relaxed": 2,
    "balanced": 3,
    "packed": 4,
}

MAX_TRAVEL_HOURS_PER_DAY = {
    "relaxed": 3.0,
    "balanced": 4.5,
    "packed": 6.0,
}

AVG_SPEED_KMPH = {
    "bus": 40.0,
    "car": 50.0,
    "train": 45.0,
}

ROAD_DETOUR_FACTOR = 1.3  # Haversine straight line to actual road network estimate

# Road condition multipliers applied on top of base speed
# These reduce effective speed for difficult terrain/conditions
ROAD_CONDITION_MULTIPLIERS = {
    "ghat": 0.70,      # Western Ghats mountain roads: 30% slower than flat
    "monsoon": 0.80,   # Monsoon season (Jun-Sep): 20% slower due to road conditions
}

# Destination IDs that involve significant ghat road sections
GHAT_DESTINATIONS = {
    "jog_falls", "kudremukh_peak", "coorg_madikeri", "chikkamagaluru_mullayanagiri",
    "sringeri_sharada_peetham", "sakleshpur_railway_trek", "agumbe_sunset_point",
    "abbey_falls_coorg", "bhadra_wildlife_sanctuary", "dubare_elephant_camp"
}

# --- Feasibility Weights (Sum = 100) ---
FEASIBILITY_WEIGHTS = {
    "budget_fit": 30.0,
    "schedule_fit": 25.0,
    "route_efficiency": 15.0,
    "preference_alignment": 20.0,
    "data_confidence": 10.0,
}

# --- Budget Default Rates (Documented Rationale) ---
# Rates reflect prevailing Karnataka tourism benchmarks (KSTDC / private homestays 2025-2026).
DAILY_RATES = {
    "economical": {
        "stay_per_person": Decimal("700"),    # Dormitories, budget lodges, basic homestays
        "food_per_person": Decimal("400"),    # Darshinis, local Udupi/Khanavali canteens
        "local_transit": Decimal("200"),      # Local city buses, shared auto-rickshaws
    },
    "moderate": {
        "stay_per_person": Decimal("1600"),   # 2-3 star hotel / boutique plantation homestays
        "food_per_person": Decimal("800"),    # Sit-down regional thalis, tourist restaurants
        "local_transit": Decimal("500"),      # Dedicated autos, cab hops
    },
    "luxury": {
        "stay_per_person": Decimal("4500"),   # Heritage resorts, 4-5 star luxury properties
        "food_per_person": Decimal("1800"),   # Fine dining, signature coastal / royal cuisines
        "local_transit": Decimal("1200"),     # Dedicated private chauffeured AC cab
    },
}

# Transport cost per km estimates
TRANSPORT_COST_PER_KM = {
    "bus": Decimal("1.80"),   # KSRTC Karnataka Sarige / Rajahamsa average per person per km
    "car": Decimal("14.00"),  # Private hatchback/sedan taxi per total vehicle km
    "train": Decimal("0.90"), # Indian Railways Sleeper / 2S average per person per km
}

# Emergency Reserve percentage
DEFAULT_EMERGENCY_RESERVE_PCT = Decimal("0.10")  # 10%

# --- Geographic Bounds (Karnataka) ---
KARNATAKA_LAT_MIN = 11.5
KARNATAKA_LAT_MAX = 18.5
KARNATAKA_LNG_MIN = 74.0
KARNATAKA_LNG_MAX = 78.6

# Major Karnataka Transit Hubs (default coordinates for start cities)
START_CITIES = {
    "Bengaluru": (12.9716, 77.5946),
    "Mysuru": (12.2958, 76.6394),
    "Mangaluru": (12.9141, 74.8560),
    "Hubballi": (15.3647, 75.1240),
    "Belagavi": (15.8497, 74.4977),
    "Kalaburagi": (17.3297, 76.8343),
    "Shivamogga": (13.9299, 75.5681),
}

# --- Application Configuration ---
BASE_DIR = os.path.abspath(os.path.dirname(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")
DATABASE_PATH = os.environ.get("DATABASE_PATH", os.path.join(BASE_DIR, "instance", "nammapayana.db"))
SECRET_KEY = os.environ.get("SECRET_KEY", "dev-nammapayana-secret-2026")
MAX_CONTENT_LENGTH = 64 * 1024  # 64 KB strict request body limit

# Production guard: refuse to start with weak SECRET_KEY
if os.environ.get("FLASK_ENV", "").lower() == "production":
    if not SECRET_KEY or SECRET_KEY == "dev-nammapayana-secret-2026":
        raise RuntimeError(
            "FATAL: SECRET_KEY must be set to a strong random value in production. "
            "Do not use the development default."
        )

# --- AI / LLM Provider Configuration ---
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "").strip()
AI_PROVIDER = os.environ.get("AI_PROVIDER", "gemini" if GEMINI_API_KEY else "none").lower()

# --- Supabase Configuration ---
SUPABASE_URL = os.environ.get("SUPABASE_URL", "").strip()
SUPABASE_ANON_KEY = os.environ.get("SUPABASE_ANON_KEY", "").strip()
SUPABASE_PUBLISHABLE_KEY = os.environ.get("SUPABASE_PUBLISHABLE_KEY", "").strip()
SUPABASE_JWT_SECRET = os.environ.get("SUPABASE_JWT_SECRET", "").strip()

# --- Rate Limiting Configuration ---
RATE_LIMIT_TRANSLATE = os.environ.get("RATE_LIMIT_TRANSLATE", "10 per minute; 60 per hour")
RATE_LIMIT_GENERATE = os.environ.get("RATE_LIMIT_GENERATE", "20 per minute; 100 per hour")
RATE_LIMIT_REPLAN = os.environ.get("RATE_LIMIT_REPLAN", "30 per minute")

# --- CORS Configuration ---
ALLOWED_ORIGINS = [
    o.strip()
    for o in os.environ.get("ALLOWED_ORIGINS", "http://localhost:5000,http://127.0.0.1:5000").split(",")
    if o.strip()
]
