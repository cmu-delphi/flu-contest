"""Constants used in COVID-19 forecasting."""


# number of samples to draw, per user curve, to simulate effects of backfill
BACKFILL_MODEL_NUM_SAMPLES = 100

# blend all distributions with uniform to prevent zero probability. this is the
# blending weight. values are from 0 (no uniform component) to 1 (output will
# exactly uniform distribution).
UNIFORM_WEIGHT = 0.2

# the max week on the epicast user interface x-axis
MAX_EPIWEEK = 202040

# 2019-2020 season values from https://www.cdc.gov/flu/weekly/overview.htm
BASELINES = {
  'nat': 2.4,
  'hhs1': 1.9,
  'hhs2': 3.2,
  'hhs3': 1.9,
  'hhs4': 2.4,
  'hhs5': 1.9,
  'hhs6': 3.8,
  'hhs7': 1.7,
  'hhs8': 2.7,
  'hhs9': 2.4,
  'hhs10': 1.5,
}

# full/friendly/display names for location codes
# with help from https://github.com/cmu-delphi/delphi-epidata/blob/master/src/\
# acquisition/fluview/fluview_locations.py
LOCATION_NAMES = {
  'nat': 'US National',
  'hhs1': 'HHS Region 1',
  'hhs2': 'HHS Region 2',
  'hhs3': 'HHS Region 3',
  'hhs4': 'HHS Region 4',
  'hhs5': 'HHS Region 5',
  'hhs6': 'HHS Region 6',
  'hhs7': 'HHS Region 7',
  'hhs8': 'HHS Region 8',
  'hhs9': 'HHS Region 9',
  'hhs10': 'HHS Region 10',
  'al': 'alabama',
  'ak': 'alaska',
  'az': 'arizona',
  'ar': 'arkansas',
  'ca': 'california',
  'co': 'colorado',
  'ct': 'connecticut',
  'de': 'delaware',
  'fl': 'florida',
  'ga': 'georgia',
  'hi': 'hawaii',
  'id': 'idaho',
  'il': 'illinois',
  'in': 'indiana',
  'ia': 'iowa',
  'ks': 'kansas',
  'ky': 'kentucky',
  'la': 'louisiana',
  'me': 'maine',
  'md': 'maryland',
  'ma': 'massachusetts',
  'mi': 'michigan',
  'mn': 'minnesota',
  'ms': 'mississippi',
  'mo': 'missouri',
  'mt': 'montana',
  'ne': 'nebraska',
  'nv': 'nevada',
  'nh': 'new hampshire',
  'nj': 'new jersey',
  'nm': 'new mexico',
  'ny_minus_jfk': 'new york',
  'nc': 'north carolina',
  'nd': 'north dakota',
  'oh': 'ohio',
  'ok': 'oklahoma',
  'or': 'oregon',
  'pa': 'pennsylvania',
  'ri': 'rhode island',
  'sc': 'south carolina',
  'sd': 'south dakota',
  'tn': 'tennessee',
  'tx': 'texas',
  'ut': 'utah',
  'vt': 'vermont',
  'va': 'virginia',
  'wa': 'washington',
  'wv': 'west virginia',
  'wi': 'wisconsin',
  'wy': 'wyoming',
  'as': 'american samoa',
  'mp': 'commonwealth of the northern mariana islands',
  'dc': 'district of columbia',
  'gu': 'guam',
  'pr': 'puerto rico',
  'vi': 'virgin islands',
  'ord': 'chicago',
  'lax': 'los angeles',
  'jfk': 'new york city',
}

# targets for regions and states
COMMON_TARGETS = [
  'peak_week',
  'peak_wili',
  '1wk_wili',
  '2wk_wili',
  '3wk_wili',
  '4wk_wili',
  '5wk_wili',
  '6wk_wili',
]

# full/friendly/display names for targets
TARGET_NAMES = {
  'peak_week': 'Peak week',
  'peak_wili': 'Peak height',
  '1wk_wili': '1 wk ahead',
  '2wk_wili': '2 wk ahead',
  '3wk_wili': '3 wk ahead',
  '4wk_wili': '4 wk ahead',
  '5wk_wili': '5 wk ahead',
  '6wk_wili': '6 wk ahead',
  'offset_week': 'First week below baseline',
  'offset_happened': 'Below baseline for 3 weeks',
}
