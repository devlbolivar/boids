from app.campaigns.schemas import ICPConfig
from app.integrations.apollo.icp_mapper import icp_to_apollo_filters


def test_icp_with_titles_maps_correctly():
    icp = ICPConfig(titles=["CTO", "VP Engineering"])
    filters = icp_to_apollo_filters(icp)
    assert filters["person_titles"] == ["CTO", "VP Engineering"]


def test_icp_with_locations_maps_correctly():
    icp = ICPConfig(locations=["Chile", "Colombia"])
    filters = icp_to_apollo_filters(icp)
    assert filters["person_locations"] == ["Chile", "Colombia"]


def test_icp_empty_fields_not_in_filters():
    icp = ICPConfig(titles=["CTO"])
    filters = icp_to_apollo_filters(icp)
    assert "person_locations" not in filters
    assert "q_keywords" not in filters
    assert "organization_industry_tag_ids" not in filters


def test_company_size_range_mapping():
    icp = ICPConfig(company_sizes=["51-200"])
    filters = icp_to_apollo_filters(icp)
    assert "organization_num_employees_ranges" in filters
    assert "51" in filters["organization_num_employees_ranges"][0]
    assert "200" in filters["organization_num_employees_ranges"][0]


def test_multiple_company_sizes_use_widest_range():
    icp = ICPConfig(company_sizes=["11-50", "51-200"])
    filters = icp_to_apollo_filters(icp)
    range_str = filters["organization_num_employees_ranges"][0]
    assert range_str.startswith("11,")
    assert range_str.endswith(",200") or "200" in range_str


def test_company_size_500_plus_uses_large_upper_bound():
    icp = ICPConfig(company_sizes=["500+"])
    filters = icp_to_apollo_filters(icp)
    assert "999999" in filters["organization_num_employees_ranges"][0]


def test_keywords_joined_as_string():
    icp = ICPConfig(keywords=["AWS", "Python", "React"])
    filters = icp_to_apollo_filters(icp)
    assert filters["q_keywords"] == "AWS Python React"


def test_industries_mapped():
    icp = ICPConfig(industries=["SaaS", "Fintech"])
    filters = icp_to_apollo_filters(icp)
    assert filters["organization_industry_tag_ids"] == ["SaaS", "Fintech"]


def test_empty_icp_returns_empty_filters():
    icp = ICPConfig()
    filters = icp_to_apollo_filters(icp)
    assert filters == {}
