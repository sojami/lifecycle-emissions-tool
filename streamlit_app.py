import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import streamlit as st
from engine import REGION_DEFAULTS, EmissionResult, RegionInputs, VehicleInputs, breakeven_miles, build_reference_vehicle, compute_vehicle_emissions, generate_narrative, generate_recommendation, lookup_region_defaults, try_dynamic_lookup as engine_try_dynamic_lookup


st.set_page_config(
    page_title="Lifecycle Emissions Analyzer",
    page_icon=":car:",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown(
    """
    <style>
    [data-testid="stAppViewContainer"] {
        background: #F2D9DF !important;
    }

    [data-testid="stHeader"] {
        background: transparent !important;
    }

    [data-testid="stToolbar"] {
        color: #2B1B22 !important;
    }

    [data-testid="stSidebar"] {
        background: #E8F3B4 !important;
    }

    [data-testid="stSidebar"] * {
        color: #1F2A12 !important;
    }

    [data-testid="stSidebar"] input,
    [data-testid="stSidebar"] textarea,
    [data-testid="stSidebar"] [data-baseweb="input"] > div,
    [data-testid="stSidebar"] [data-baseweb="select"] > div,
    [data-testid="stSidebar"] [data-baseweb="base-input"] {
        background-color: #F8FBEA !important;
        color: #1F2A12 !important;
    }

    [data-testid="stSidebar"] button {
        color: inherit !important;
    }

    [data-testid="stAppViewContainer"] .main,
    [data-testid="stAppViewContainer"] .main .block-container {
        color: #2B1B22 !important;
    }

    [data-testid="stAppViewContainer"] .main h1,
    [data-testid="stAppViewContainer"] .main h2,
    [data-testid="stAppViewContainer"] .main h1 a,
    [data-testid="stAppViewContainer"] .main h2 a {
        color: #7A0019 !important;
    }

    [data-testid="stAppViewContainer"] .main h3,
    [data-testid="stAppViewContainer"] .main h4,
    [data-testid="stAppViewContainer"] .main h5,
    [data-testid="stAppViewContainer"] .main h6,
    [data-testid="stAppViewContainer"] .main h3 a,
    [data-testid="stAppViewContainer"] .main h4 a,
    [data-testid="stAppViewContainer"] .main h5 a,
    [data-testid="stAppViewContainer"] .main h6 a {
        color: #A30D2D !important;
    }

    [data-testid="stAppViewContainer"] .main p,
    [data-testid="stAppViewContainer"] .main li,
    [data-testid="stAppViewContainer"] .main label,
    [data-testid="stAppViewContainer"] .main .stMarkdown,
    [data-testid="stAppViewContainer"] .main .stMarkdown p,
    [data-testid="stAppViewContainer"] .main .stMarkdown li,
    [data-testid="stAppViewContainer"] .main [data-testid="stText"],
    [data-testid="stAppViewContainer"] .main [data-testid="stMarkdownContainer"] p,
    [data-testid="stAppViewContainer"] .main [data-testid="stMarkdownContainer"] li {
        color: #2B1B22 !important;
    }

    [data-testid="stAppViewContainer"] .main [data-testid="stMetricLabel"] {
        color: #7A0019 !important;
    }

    [data-testid="stAppViewContainer"] .main [data-testid="stMetricValue"] {
        color: #2B1B22 !important;
    }

    [data-testid="stAppViewContainer"] .main .stCaption,
    [data-testid="stAppViewContainer"] .main [data-testid="stCaptionContainer"] {
        color: #A30D2D !important;
    }

    [data-testid="stAppViewContainer"] .main .stAlert {
        background-color: rgba(122, 0, 25, 0.08) !important;
        border: 1px solid rgba(122, 0, 25, 0.18) !important;
    }

    [data-testid="stAppViewContainer"] .main .stAlert * {
        color: #2B1B22 !important;
    }
    </style>
    """,
    unsafe_allow_html=True,
)


TECH_OPTIONS = ["ICE", "HEV", "PHEV", "BEV"]
CLASS_OPTIONS = ["sedan", "compact_suv", "midsize_suv", "hatchback", "pickup", "van", "wagon", "coupe", "other"]
KNOWN_VEHICLE_CATALOG = [
    {"label": "Custom entry", "make": "", "model": "", "year": None, "tech_type": "ICE", "vehicle_class": "sedan"},
    {"label": "2024 Tesla Model 3", "make": "Tesla", "model": "Model 3", "year": 2024, "tech_type": "BEV", "vehicle_class": "sedan"},
    {"label": "2024 Tesla Model Y", "make": "Tesla", "model": "Model Y", "year": 2024, "tech_type": "BEV", "vehicle_class": "midsize_suv"},
    {"label": "2024 Toyota Prius", "make": "Toyota", "model": "Prius", "year": 2024, "tech_type": "HEV", "vehicle_class": "hatchback"},
    {"label": "2024 Toyota RAV4", "make": "Toyota", "model": "RAV4", "year": 2024, "tech_type": "ICE", "vehicle_class": "compact_suv"},
    {"label": "2024 Toyota RAV4 Hybrid", "make": "Toyota", "model": "RAV4 Hybrid", "year": 2024, "tech_type": "HEV", "vehicle_class": "compact_suv"},
    {"label": "2024 Ford F-150 Lightning", "make": "Ford", "model": "F-150 Lightning", "year": 2024, "tech_type": "BEV", "vehicle_class": "pickup"},
]

TECH_KEYWORDS = {
    "BEV": ["ev", "electric", "model 3", "model y", "leaf", "bolt", "ioniq 5", "mach-e"],
    "PHEV": ["plug-in", "phev", "prime", "volt"],
    "HEV": ["hybrid", "prius", "camry hybrid", "accord hybrid"],
}

CLASS_KEYWORDS = {
    "pickup": ["f-150", "silverado", "ram 1500", "tacoma", "ranger"],
    "compact_suv": ["rav4", "cr-v", "cx-5", "sportage", "escape", "rogue"],
    "midsize_suv": ["model y", "explorer", "pilot", "sorento", "highlander", "telluride"],
    "sedan": ["camry", "accord", "model 3", "civic", "corolla", "elantra", "altima"],
    "hatchback": ["golf", "leaf", "prius", "bolt", "fit"],
    "van": ["odyssey", "sienna", "pacifica", "transit"],
}


def detect_tech(text: str) -> str:
    normalized = text.lower()
    for tech_type, keywords in TECH_KEYWORDS.items():
        if any(keyword in normalized for keyword in keywords):
            return tech_type
    return "ICE"


def detect_vehicle_class(text: str) -> str:
    normalized = text.lower()
    for vehicle_class, keywords in CLASS_KEYWORDS.items():
        if any(keyword in normalized for keyword in keywords):
            return vehicle_class
    return "other"

def build_vehicle_name(year: int | None, make: str, model: str) -> str:
    return " ".join(part for part in [str(year) if year else "", make.strip(), model.strip()] if part).strip()


REGION_OPTIONS = sorted(REGION_DEFAULTS.keys()) + ["United States", "Other"]
US_STATE_OPTIONS = ["N/A", "Minnesota", "California", "Texas", "New York", "Florida"]


def format_region_label(region_key: str) -> str:
    if region_key == "United States":
        return "United States"
    if region_key == "usa":
        return "USA"
    if region_key == "uk":
        return "UK"
    if region_key == "uae":
        return "UAE"
    if region_key == "eu_average":
        return "EU Average"
    if region_key == "global_average":
        return "Global Average"
    return region_key.replace("_", " ").title()


# --------------------------------------------------------------------
# CLEAN + ROBUST VEHICLE LOOKUP FUNCTIONS
# --------------------------------------------------------------------

def get_vehicle_specs(make, model, year, vehicle_class, tech_type):
    """
    Full 3-layer cascade:
    1. Provider lookup (via engine.try_dynamic_lookup)
    2. Curated internal data (inside engine)
    3. Fallback table (inside engine)
    """

    # Normalize inputs
    vc = (vehicle_class or "").strip().lower()
    tt = (tech_type or "").strip().lower()

    # Call the engine's full cascade
    specs = engine_try_dynamic_lookup(make, model, year, vc, tt)

    # If engine returns something valid, use it
    if specs:
        return specs

    fallback_class_map = {
        "compact_suv": "suv",
        "midsize_suv": "suv",
        "pickup": "truck",
        "hatchback": "sedan",
        "van": "suv",
        "wagon": "sedan",
        "coupe": "sedan",
        "other": "sedan",
    }
    safe_class = fallback_class_map.get(vc, vc or "sedan")
    safe_tech = tt or "ice"

    # Absolute safety fallback (never fail)
    if safe_tech == "bev":
        return {
            "vehicle_class": vc or "sedan",
            "tech_type": "BEV",
            "vehicle_mfg_kg": 1800,
            "battery_kwh": 60,
            "kwh_per_mile": 0.30,
            "fuel_economy_mpg": None,
            "curb_weight": 1800,
            "fuel_eff": None,
        }
    if safe_tech == "phev":
        return {
            "vehicle_class": vc or "sedan",
            "tech_type": "PHEV",
            "vehicle_mfg_kg": 1800,
            "battery_kwh": 14,
            "kwh_per_mile": 0.33,
            "fuel_economy_mpg": 35,
            "curb_weight": 1800,
            "fuel_eff": 35,
        }
    if safe_tech == "hev":
        return {
            "vehicle_class": vc or "sedan",
            "tech_type": "HEV",
            "vehicle_mfg_kg": 1700,
            "battery_kwh": 1.5,
            "kwh_per_mile": None,
            "fuel_economy_mpg": 50,
            "curb_weight": 1700,
            "fuel_eff": 50,
        }

    return {
        "vehicle_class": safe_class,
        "tech_type": "ICE",
        "vehicle_mfg_kg": 1800 if safe_class == "sedan" else 2000 if safe_class == "suv" else 2500,
        "battery_kwh": 0,
        "kwh_per_mile": None,
        "fuel_economy_mpg": 30 if safe_class == "sedan" else 22 if safe_class == "suv" else 18,
        "curb_weight": 1800 if safe_class == "sedan" else 2000 if safe_class == "suv" else 2500,
        "fuel_eff": 30 if safe_class == "sedan" else 22 if safe_class == "suv" else 18,
    }

# --------------------------------------------------------------------
# END OF REPLACEMENT
# --------------------------------------------------------------------


def get_vehicle_suggestion(label: str) -> dict | None:
    for vehicle in KNOWN_VEHICLE_CATALOG:
        if vehicle["label"] == label:
            return vehicle
    return None


def vehicle_summary(vehicle: VehicleInputs, result: EmissionResult) -> dict:
    return {
        "Vehicle": vehicle.name,
        "Technology Type": vehicle.tech_type,
        "Vehicle Class": vehicle.vehicle_class,
        "Upstream (kg CO2e)": round(result.upstream_kg, 2),
        "Downstream (kg CO2e)": round(result.downstream_kg, 2),
        "Total (kg CO2e)": round(result.total_kg, 2),
        "Per Mile (kg CO2e/mile)": round(result.per_mile_kg, 4),
        "Lifetime Miles": round(vehicle.lifetime_miles, 0),
    }


def build_emissions_curve_data(
    car_a: VehicleInputs,
    car_b: VehicleInputs,
    res_a: EmissionResult,
    res_b: EmissionResult,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    miles = np.linspace(0, car_a.lifetime_miles, 50)
    car_a_curve = res_a.per_mile_kg * miles + res_a.upstream_kg
    car_b_curve = res_b.per_mile_kg * miles + res_b.upstream_kg
    return miles, car_a_curve, car_b_curve


def render_vehicle_inputs(prefix: str, title: str, lifetime_miles: float) -> dict:
    st.markdown(f"### {title}")
    suggestion_label = st.selectbox(
        f"{title} suggested entry",
        [vehicle["label"] for vehicle in KNOWN_VEHICLE_CATALOG],
        key=f"{prefix}_suggested_vehicle",
        help="Search and select a known vehicle to autofill the structured fields, or keep Custom entry.",
    )
    suggested_vehicle = get_vehicle_suggestion(suggestion_label)
    if suggested_vehicle and suggested_vehicle["label"] != "Custom entry":
        st.session_state[f"{prefix}_make"] = suggested_vehicle["make"]
        st.session_state[f"{prefix}_model"] = suggested_vehicle["model"]
        st.session_state[f"{prefix}_include_year"] = suggested_vehicle["year"] is not None
        if suggested_vehicle["year"] is not None:
            st.session_state[f"{prefix}_year"] = suggested_vehicle["year"]
        st.session_state[f"{prefix}_tech_type"] = suggested_vehicle["tech_type"]
        st.session_state[f"{prefix}_vehicle_class"] = suggested_vehicle["vehicle_class"]

    make = st.text_input("Make", key=f"{prefix}_make")
    model = st.text_input("Model", key=f"{prefix}_model")
    inferred_text = f"{make} {model}".strip()

    include_year = st.checkbox(
        "Include year",
        key=f"{prefix}_include_year",
        value=st.session_state.get(f"{prefix}_include_year", suggested_vehicle["year"] is not None if suggested_vehicle else False),
    )
    year = None
    if include_year:
        year = int(
            st.number_input(
                "Year",
                min_value=1990,
                max_value=2035,
                step=1,
                key=f"{prefix}_year",
                value=st.session_state.get(f"{prefix}_year", suggested_vehicle["year"] if suggested_vehicle and suggested_vehicle["year"] else 2024),
            )
        )

    detected_tech_type = detect_tech(inferred_text) if inferred_text else "ICE"
    detected_vehicle_class = detect_vehicle_class(inferred_text) if inferred_text else "other"
    tech_type = st.selectbox(
        "Technology Type",
        TECH_OPTIONS,
        index=TECH_OPTIONS.index(st.session_state.get(f"{prefix}_tech_type", detected_tech_type)),
        key=f"{prefix}_tech_type",
        help="Autofilled from a suggested vehicle when selected, but fully editable.",
    )
    vehicle_class = st.selectbox(
        "Vehicle Class",
        CLASS_OPTIONS,
        index=CLASS_OPTIONS.index(
            st.session_state.get(
                f"{prefix}_vehicle_class",
                detected_vehicle_class if detected_vehicle_class in CLASS_OPTIONS else "other",
            )
        ),
        key=f"{prefix}_vehicle_class",
        help="Autofilled from a suggested vehicle when selected.",
    )

    normalized_tech_type = tech_type.upper()
    normalized_vehicle_class = vehicle_class.lower()
    specs = get_vehicle_specs(make, model, year, normalized_vehicle_class, normalized_tech_type)
    resolved_tech_type = specs.get("tech_type", normalized_tech_type)
    resolved_vehicle_class = specs.get("vehicle_class", normalized_vehicle_class)
    if resolved_tech_type != tech_type:
        tech_type = resolved_tech_type
    if resolved_vehicle_class != vehicle_class:
        vehicle_class = resolved_vehicle_class

    defaults = {
        "fuel_economy_mpg": specs.get("fuel_economy_mpg", specs.get("fuel_eff")),
        "kwh_per_mile": specs.get("kwh_per_mile"),
        "battery_kwh": specs.get("battery_kwh"),
        "vehicle_mfg_kg": specs.get("vehicle_mfg_kg", specs.get("curb_weight")),
    }
    fuel_economy_mpg = None
    kwh_per_mile = None
    battery_kwh = None

    if tech_type in {"ICE", "HEV", "PHEV"}:
        fuel_economy_mpg = st.number_input(
            "Fuel economy (mpg)",
            min_value=1.0,
            step=1.0,
            key=f"{prefix}_fuel_economy_mpg",
            value=float(defaults["fuel_economy_mpg"]),
        )

    if tech_type in {"BEV", "PHEV"}:
        kwh_per_mile = st.number_input(
            "Electricity use (kWh/mile)",
            min_value=0.01,
            step=0.01,
            key=f"{prefix}_kwh_per_mile",
            value=float(defaults["kwh_per_mile"]),
        )

    if tech_type in {"BEV", "PHEV", "HEV"}:
        battery_kwh = st.number_input(
            "Battery size (kWh)",
            min_value=0.1,
            step=0.1,
            key=f"{prefix}_battery_kwh",
            value=float(defaults["battery_kwh"]),
        )

    vehicle_mfg_kg = st.number_input(
        "Vehicle manufacturing (kg CO2e, excluding battery)",
        min_value=0.0,
        step=100.0,
        key=f"{prefix}_vehicle_mfg_kg",
        value=float(defaults["vehicle_mfg_kg"]),
    )
    battery_mfg_kg_per_kwh = st.number_input(
        "Battery manufacturing factor (kg CO2e/kWh)",
        min_value=0.0,
        step=1.0,
        key=f"{prefix}_battery_mfg_kg_per_kwh",
        value=80.0,
    )

    vehicle_name = build_vehicle_name(year, make, model) or title
    return {
        "make": make,
        "model": model,
        "year": year,
        "name": vehicle_name,
        "tech_type": tech_type,
        "vehicle_class": vehicle_class,
        "lifetime_miles": float(lifetime_miles),
        "fuel_economy_mpg": float(fuel_economy_mpg) if fuel_economy_mpg is not None else None,
        "kwh_per_mile": float(kwh_per_mile) if kwh_per_mile is not None else None,
        "battery_kwh": float(battery_kwh) if battery_kwh is not None else None,
        "vehicle_mfg_kg": float(vehicle_mfg_kg),
        "battery_mfg_kg_per_kwh": float(battery_mfg_kg_per_kwh),
    }


def run_analysis(
    vehicle_a: VehicleInputs,
    vehicle_b: VehicleInputs | None,
    region: RegionInputs,
    used_default_flag: bool,
) -> dict:
    res_a = compute_vehicle_emissions(vehicle_a, region)
    pairs = [(vehicle_a, res_a)]
    res_b = None
    if vehicle_b:
        res_b = compute_vehicle_emissions(vehicle_b, region)
        pairs.append((vehicle_b, res_b))

    results_table = pd.DataFrame([vehicle_summary(vehicle, result) for vehicle, result in pairs])
    best_vehicle, best_result = min(pairs, key=lambda item: item[1].total_kg)
    _, worst_result = max(pairs, key=lambda item: item[1].total_kg)
    emissions_gap = round(worst_result.total_kg - best_result.total_kg, 2)

    breakeven_text = None
    miles_be = None
    if len(pairs) == 2:
        first_vehicle, first_result = pairs[0]
        second_vehicle, second_result = pairs[1]
        miles_be = breakeven_miles(first_result, second_result)
        if miles_be is None:
            breakeven_text = "A positive breakeven point was not found with the current upstream and per-mile assumptions."
        else:
            lower_running_vehicle = first_vehicle if first_result.per_mile_kg < second_result.per_mile_kg else second_vehicle
            breakeven_text = (
                f"{lower_running_vehicle.name} reaches lifecycle breakeven at approximately {miles_be:,.0f} miles."
            )

    if vehicle_b and res_b:
        miles, car_a_curve, car_b_curve = build_emissions_curve_data(vehicle_a, vehicle_b, res_a, res_b)
        curve_data = {
            "miles": miles,
            "car_a_curve": car_a_curve,
            "car_b_curve": car_b_curve,
            "car_a_name": vehicle_a.name,
            "car_b_name": vehicle_b.name,
        }
        narrative = generate_narrative(
            vehicle_a,
            vehicle_b,
            res_a,
            res_b,
            miles_be if len(pairs) == 2 else None,
            region,
            used_default_flag=used_default_flag,
        )
        recommendation = generate_recommendation(
            vehicle_a,
            vehicle_b,
            res_a,
            res_b,
            miles_be,
            region,
            used_default_flag=used_default_flag,
        )
    else:
        curve_data = None
        narrative = (
            f"In {region.name}, {best_vehicle.name} has the lowest modeled lifecycle footprint at "
            f"{best_result.total_kg:,.0f} kg CO2e."
        )
        recommendation = f"Overall, based on lifecycle emissions, {best_vehicle.name} is the lower-carbon choice."

    return {
        "summary": {
            "best_vehicle": best_vehicle.name,
            "best_total_kg": round(best_result.total_kg, 2),
            "emissions_gap_kg": emissions_gap,
        },
        "breakeven": breakeven_text,
        "table": results_table,
        "curve_data": curve_data,
        "narrative": narrative,
        "recommendation": recommendation,
        "used_reference_vehicle": vehicle_b is not None and vehicle_b.name.startswith("Average "),
    }


st.title("Lifecycle Carbon Modeling & Supply Chain Emissions Analytics")
st.caption("Compare vehicle lifecycle emissions using natural language entry or structured inputs.")

with st.sidebar:
    st.header("Inputs")
    st.write("Use the quick-entry boxes, the structured fields, or a mix of both.")

    st.markdown("### Region")
    default_region_index = REGION_OPTIONS.index("usa") if "usa" in REGION_OPTIONS else 0
    country = st.selectbox(
        "Country",
        REGION_OPTIONS,
        index=default_region_index,
        format_func=format_region_label,
    )

    state = "N/A"
    if country == "United States":
        state = st.selectbox("Select State", US_STATE_OPTIONS)

    if country == "United States":
        if state != "N/A":
            region_data = lookup_region_defaults(state.lower())
            region_display_name = state
        else:
            region_data = lookup_region_defaults("usa_average")
            region_display_name = "United States"
    else:
        region_data = lookup_region_defaults(country.lower())
        region_display_name = format_region_label(country)

    region_defaults, used_default_flag = region_data

    if used_default_flag:
        st.caption("Using global average values because region-specific data was unavailable.")

    grid_kg_per_kwh = st.number_input(
        "Grid emissions factor (kg CO2e/kWh)",
        min_value=0.0,
        step=0.01,
        value=float(region_defaults["grid_kg_per_kwh"]),
    )
    fuel_kg_per_gallon = st.number_input(
        "Fuel emissions factor (kg CO2e/gallon)",
        min_value=0.0,
        step=0.01,
        value=float(region_defaults["fuel_kg_per_gallon"]),
    )
    lifetime_miles = st.number_input(
        "Lifetime mileage",
        min_value=1_000.0,
        max_value=500_000.0,
        step=5_000.0,
        value=150_000.0,
    )

    car_a = render_vehicle_inputs("car_a", "Car A", lifetime_miles)
    add_second_car = st.toggle("Compare with a second car")
    car_b = render_vehicle_inputs("car_b", "Car B", lifetime_miles) if add_second_car else None

    run_clicked = st.button("Run Analysis", type="primary", use_container_width=True)


if "analysis_results" not in st.session_state:
    st.session_state.analysis_results = None


if run_clicked:
    if not car_a["name"] or car_a["name"] == "Car A":
        st.sidebar.error("Please complete Car A before running the analysis.")
    elif add_second_car and car_b and (not car_b["name"] or car_b["name"] == "Car B"):
        st.sidebar.error("Please complete Car B or turn off the second-car comparison.")
    else:
        grid_intensity_value = float(grid_kg_per_kwh)
        fuel_intensity_value = float(fuel_kg_per_gallon)
        region = RegionInputs(
            name=region_display_name,
            grid_kg_per_kwh=grid_intensity_value,
            fuel_kg_per_gallon=fuel_intensity_value,
        )
        car_a_name = car_a["name"]
        car_a_tech = car_a["tech_type"]
        car_a_class = car_a["vehicle_class"]
        car_a_mpg = car_a["fuel_economy_mpg"]
        car_a_kwh_per_mile = car_a["kwh_per_mile"]
        car_a_battery_kwh = car_a["battery_kwh"]
        car_a_mfg_kg = car_a["vehicle_mfg_kg"]
        car_a_battery_mfg_kg_per_kwh = car_a["battery_mfg_kg_per_kwh"]

        vehicle_a = VehicleInputs(
            name=car_a_name,
            tech_type=car_a_tech,
            vehicle_class=car_a_class,
            lifetime_miles=lifetime_miles,
            fuel_economy_mpg=car_a_mpg,
            kwh_per_mile=car_a_kwh_per_mile,
            battery_kwh=car_a_battery_kwh,
            vehicle_mfg_kg=car_a_mfg_kg,
            battery_mfg_kg_per_kwh=car_a_battery_mfg_kg_per_kwh,
        )

        vehicle_b = None
        if add_second_car and car_b:
            car_b_name = car_b["name"]
            car_b_tech = car_b["tech_type"]
            car_b_class = car_b["vehicle_class"]
            car_b_mpg = car_b["fuel_economy_mpg"]
            car_b_kwh_per_mile = car_b["kwh_per_mile"]
            car_b_battery_kwh = car_b["battery_kwh"]
            car_b_mfg_kg = car_b["vehicle_mfg_kg"]
            car_b_battery_mfg_kg_per_kwh = car_b["battery_mfg_kg_per_kwh"]

            vehicle_b = VehicleInputs(
                name=car_b_name,
                tech_type=car_b_tech,
                vehicle_class=car_b_class,
                lifetime_miles=lifetime_miles,
                fuel_economy_mpg=car_b_mpg,
                kwh_per_mile=car_b_kwh_per_mile,
                battery_kwh=car_b_battery_kwh,
                vehicle_mfg_kg=car_b_mfg_kg,
                battery_mfg_kg_per_kwh=car_b_battery_mfg_kg_per_kwh,
            )
        else:
            vehicle_b = build_reference_vehicle(vehicle_a, region)

        st.session_state.analysis_results = run_analysis(vehicle_a, vehicle_b, region, used_default_flag)


results = st.session_state.analysis_results

if results is None:
    st.info("Configure the vehicles in the sidebar, then click `Run Analysis` to see results.")
else:
    summary = results["summary"]

    if results["used_reference_vehicle"]:
        st.info("A reference vehicle was auto-generated using the same class and the opposite technology type.")

    st.subheader("Summary")
    col1, col2, col3 = st.columns(3)
    col1.metric("Lowest Emissions Vehicle", summary["best_vehicle"])
    col2.metric("Best Total Lifecycle Emissions", f"{summary['best_total_kg']:,.0f} kg CO2e")
    col3.metric("Scenario Spread", f"{summary['emissions_gap_kg']:,.0f} kg CO2e")

    st.subheader("Breakeven")
    st.write(results["breakeven"] or "Breakeven will appear when two vehicles are compared.")
    if results["curve_data"] is not None:
        st.subheader("Cumulative Emissions Chart")
        miles = results["curve_data"]["miles"]
        car_a_curve = results["curve_data"]["car_a_curve"]
        car_b_curve = results["curve_data"]["car_b_curve"]
        car_a_name = results["curve_data"]["car_a_name"]
        car_b_name = results["curve_data"]["car_b_name"]

        fig, ax = plt.subplots(figsize=(10, 6))
        ax.plot(miles, car_a_curve, label=car_a_name, color="crimson", linewidth=2.5)
        ax.fill_between(miles, car_a_curve, color="crimson", alpha=0.3)

        ax.plot(miles, car_b_curve, label=car_b_name, color="royalblue", linewidth=2.5)
        ax.fill_between(miles, car_b_curve, color="royalblue", alpha=0.3)

        ax.set_title("Cumulative Emissions Over Vehicle Lifetime", fontsize=16, weight="bold")
        ax.set_xlabel("Miles Driven")
        ax.set_ylabel("Cumulative CO2 Emissions (kg)")
        ax.legend()
        ax.grid(True)

        st.pyplot(fig)
        plt.close(fig)

    st.subheader("Emissions Table")
    st.dataframe(results["table"], use_container_width=True, hide_index=True)

    st.subheader("Narrative Explanation")
    st.write(results["narrative"])

    st.subheader("Recommendations")
    st.write(results["recommendation"])
