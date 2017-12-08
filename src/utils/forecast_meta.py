"""Forecast metadata."""


class Locations:

  __is_region = {}
  __delphi_to_display = {}
  __display_to_delphi = {}

  for is_region, delphi_name, display_name in (
    # regions
    (True, 'nat', 'US National'),
    (True, 'hhs1', 'HHS Region 1'),
    (True, 'hhs2', 'HHS Region 2'),
    (True, 'hhs3', 'HHS Region 3'),
    (True, 'hhs4', 'HHS Region 4'),
    (True, 'hhs5', 'HHS Region 5'),
    (True, 'hhs6', 'HHS Region 6'),
    (True, 'hhs7', 'HHS Region 7'),
    (True, 'hhs8', 'HHS Region 8'),
    (True, 'hhs9', 'HHS Region 9'),
    (True, 'hhs10', 'HHS Region 10'),
    (True, 'cen1', 'New England'),
    (True, 'cen2', 'Mid-Atlantic'),
    (True, 'cen3', 'East North Central'),
    (True, 'cen4', 'West North Central'),
    (True, 'cen5', 'South Atlantic'),
    (True, 'cen6', 'East South Central'),
    (True, 'cen7', 'West South Central'),
    (True, 'cen8', 'Mountain'),
    (True, 'cen9', 'Pacific'),
    # states (ISO 3166)
    (False, 'al', 'Alabama'),
    (False, 'ak', 'Alaska'),
    (False, 'az', 'Arizona'),
    (False, 'ar', 'Arkansas'),
    (False, 'ca', 'California'),
    (False, 'co', 'Colorado'),
    (False, 'ct', 'Connecticut'),
    (False, 'de', 'Delaware'),
    (False, 'fl', 'Florida'),
    (False, 'ga', 'Georgia'),
    (False, 'hi', 'Hawaii'),
    (False, 'id', 'Idaho'),
    (False, 'il', 'Illinois'),
    (False, 'in', 'Indiana'),
    (False, 'ia', 'Iowa'),
    (False, 'ks', 'Kansas'),
    (False, 'ky', 'Kentucky'),
    (False, 'la', 'Louisiana'),
    (False, 'me', 'Maine'),
    (False, 'md', 'Maryland'),
    (False, 'ma', 'Massachusetts'),
    (False, 'mi', 'Michigan'),
    (False, 'mn', 'Minnesota'),
    (False, 'ms', 'Mississippi'),
    (False, 'mo', 'Missouri'),
    (False, 'mt', 'Montana'),
    (False, 'ne', 'Nebraska'),
    (False, 'nv', 'Nevada'),
    (False, 'nh', 'New Hampshire'),
    (False, 'nj', 'New Jersey'),
    (False, 'nm', 'New Mexico'),
    (False, 'ny', 'New York'),
    (False, 'nc', 'North Carolina'),
    (False, 'nd', 'North Dakota'),
    (False, 'oh', 'Ohio'),
    (False, 'ok', 'Oklahoma'),
    (False, 'or', 'Oregon'),
    (False, 'pa', 'Pennsylvania'),
    (False, 'ri', 'Rhode Island'),
    (False, 'sc', 'South Carolina'),
    (False, 'sd', 'South Dakota'),
    (False, 'tn', 'Tennessee'),
    (False, 'tx', 'Texas'),
    (False, 'ut', 'Utah'),
    (False, 'vt', 'Vermont'),
    (False, 'va', 'Virginia'),
    (False, 'wa', 'Washington'),
    (False, 'wv', 'West Virginia'),
    (False, 'wi', 'Wisconsin'),
    (False, 'wy', 'Wyoming'),
    # territories (ISO 3166)
    (False, 'as', 'American Samoa'),
    (False, 'mp', 'Commonwealth of the Northern Mariana Islands'),
    (False, 'dc', 'District of Columbia'),
    (False, 'gu', 'Guam'),
    (False, 'pr', 'Puerto Rico'),
    (False, 'vi', 'Virgin Islands'),
    # cities (IATA airport code)
    (False, 'ord', 'Chicago'),
    (False, 'lax', 'Los Angeles'),
    (False, 'jfk', 'New York City'),
    # age groups (hospitalization forecast)
    (False, 'rate_age_0', '0-4 yr'),
    (False, 'rate_age_1', '5-17 yr'),
    (False, 'rate_age_2', '18-49 yr'),
    (False, 'rate_age_3', '50-64 yr'),
    (False, 'rate_age_4', '65 + yr'),
    (False, 'rate_overall', 'Overall'),
  ):
    __is_region[delphi_name] = __is_region[display_name] = is_region
    __delphi_to_display[delphi_name] = display_name
    __display_to_delphi[display_name] = delphi_name

  @staticmethod
  def is_region(name):
    return Locations.__is_region[name]

  @staticmethod
  def get_display_name(delphi_name):
    return Locations.__delphi_to_display[delphi_name]

  @staticmethod
  def get_delphi_name(display_name):
    return Locations.__display_to_delphi[display_name]


class Targets:

  __is_ili = {}
  __delphi_to_display = {}
  __display_to_delphi = {}

  for is_ili, delphi_name, display_name in (
    (False, 'onset', 'Season onset'),
    (False, 'peakweek', 'Season peak week'),
    (True, 'peak', 'Season peak percentage'),
    (True, 'x1', '1 wk ahead'),
    (True, 'x2', '2 wk ahead'),
    (True, 'x3', '3 wk ahead'),
    (True, 'x4', '4 wk ahead'),
  ):
    __is_ili[delphi_name] = is_ili
    __delphi_to_display[delphi_name] = display_name
    __display_to_delphi[display_name] = delphi_name

  @staticmethod
  def is_ili(name):
    return Targets.__is_ili[name]

  @staticmethod
  def get_display_name(delphi_name):
    return Targets.__delphi_to_display[delphi_name]

  @staticmethod
  def get_delphi_name(display_name):
    return Targets.__display_to_delphi[display_name]


class Types:

  __delphi_to_display = {}
  __display_to_delphi = {}

  for delphi_name, display_name in (
    ('dist', 'Bin'),
    ('point', 'Point'),
  ):
    __delphi_to_display[delphi_name] = display_name
    __display_to_delphi[display_name] = delphi_name

  @staticmethod
  def get_display_name(delphi_name):
    return Types.__delphi_to_display[delphi_name]

  @staticmethod
  def get_delphi_name(display_name):
    return Types.__display_to_delphi[display_name]
