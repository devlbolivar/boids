from app.campaigns.schemas import ICPConfig

COMPANY_SIZE_MAP = {
    "1-10":    {"min": 1,   "max": 10},
    "11-50":   {"min": 11,  "max": 50},
    "51-200":  {"min": 51,  "max": 200},
    "201-500": {"min": 201, "max": 500},
    "500+":    {"min": 501, "max": None},
}


def icp_to_apollo_filters(icp: ICPConfig) -> dict:
    """Convierte un ICPConfig a los filtros de Apollo API."""
    filters: dict = {}

    if icp.titles:
        filters["person_titles"] = icp.titles

    if icp.industries:
        filters["organization_industry_tag_ids"] = icp.industries

    if icp.locations:
        filters["person_locations"] = icp.locations

    if icp.company_sizes:
        min_vals = []
        max_vals = []
        for size in icp.company_sizes:
            if size in COMPANY_SIZE_MAP:
                min_vals.append(COMPANY_SIZE_MAP[size]["min"])
                if COMPANY_SIZE_MAP[size]["max"]:
                    max_vals.append(COMPANY_SIZE_MAP[size]["max"])

        if min_vals:
            upper = max(max_vals) if max_vals else 999999
            filters["organization_num_employees_ranges"] = [f"{min(min_vals)},{upper}"]

    if icp.keywords:
        filters["q_keywords"] = " ".join(icp.keywords)

    return filters
