import re
from dataclasses import dataclass

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import streamlit as st
from engine import REGION_DEFAULTS, EmissionResult, RegionInputs, VehicleInputs, breakeven_miles, build_reference_vehicle, compute_vehicle_emissions, generate_narrative, generate_recommendation, lookup_region_defaults


st.set_page_config(
    page_title="Lifecycle Emissions Analyzer",
    page_icon=":car:",
    layout="wide",
    initial_sidebar_state="expanded",
)


TECH_OPTIONS = ["ICE", "HEV", "PHEV", "BEV"]
CLASS_OPTIONS = ["sedan", "compact_suv", "midsize_suv", "hatchback", "pickup", "van", "wagon", "coupe", "other"]

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

FALLBACK_VEHICLE_SPECS = {
    "sedan": {
        "ICE": {
            "fuel_economy_mpg": 30,
            "kwh_per_mile": None,
            "battery_kwh": None,
            "vehicle_mfg_kg": 6500,
        },
        "HEV": {
            "fuel_economy_mpg": 50,
            "kwh_per_mile": None,
            "battery_kwh": 1.5,
            "vehicle_mfg_kg": 7000,
        },
        "PHEV": {
            "fuel_economy_mpg": 40,
            "kwh_per_mile": 0.30,
            "battery_kwh": 12,
            "vehicle_mfg_kg": 7500,
        },
        "BEV": {
            "fuel_economy_mpg": None,
            "kwh_per_mile": 0.27,
            "battery_kwh": 60,
            "vehicle_mfg_kg": 8000,
        },
    },
    "compact_suv": {
        "ICE": {
            "fuel_economy_mpg": 26,
            "kwh_per_mile": None,
            "battery_kwh": None,
            "vehicle_mfg_kg": 7500,
        },
        "HEV": {
            "fuel_economy_mpg": 38,
            "kwh_per_mile": None,
            "battery_kwh": 1.6,
            "vehicle_mfg_kg": 8000,
        },
        "PHEV": {
            "fuel_economy_mpg": 35,
            "kwh_per_mile": 0.33,
            "battery_kwh": 14,
            "vehicle_mfg_kg": 8500,
        },
        "BEV": {
            "fuel_economy_mpg": None,
            "kwh_per_mile": 0.30,
            "battery_kwh": 75,
            "vehicle_mfg_kg": 9000,
        },
    },
    "midsize_suv": {
        "ICE": {
            "fuel_economy_mpg": 22,
            "kwh_per_mile": None,
            "battery_kwh": None,
            "vehicle_mfg_kg": 9000,
        },
        "HEV": {
            "fuel_economy_mpg": 32,
            "kwh_per_mile": None,
            "battery_kwh": 1.8,
            "vehicle_mfg_kg": 9500,
        },
        "PHEV": {
            "fuel_economy_mpg": 30,
            "kwh_per_mile": 0.38,
            "battery_kwh": 17,
            "vehicle_mfg_kg": 10000,
        },
        "BEV": {
            "fuel_economy_mpg": None,
            "kwh_per_mile": 0.36,
            "battery_kwh": 90,
            "vehicle_mfg_kg": 11000,
        },
    },
    "pickup": {
        "ICE": {
            "fuel_economy_mpg": 18,
            "kwh_per_mile": None,
            "battery_kwh": None,
            "vehicle_mfg_kg": 11000,
        },
        "HEV": {
            "fuel_economy_mpg": 24,
            "kwh_per_mile": None,
            "battery_kwh": 2.0,
            "vehicle_mfg_kg": 12000,
        },
        "PHEV": {
            "fuel_economy_mpg": 22,
            "kwh_per_mile": 0.45,
            "battery_kwh": 20,
            "vehicle_mfg_kg": 13000,
        },
        "BEV": {
            "fuel_economy_mpg": None,
            "kwh_per_mile": 0.50,
            "battery_kwh": 130,
            "vehicle_mfg_kg": 15000,
        },
    },
    "hatchback": {
        "ICE": {
            "fuel_economy_mpg": 32,
            "kwh_per_mile": None,
            "battery_kwh": None,
            "vehicle_mfg_kg": 6000,
        },
        "HEV": {
            "fuel_economy_mpg": 52,
            "kwh_per_mile": None,
            "battery_kwh": 1.3,
            "vehicle_mfg_kg": 6500,
        },
        "PHEV": {
            "fuel_economy_mpg": 42,
            "kwh_per_mile": 0.28,
            "battery_kwh": 10,
            "vehicle_mfg_kg": 7000,
        },
        "BEV": {
            "fuel_economy_mpg": None,
            "kwh_per_mile": 0.25,
            "battery_kwh": 50,
            "vehicle_mfg_kg": 7500,
        },
    },
}

VEHICLE_SPEC_DB = {
    ("Tesla", "Model 3", 2024): {
        "vehicle_class": "sedan",
        "tech_type": "BEV",
        "fuel_economy_mpg": None,
        "kwh_per_mile": 0.26,
        "battery_kwh": 75.0,
        "vehicle_mfg_kg": 8500.0,
    },
    ("Toyota", "Prius", 2024): {
        "vehicle_class": "hatchback",
        "tech_type": "HEV",
        "fuel_economy_mpg": 57.0,
        "kwh_per_mile": None,
        "battery_kwh": 1.3,
        "vehicle_mfg_kg": 7600.0,
    },
    ("Toyota", "Rav4", 2024): {
        "vehicle_class": "suv",
        "tech_type": "ICE",
        "fuel_economy_mpg": 30.0,
        "kwh_per_mile": None,
        "battery_kwh": None,
        "vehicle_mfg_kg": 7800.0,
    },
    ("Toyota", "Rav4 Hybrid", 2024): {
        "vehicle_class": "suv",
        "tech_type": "HEV",
        "fuel_economy_mpg": 39.0,
        "kwh_per_mile": None,
        "battery_kwh": 1.6,
        "vehicle_mfg_kg": 8000.0,
    },
}

AVERAGE_REFERENCE_SPEC_DB = {
    ("BEV", "sedan"): {
        "fuel_economy_mpg": None,
        "kwh_per_mile": 0.27,
        "battery_kwh": 60,
        "vehicle_mfg_kg": 8000,
    },
    ("ICE", "sedan"): {
        "fuel_economy_mpg": 30,
        "kwh_per_mile": None,
        "battery_kwh": None,
        "vehicle_mfg_kg": 6500,
    },
    ("BEV", "compact_suv"): {
        "fuel_economy_mpg": None,
        "kwh_per_mile": 0.30,
        "battery_kwh": 75,
        "vehicle_mfg_kg": 9000,
    },
    ("ICE", "compact_suv"): {
        "fuel_economy_mpg": 26,
        "kwh_per_mile": None,
        "battery_kwh": None,
        "vehicle_mfg_kg": 7500,
    },
    ("BEV", "midsize_suv"): {
        "fuel_economy_mpg": None,
        "kwh_per_mile": 0.36,
        "battery_kwh": 90,
        "vehicle_mfg_kg": 11000,
    },
    ("ICE", "midsize_suv"): {
        "fuel_economy_mpg": 22,
        "kwh_per_mile": None,
        "battery_kwh": None,
        "vehicle_mfg_kg": 9000,
    },
    ("BEV", "pickup"): {
        "fuel_economy_mpg": None,
        "kwh_per_mile": 0.50,
        "battery_kwh": 130,
        "vehicle_mfg_kg": 15000,
    },
    ("ICE", "pickup"): {
        "fuel_economy_mpg": 18,
        "kwh_per_mile": None,
        "battery_kwh": None,
        "vehicle_mfg_kg": 11000,
    },
    ("BEV", "hatchback"): {
        "fuel_economy_mpg": None,
        "kwh_per_mile": 0.25,
        "battery_kwh": 50,
        "vehicle_mfg_kg": 7500,
    },
    ("ICE", "hatchback"): {
        "fuel_economy_mpg": 32,
        "kwh_per_mile": None,
        "battery_kwh": None,
        "vehicle_mfg_kg": 6000,
    },
}


@dataclass
class VehicleFormState:
    make: str = ""
    model: str = ""
    year: int | None = None
    tech_type: str = "ICE"
    vehicle_class: str = "other"

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


def parse_vehicle_from_text(text: str) -> VehicleFormState:
    cleaned = text.strip()
    if not cleaned:
        return VehicleFormState()

    year_match = re.search(r"\b(19|20)\d{2}\b", cleaned)
    year = int(year_match.group()) if year_match else None
    remainder = cleaned.replace(str(year), "").strip() if year else cleaned

    tokens = [token for token in re.split(r"\s+", remainder) if token]
    make = tokens[0].title() if tokens else ""
    model = " ".join(tokens[1:]).title() if len(tokens) > 1 else ""

    return VehicleFormState(
        make=make,
        model=model,
        year=year,
        tech_type=detect_tech(cleaned),
        vehicle_class=detect_vehicle_class(cleaned),
    )


def resolve_vehicle_class(user_vehicle_class: str | None, model: str | None) -> str:
    normalized_class = (user_vehicle_class or "").lower().strip()
    if normalized_class in FALLBACK_VEHICLE_SPECS:
        return normalized_class

    inferred_class = detect_vehicle_class(model or "")
    if inferred_class in FALLBACK_VEHICLE_SPECS:
        return inferred_class

    return "sedan"


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


def try_dynamic_lookup(make: str, model: str, year: int | None) -> dict | None:
    if not make or not model or year is None:
        return None
    normalized_key = (make.strip().title(), model.strip().title(), year)
    return VEHICLE_SPEC_DB.get(normalized_key)


def try_dynamic_reference_lookup(
    vehicle_class: str,
    tech_type: str,
) -> dict | None:
    normalized_class = vehicle_class.lower()
    normalized_tech = tech_type.upper()
    query = f"average {normalized_tech} {normalized_class}"
    return lookup_average_reference_specs(query)


def lookup_average_reference_specs(query: str) -> dict | None:
    normalized_query = query.strip().lower().replace("-", "_")
    for (tech_type, vehicle_class), data in AVERAGE_REFERENCE_SPEC_DB.items():
        expected_query = f"average {tech_type.lower()} {vehicle_class}"
        if normalized_query == expected_query:
            return {
                "tech_type": tech_type,
                "vehicle_class": vehicle_class,
                **data,
            }
    return None


def fallback_table_lookup(vehicle_class: str, tech_type: str) -> dict:
    vehicle_class = vehicle_class.lower()
    tech_type = tech_type.upper()

    if vehicle_class not in FALLBACK_VEHICLE_SPECS:
        raise ValueError(f"Unknown vehicle class: {vehicle_class}")

    if tech_type not in FALLBACK_VEHICLE_SPECS[vehicle_class]:
        raise ValueError(f"Unknown tech type: {tech_type}")

    return FALLBACK_VEHICLE_SPECS[vehicle_class][tech_type]


def get_vehicle_specs(make: str, model: str, year: int | None, vehicle_class: str, tech_type: str) -> dict:
    # 1. Try dynamic lookup (Codex-assisted)
    data = try_dynamic_lookup(make, model, year)
    if data is not None:
        return data

    # 2. Fallback to internal tables
    return fallback_table_lookup(vehicle_class, tech_type)


def opposite_technology_type(tech_type: str) -> str:
    opposites = {
        "ICE": "BEV",
        "BEV": "ICE",
        "HEV": "ICE",
        "PHEV": "ICE",
    }
    return opposites.get(tech_type.upper(), "BEV")


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
    natural_text = st.text_input(
        f"{title} quick entry",
        key=f"{prefix}_natural_text",
        placeholder="Example: 2024 Tesla Model 3 or 2022 Toyota RAV4 Hybrid",
        help="Type naturally here, then fine-tune the structured fields below.",
    )

    parsed_vehicle = parse_vehicle_from_text(natural_text)
    make = st.text_input("Make", key=f"{prefix}_make", value=parsed_vehicle.make)
    model = st.text_input("Model", key=f"{prefix}_model", value=parsed_vehicle.model)

    include_year = st.checkbox("Include year", key=f"{prefix}_include_year", value=parsed_vehicle.year is not None)
    year = None
    if include_year:
        year = int(
            st.number_input(
                "Year",
                min_value=1990,
                max_value=2035,
                step=1,
                key=f"{prefix}_year",
                value=parsed_vehicle.year or 2024,
            )
        )

    tech_type = st.selectbox(
        "Technology Type",
        TECH_OPTIONS,
        index=TECH_OPTIONS.index(parsed_vehicle.tech_type),
        key=f"{prefix}_tech_type",
        help="Auto-detected from quick entry but fully editable.",
    )
    vehicle_class = st.selectbox(
        "Vehicle Class",
        CLASS_OPTIONS,
        index=CLASS_OPTIONS.index(parsed_vehicle.vehicle_class if parsed_vehicle.vehicle_class in CLASS_OPTIONS else "other"),
        key=f"{prefix}_vehicle_class",
        help="Auto-detected from quick entry when possible.",
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
        "fuel_economy_mpg": specs.get("fuel_economy_mpg"),
        "kwh_per_mile": specs.get("kwh_per_mile"),
        "battery_kwh": specs.get("battery_kwh"),
        "vehicle_mfg_kg": specs.get("vehicle_mfg_kg"),
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
