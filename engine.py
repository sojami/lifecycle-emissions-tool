from dataclasses import dataclass
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import urlopen
import xml.etree.ElementTree as ET


REGION_DEFAULTS = {
    "global_average": {"grid_kg_per_kwh": 0.46, "fuel_kg_per_gallon": 8.89},
    "usa": {"grid_kg_per_kwh": 0.37, "fuel_kg_per_gallon": 8.89},
    "minnesota": {"grid_kg_per_kwh": 0.42, "fuel_kg_per_gallon": 8.89},
    "california": {"grid_kg_per_kwh": 0.19, "fuel_kg_per_gallon": 8.89},
    "texas": {"grid_kg_per_kwh": 0.43, "fuel_kg_per_gallon": 8.89},
    "new_york": {"grid_kg_per_kwh": 0.17, "fuel_kg_per_gallon": 8.89},
    "florida": {"grid_kg_per_kwh": 0.39, "fuel_kg_per_gallon": 8.89},
    "canada": {"grid_kg_per_kwh": 0.11, "fuel_kg_per_gallon": 8.89},
    "mexico": {"grid_kg_per_kwh": 0.43, "fuel_kg_per_gallon": 8.89},
    "uk": {"grid_kg_per_kwh": 0.12, "fuel_kg_per_gallon": 8.89},
    "germany": {"grid_kg_per_kwh": 0.38, "fuel_kg_per_gallon": 8.89},
    "france": {"grid_kg_per_kwh": 0.06, "fuel_kg_per_gallon": 8.89},
    "netherlands": {"grid_kg_per_kwh": 0.24, "fuel_kg_per_gallon": 8.89},
    "norway": {"grid_kg_per_kwh": 0.02, "fuel_kg_per_gallon": 8.89},
    "sweden": {"grid_kg_per_kwh": 0.03, "fuel_kg_per_gallon": 8.89},
    "spain": {"grid_kg_per_kwh": 0.16, "fuel_kg_per_gallon": 8.89},
    "italy": {"grid_kg_per_kwh": 0.29, "fuel_kg_per_gallon": 8.89},
    "nigeria": {"grid_kg_per_kwh": 0.46, "fuel_kg_per_gallon": 8.89},
    "south_africa": {"grid_kg_per_kwh": 0.70, "fuel_kg_per_gallon": 8.89},
    "kenya": {"grid_kg_per_kwh": 0.10, "fuel_kg_per_gallon": 8.89},
    "egypt": {"grid_kg_per_kwh": 0.44, "fuel_kg_per_gallon": 8.89},
    "china": {"grid_kg_per_kwh": 0.54, "fuel_kg_per_gallon": 8.89},
    "india": {"grid_kg_per_kwh": 0.70, "fuel_kg_per_gallon": 8.89},
    "japan": {"grid_kg_per_kwh": 0.43, "fuel_kg_per_gallon": 8.89},
    "south_korea": {"grid_kg_per_kwh": 0.41, "fuel_kg_per_gallon": 8.89},
    "indonesia": {"grid_kg_per_kwh": 0.67, "fuel_kg_per_gallon": 8.89},
    "saudi_arabia": {"grid_kg_per_kwh": 0.59, "fuel_kg_per_gallon": 8.89},
    "uae": {"grid_kg_per_kwh": 0.43, "fuel_kg_per_gallon": 8.89},
    "australia": {"grid_kg_per_kwh": 0.52, "fuel_kg_per_gallon": 8.89},
    "new_zealand": {"grid_kg_per_kwh": 0.09, "fuel_kg_per_gallon": 8.89},
    "eu_average": {"grid_kg_per_kwh": 0.23, "fuel_kg_per_gallon": 8.89},
}

REGION_ALIASES = {
    "us": "usa",
    "united_states": "usa",
    "united_states_of_america": "usa",
    "usa_average": "usa",
    "united_kingdom": "uk",
    "great_britain": "uk",
    "england": "uk",
    "korea": "south_korea",
    "south_korea": "south_korea",
    "uae": "uae",
    "united_arab_emirates": "uae",
    "eu": "eu_average",
    "european_union": "eu_average",
}


FALLBACK_VEHICLE_SPECS = {
    "sedan": {
        "ICE": {"fuel_economy_mpg": 30, "kwh_per_mile": None, "battery_kwh": None, "vehicle_mfg_kg": 6500},
        "HEV": {"fuel_economy_mpg": 50, "kwh_per_mile": None, "battery_kwh": 1.5, "vehicle_mfg_kg": 7000},
        "PHEV": {"fuel_economy_mpg": 40, "kwh_per_mile": 0.30, "battery_kwh": 12, "vehicle_mfg_kg": 7500},
        "BEV": {"fuel_economy_mpg": None, "kwh_per_mile": 0.27, "battery_kwh": 60, "vehicle_mfg_kg": 8000},
    },
    "compact_suv": {
        "ICE": {"fuel_economy_mpg": 26, "kwh_per_mile": None, "battery_kwh": None, "vehicle_mfg_kg": 7500},
        "HEV": {"fuel_economy_mpg": 38, "kwh_per_mile": None, "battery_kwh": 1.6, "vehicle_mfg_kg": 8000},
        "PHEV": {"fuel_economy_mpg": 35, "kwh_per_mile": 0.33, "battery_kwh": 14, "vehicle_mfg_kg": 8500},
        "BEV": {"fuel_economy_mpg": None, "kwh_per_mile": 0.30, "battery_kwh": 75, "vehicle_mfg_kg": 9000},
    },
    "midsize_suv": {
        "ICE": {"fuel_economy_mpg": 22, "kwh_per_mile": None, "battery_kwh": None, "vehicle_mfg_kg": 9000},
        "HEV": {"fuel_economy_mpg": 32, "kwh_per_mile": None, "battery_kwh": 1.8, "vehicle_mfg_kg": 9500},
        "PHEV": {"fuel_economy_mpg": 30, "kwh_per_mile": 0.38, "battery_kwh": 17, "vehicle_mfg_kg": 10000},
        "BEV": {"fuel_economy_mpg": None, "kwh_per_mile": 0.36, "battery_kwh": 90, "vehicle_mfg_kg": 11000},
    },
    "pickup": {
        "ICE": {"fuel_economy_mpg": 18, "kwh_per_mile": None, "battery_kwh": None, "vehicle_mfg_kg": 11000},
        "HEV": {"fuel_economy_mpg": 24, "kwh_per_mile": None, "battery_kwh": 2.0, "vehicle_mfg_kg": 12000},
        "PHEV": {"fuel_economy_mpg": 22, "kwh_per_mile": 0.45, "battery_kwh": 20, "vehicle_mfg_kg": 13000},
        "BEV": {"fuel_economy_mpg": None, "kwh_per_mile": 0.50, "battery_kwh": 130, "vehicle_mfg_kg": 15000},
    },
    "hatchback": {
        "ICE": {"fuel_economy_mpg": 32, "kwh_per_mile": None, "battery_kwh": None, "vehicle_mfg_kg": 6000},
        "HEV": {"fuel_economy_mpg": 52, "kwh_per_mile": None, "battery_kwh": 1.3, "vehicle_mfg_kg": 6500},
        "PHEV": {"fuel_economy_mpg": 42, "kwh_per_mile": 0.28, "battery_kwh": 10, "vehicle_mfg_kg": 7000},
        "BEV": {"fuel_economy_mpg": None, "kwh_per_mile": 0.25, "battery_kwh": 50, "vehicle_mfg_kg": 7500},
    },
}

AVERAGE_REFERENCE_SPEC_DB = {
    ("BEV", "sedan"): {"fuel_economy_mpg": None, "kwh_per_mile": 0.27, "battery_kwh": 60, "vehicle_mfg_kg": 8000},
    ("ICE", "sedan"): {"fuel_economy_mpg": 30, "kwh_per_mile": None, "battery_kwh": None, "vehicle_mfg_kg": 6500},
    ("BEV", "compact_suv"): {"fuel_economy_mpg": None, "kwh_per_mile": 0.30, "battery_kwh": 75, "vehicle_mfg_kg": 9000},
    ("ICE", "compact_suv"): {"fuel_economy_mpg": 26, "kwh_per_mile": None, "battery_kwh": None, "vehicle_mfg_kg": 7500},
    ("BEV", "midsize_suv"): {"fuel_economy_mpg": None, "kwh_per_mile": 0.36, "battery_kwh": 90, "vehicle_mfg_kg": 11000},
    ("ICE", "midsize_suv"): {"fuel_economy_mpg": 22, "kwh_per_mile": None, "battery_kwh": None, "vehicle_mfg_kg": 9000},
    ("BEV", "pickup"): {"fuel_economy_mpg": None, "kwh_per_mile": 0.50, "battery_kwh": 130, "vehicle_mfg_kg": 15000},
    ("ICE", "pickup"): {"fuel_economy_mpg": 18, "kwh_per_mile": None, "battery_kwh": None, "vehicle_mfg_kg": 11000},
    ("BEV", "hatchback"): {"fuel_economy_mpg": None, "kwh_per_mile": 0.25, "battery_kwh": 50, "vehicle_mfg_kg": 7500},
    ("ICE", "hatchback"): {"fuel_economy_mpg": 32, "kwh_per_mile": None, "battery_kwh": None, "vehicle_mfg_kg": 6000},
}

CURATED_VEHICLE_SPECS = {
    ("TESLA", "MODEL 3"): {
        2023: {
            "fuel_economy_mpg": None,
            "kwh_per_mile": 0.26,
            "battery_kwh": 75.0,
            "vehicle_mfg_kg": 8500.0,
            "vehicle_class": "sedan",
            "tech_type": "BEV",
        },
        2024: {
            "fuel_economy_mpg": None,
            "kwh_per_mile": 0.26,
            "battery_kwh": 75.0,
            "vehicle_mfg_kg": 8500.0,
            "vehicle_class": "sedan",
            "tech_type": "BEV",
        },
    },
    ("TESLA", "MODEL Y"): {
        2024: {
            "fuel_economy_mpg": None,
            "kwh_per_mile": 0.30,
            "battery_kwh": 81.0,
            "vehicle_mfg_kg": 9200.0,
            "vehicle_class": "midsize_suv",
            "tech_type": "BEV",
        },
    },
    ("TOYOTA", "PRIUS"): {
        2024: {
            "fuel_economy_mpg": 57.0,
            "kwh_per_mile": None,
            "battery_kwh": 1.3,
            "vehicle_mfg_kg": 7600.0,
            "vehicle_class": "hatchback",
            "tech_type": "HEV",
        },
    },
    ("TOYOTA", "RAV4"): {
        2024: {
            "fuel_economy_mpg": 30.0,
            "kwh_per_mile": None,
            "battery_kwh": None,
            "vehicle_mfg_kg": 7800.0,
            "vehicle_class": "compact_suv",
            "tech_type": "ICE",
        },
    },
    ("TOYOTA", "RAV4 HYBRID"): {
        2024: {
            "fuel_economy_mpg": 39.0,
            "kwh_per_mile": None,
            "battery_kwh": 1.6,
            "vehicle_mfg_kg": 8000.0,
            "vehicle_class": "compact_suv",
            "tech_type": "HEV",
        },
    },
    ("FORD", "F-150 LIGHTNING"): {
        2024: {
            "fuel_economy_mpg": None,
            "kwh_per_mile": 0.48,
            "battery_kwh": 131.0,
            "vehicle_mfg_kg": 15000.0,
            "vehicle_class": "pickup",
            "tech_type": "BEV",
        },
    },
}


@dataclass
class VehicleInputs:
    name: str
    tech_type: str
    vehicle_class: str
    lifetime_miles: float
    fuel_economy_mpg: float | None = None
    kwh_per_mile: float | None = None
    battery_kwh: float | None = None
    vehicle_mfg_kg: float | None = None
    battery_mfg_kg_per_kwh: float = 80.0


@dataclass
class RegionInputs:
    name: str
    grid_kg_per_kwh: float
    fuel_kg_per_gallon: float


@dataclass
class EmissionResult:
    upstream_kg: float
    downstream_kg: float
    total_kg: float
    per_mile_kg: float


def lookup_region_defaults(region_name: str) -> tuple[dict, bool]:
    if not region_name:
        return REGION_DEFAULTS["global_average"], True

    normalized_region = region_name.strip().lower().replace(" ", "_").replace("-", "_")
    normalized_region = REGION_ALIASES.get(normalized_region, normalized_region)

    region_data = REGION_DEFAULTS.get(normalized_region)
    if region_data is not None:
        return region_data, False
    return REGION_DEFAULTS["global_average"], True


def lookup_state_defaults(state_name: str) -> tuple[dict, bool]:
    if not state_name or state_name == "N/A":
        return lookup_region_defaults("usa_average")
    return lookup_region_defaults(state_name)


def compute_vehicle_emissions(vehicle: VehicleInputs, region: RegionInputs) -> EmissionResult:
    vehicle_mfg = vehicle.vehicle_mfg_kg or 0.0
    battery_mfg = 0.0
    if vehicle.battery_kwh is not None:
        battery_mfg = vehicle.battery_kwh * vehicle.battery_mfg_kg_per_kwh
    upstream = vehicle_mfg + battery_mfg

    fuel_use_kg = 0.0
    elec_use_kg = 0.0

    if vehicle.fuel_economy_mpg:
        gallons = vehicle.lifetime_miles / vehicle.fuel_economy_mpg
        fuel_use_kg = gallons * region.fuel_kg_per_gallon

    if vehicle.kwh_per_mile:
        kwh = vehicle.lifetime_miles * vehicle.kwh_per_mile
        elec_use_kg = kwh * region.grid_kg_per_kwh

    downstream = fuel_use_kg + elec_use_kg
    total = upstream + downstream
    per_mile = downstream / vehicle.lifetime_miles if vehicle.lifetime_miles > 0 else 0.0

    return EmissionResult(
        upstream_kg=upstream,
        downstream_kg=downstream,
        total_kg=total,
        per_mile_kg=per_mile,
    )


def breakeven_miles(a: EmissionResult, b: EmissionResult) -> float | None:
    num = a.upstream_kg - b.upstream_kg
    den = b.per_mile_kg - a.per_mile_kg
    if abs(den) < 1e-9:
        return None
    miles = num / den
    return miles if miles > 0 else None


def try_dynamic_lookup(
    make: str | None = None,
    model: str | None = None,
    year: int | None = None,
    vehicle_class: str | None = None,
    tech_type: str | None = None,
) -> dict | None:
    required_keys = {
        "fuel_economy_mpg",
        "kwh_per_mile",
        "battery_kwh",
        "vehicle_mfg_kg",
        "vehicle_class",
        "tech_type",
    }

    try:
        if make and model:
            provider_result = dynamic_provider_lookup(make, model, year)
            if provider_result and required_keys.issubset(provider_result.keys()):
                return {key: provider_result[key] for key in required_keys}

            curated_result = _lookup_curated_vehicle_specs(make, model, year)
            if curated_result:
                if vehicle_class and not curated_result.get("vehicle_class"):
                    curated_result["vehicle_class"] = vehicle_class.lower()
                if tech_type and not curated_result.get("tech_type"):
                    curated_result["tech_type"] = tech_type.upper()
                if required_keys.issubset(curated_result.keys()):
                    return {key: curated_result[key] for key in required_keys}

        if vehicle_class is not None and tech_type is not None:
            normalized_class = vehicle_class.lower()
            normalized_tech = tech_type.upper()
            reference_result = AVERAGE_REFERENCE_SPEC_DB.get((normalized_tech, normalized_class))
            if reference_result is not None:
                enriched = {
                    "vehicle_class": normalized_class,
                    "tech_type": normalized_tech,
                    **reference_result,
                }
                if required_keys.issubset(enriched.keys()):
                    return {key: enriched[key] for key in required_keys}

            fallback_result = fallback_table_lookup(normalized_class, normalized_tech)
            enriched = {
                "vehicle_class": normalized_class,
                "tech_type": normalized_tech,
                **fallback_result,
            }
            if required_keys.issubset(enriched.keys()):
                return {key: enriched[key] for key in required_keys}
    except Exception:
        return None

    return None


def dynamic_provider_lookup(make: str, model: str, year: int | None) -> dict | None:
    try:
        fuel_economy_record = _lookup_fuel_economy_vehicle(make, model, year)
        vehicle_class_value = None
        tech_type_value = None
        fuel_economy_mpg = None
        kwh_per_mile = None
        battery_kwh = None
        vehicle_mfg_kg = None

        if fuel_economy_record:
            vehicle_class_value = _normalize_vehicle_class(fuel_economy_record.get("VClass"))
            tech_type_value = _infer_tech_type(
                fuel_type=fuel_economy_record.get("fuelType1"),
                fuel_type_secondary=fuel_economy_record.get("fuelType2"),
                atv_type=fuel_economy_record.get("atvType"),
                phev_blended=fuel_economy_record.get("phevBlended"),
            )

            fuel_economy_mpg = _to_float(fuel_economy_record.get("comb08"))
            if fuel_economy_mpg is not None and fuel_economy_mpg <= 0:
                fuel_economy_mpg = None

            electric_consumption = _to_float(fuel_economy_record.get("combA08"))
            if electric_consumption is not None and electric_consumption > 0:
                kwh_per_mile = electric_consumption / 100.0

        specs = {
            "fuel_economy_mpg": fuel_economy_mpg,
            "kwh_per_mile": kwh_per_mile,
            "battery_kwh": battery_kwh,
            "vehicle_mfg_kg": vehicle_mfg_kg,
            "vehicle_class": vehicle_class_value,
            "tech_type": tech_type_value,
        }

        if any(specs[key] is None for key in specs):
            return None
        return specs
    except Exception:
        return None


def _lookup_curated_vehicle_specs(make: str, model: str, year: int | None) -> dict | None:
    normalized_make = make.strip().upper()
    normalized_model = model.strip().upper()
    candidates = CURATED_VEHICLE_SPECS.get((normalized_make, normalized_model))
    if not candidates:
        return None

    if year is not None and year in candidates:
        return candidates[year].copy()
    if year is not None:
        closest_year = min(candidates.keys(), key=lambda candidate_year: abs(candidate_year - year))
        return candidates[closest_year].copy()

    latest_year = max(candidates.keys())
    return candidates[latest_year].copy()


def _lookup_fuel_economy_vehicle(make: str, model: str, year: int | None) -> dict | None:
    if not make or not model:
        return None
    if year is None:
        return None

    base_url = "https://www.fueleconomy.gov/ws/rest/vehicle/menu/options"
    request_url = (
        f"{base_url}?year={quote(str(year))}&make={quote(make)}&model={quote(model)}"
    )
    options_xml = _fetch_xml(request_url)
    if options_xml is None:
        return None

    option_id = _extract_first_vehicle_id(options_xml)
    if option_id is None:
        return None

    vehicle_xml = _fetch_xml(f"https://www.fueleconomy.gov/ws/rest/vehicle/{option_id}")
    if vehicle_xml is None:
        return None
    return _xml_to_dict(vehicle_xml)


def _fetch_xml(url: str) -> ET.Element | None:
    response_text = _fetch_text(url)
    if response_text is None:
        return None
    try:
        return ET.fromstring(response_text)
    except ET.ParseError:
        return None


def _fetch_text(url: str) -> str | None:
    try:
        with urlopen(url, timeout=8) as response:
            return response.read().decode("utf-8")
    except (HTTPError, URLError, TimeoutError, ValueError):
        return None


def _extract_first_vehicle_id(root: ET.Element) -> str | None:
    for element in root.iter():
        if element.tag.endswith("value") and element.text and element.text.strip():
            return element.text.strip()
    return None


def _xml_to_dict(root: ET.Element) -> dict:
    data: dict[str, str] = {}
    for child in root:
        tag = child.tag.split("}")[-1]
        text = (child.text or "").strip()
        if text:
            data[tag] = text
    return data


def _to_float(value: object) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _normalize_vehicle_class(raw_value: str | None) -> str | None:
    if not raw_value:
        return None

    normalized = raw_value.lower()
    if "pickup" in normalized or "truck" in normalized:
        return "pickup"
    if "sport utility" in normalized or "small sport utility" in normalized or "small suv" in normalized:
        return "compact_suv"
    if "standard sport utility" in normalized or "midsize" in normalized or "utility vehicle" in normalized:
        return "midsize_suv"
    if "sedan" in normalized or "compact car" in normalized or "midsize car" in normalized or "large car" in normalized:
        return "sedan"
    if "hatchback" in normalized:
        return "hatchback"
    return None


def _infer_tech_type(
    fuel_type: str | None,
    fuel_type_secondary: str | None,
    atv_type: str | None,
    phev_blended: str | None,
) -> str | None:
    joined = " ".join(
        value.lower()
        for value in [fuel_type, fuel_type_secondary, atv_type, phev_blended]
        if value
    )
    if "plug-in hybrid" in joined or "phev" in joined:
        return "PHEV"
    if "hybrid" in joined:
        return "HEV"
    if "electric" in joined or "ev" in joined:
        return "BEV"
    if "gasoline" in joined or "regular" in joined or "diesel" in joined:
        return "ICE"
    return None


def fallback_table_lookup(vehicle_class: str, tech_type: str) -> dict:
    normalized_class = (vehicle_class or "").strip().lower()
    normalized_tech = (tech_type or "").strip().upper()

    class_aliases = {
        "suv": "compact_suv",
        "truck": "pickup",
        "van": "midsize_suv",
        "wagon": "sedan",
        "coupe": "sedan",
        "other": "sedan",
        "": "sedan",
    }
    tech_aliases = {
        "EV": "BEV",
        "": "ICE",
    }

    normalized_class = class_aliases.get(normalized_class, normalized_class)
    normalized_tech = tech_aliases.get(normalized_tech, normalized_tech)

    if normalized_class not in FALLBACK_VEHICLE_SPECS:
        normalized_class = "sedan"
    if normalized_tech not in FALLBACK_VEHICLE_SPECS[normalized_class]:
        normalized_tech = "ICE"

    return FALLBACK_VEHICLE_SPECS[normalized_class][normalized_tech].copy()


def build_reference_vehicle(user_vehicle: VehicleInputs, region: RegionInputs) -> VehicleInputs:
    vehicle_class = user_vehicle.vehicle_class.lower()
    reference_tech = {
        "ICE": "BEV",
        "BEV": "ICE",
        "HEV": "ICE",
        "PHEV": "ICE",
    }.get(user_vehicle.tech_type.upper(), "ICE")

    reference_name = f"Average {reference_tech} {vehicle_class}"

    # Try dynamic lookup first for the reference class/technology pair.
    specs = try_dynamic_lookup(
        make=None,
        model=None,
        year=None,
        vehicle_class=vehicle_class,
        tech_type=reference_tech,
    )

    # Fall back to internal defaults if dynamic lookup does not return data.
    if specs is None:
        specs = fallback_table_lookup(vehicle_class, reference_tech)

    return VehicleInputs(
        name=reference_name,
        tech_type=reference_tech,
        vehicle_class=vehicle_class,
        # Reference vehicle inherits user assumptions for study horizon and battery factor.
        lifetime_miles=user_vehicle.lifetime_miles,
        fuel_economy_mpg=specs.get("fuel_economy_mpg"),
        kwh_per_mile=specs.get("kwh_per_mile"),
        battery_kwh=specs.get("battery_kwh"),
        vehicle_mfg_kg=specs.get("vehicle_mfg_kg"),
        battery_mfg_kg_per_kwh=user_vehicle.battery_mfg_kg_per_kwh,
    )


def generate_narrative(
    car_a: VehicleInputs,
    car_b: VehicleInputs,
    res_a: EmissionResult,
    res_b: EmissionResult,
    breakeven: float | None,
    region: RegionInputs,
    used_default_flag: bool = False,
) -> str:
    lower_total_vehicle = car_a if res_a.total_kg <= res_b.total_kg else car_b
    higher_total_vehicle = car_b if lower_total_vehicle is car_a else car_a
    lower_total_result = res_a if lower_total_vehicle is car_a else res_b
    higher_total_result = res_b if lower_total_vehicle is car_a else res_a
    total_gap = abs(res_a.total_kg - res_b.total_kg)

    upstream_gap = abs(res_a.upstream_kg - res_b.upstream_kg)
    upstream_leader = car_a if res_a.upstream_kg <= res_b.upstream_kg else car_b
    downstream_gap = abs(res_a.downstream_kg - res_b.downstream_kg)
    downstream_leader = car_a if res_a.downstream_kg <= res_b.downstream_kg else car_b

    summary_paragraph = (
        f"In {region.name}, the lifecycle comparison indicates that {lower_total_vehicle.name} has the lower total "
        f"emissions footprint at {lower_total_result.total_kg:,.0f} kg CO2e, compared with "
        f"{higher_total_vehicle.name} at {higher_total_result.total_kg:,.0f} kg CO2e. "
        f"The overall difference between the two scenarios is {total_gap:,.0f} kg CO2e across "
        f"{car_a.lifetime_miles:,.0f} lifetime miles."
    )

    upstream_paragraph = (
        f"Upstream emissions are driven by base vehicle manufacturing plus any battery-related manufacturing burden. "
        f"{upstream_leader.name} has the lower upstream total, and the gap between the two vehicles is "
        f"{upstream_gap:,.0f} kg CO2e. Vehicles with larger batteries or higher manufacturing assumptions will "
        f"tend to start with a higher carbon burden even when they perform better in the use phase."
    )

    downstream_paragraph = (
        f"Downstream emissions reflect operational energy use over the full study period. "
        f"{downstream_leader.name} performs better in the use phase, with a downstream advantage of "
        f"{downstream_gap:,.0f} kg CO2e. This difference is shaped by each vehicle's fuel economy and electricity "
        f"consumption, along with the regional grid intensity of {region.grid_kg_per_kwh:.2f} kg CO2e/kWh and "
        f"fuel intensity of {region.fuel_kg_per_gallon:.2f} kg CO2e/gallon."
    )

    if breakeven is None:
        breakeven_paragraph = (
            "A breakeven point does not emerge under the current assumptions. This usually means that the vehicle "
            "with the higher manufacturing burden does not recover that disadvantage through lower per-mile "
            "operating emissions, or that both vehicles have operating profiles that are too similar for a crossover "
            "to occur within a meaningful mileage range."
        )
    else:
        breakeven_paragraph = (
            f"The breakeven analysis indicates that {car_b.name} overtakes {car_a.name} at approximately "
            f"{breakeven:,.0f} miles. Before that point, the higher upfront manufacturing burden remains dominant; "
            "after that point, lower operating emissions are sufficient to offset the initial disadvantage."
        )

    region_paragraph = (
        f"The regional context matters materially in this result. A grid intensity of {region.grid_kg_per_kwh:.2f} "
        f"kg CO2e/kWh increases the penalty for electricity consumption in dirtier grids and strengthens the case "
        f"for electric drivetrains in cleaner grids. Similarly, a fuel intensity of {region.fuel_kg_per_gallon:.2f} "
        f"kg CO2e/gallon directly affects combustion-based scenarios and can widen the lifecycle advantage of "
        f"lower-fuel or electrified options."
    )
    if used_default_flag:
        region_paragraph += (
            " Region-specific carbon intensity data was unavailable for this location, so global average values "
            "were used as a fallback for the regional comparison."
        )

    recommendation_paragraph = (
        f"Based on the modeled totals, the preferred option is {lower_total_vehicle.name} because it delivers the "
        f"lower lifecycle emissions outcome in this region. The next step would be to refine vehicle manufacturing, "
        "battery sourcing, and real-world energy-use assumptions if this comparison will support a high-stakes "
        "procurement or policy decision."
    )

    return "\n\n".join(
        [
            summary_paragraph,
            upstream_paragraph,
            downstream_paragraph,
            breakeven_paragraph,
            region_paragraph,
            recommendation_paragraph,
        ]
    )


def generate_recommendation(
    car_a: VehicleInputs,
    car_b: VehicleInputs,
    res_a: EmissionResult,
    res_b: EmissionResult,
    breakeven: float | None,
    region: RegionInputs,
    used_default_flag: bool = False,
) -> str:
    lower_vehicle = car_a if res_a.total_kg <= res_b.total_kg else car_b
    higher_vehicle = car_b if lower_vehicle is car_a else car_a
    lower_result = res_a if lower_vehicle is car_a else res_b
    higher_result = res_b if lower_vehicle is car_a else res_a

    total_gap = abs(higher_result.total_kg - lower_result.total_kg)
    gap_ratio = total_gap / higher_result.total_kg if higher_result.total_kg else 0.0

    sentences = []
    if gap_ratio <= 0.05:
        sentences.append(
            f"{car_a.name} and {car_b.name} are broadly comparable on total lifecycle emissions, with less than a 5% difference between them."
        )
    else:
        sentences.append(
            f"{lower_vehicle.name} has the lower modeled lifecycle footprint, outperforming {higher_vehicle.name} by about {total_gap:,.0f} kg CO2e."
        )

    if breakeven is None:
        sentences.append(f"{lower_vehicle.name} is the better lifecycle option from day one under the current assumptions.")
    elif breakeven < 20_000:
        sentences.append(
            f"The cleaner vehicle overtakes quickly, with breakeven occurring at roughly {breakeven:,.0f} miles."
        )
    elif breakeven > car_a.lifetime_miles:
        sentences.append(
            f"The breakeven point would occur beyond the assumed lifetime of {car_a.lifetime_miles:,.0f} miles, so it does not fully overtake within the study horizon."
        )
    else:
        sentences.append(f"The lifecycle crossover occurs at approximately {breakeven:,.0f} miles.")

    if region.grid_kg_per_kwh <= 0.2:
        sentences.append(
            f"The relatively clean grid in {region.name} at {region.grid_kg_per_kwh:.2f} kg CO2e/kWh strengthens the case for electric driving."
        )
    elif region.grid_kg_per_kwh >= 0.5:
        sentences.append(
            f"The relatively carbon-intensive grid in {region.name} at {region.grid_kg_per_kwh:.2f} kg CO2e/kWh reduces, but does not eliminate, the advantage of electric operation."
        )
    else:
        sentences.append(
            f"With a grid intensity of {region.grid_kg_per_kwh:.2f} kg CO2e/kWh in {region.name}, operational emissions remain an important part of the comparison."
        )
    if used_default_flag:
        sentences.append("Region-specific grid data was unavailable, so this comparison uses global average regional assumptions.")

    sentences.append(f"Overall, based on lifecycle emissions, {lower_vehicle.name} is the lower-carbon choice.")
    return " ".join(sentences)
