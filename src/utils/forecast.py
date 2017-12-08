"""A collection of forecasts, each for a different location."""

# first party
from .forecast_location import ForecastLocation
from .forecast_meta import Locations
from .forecast_type import ForecastType

class Forecast:

  @staticmethod
  def split(forecast):
    group_regional = Forecast(*forecast.get_metadata())
    group_states = Forecast(*forecast.get_metadata())
    for location in forecast.get_locations():
      fc = forecast.get_forecast(location)
      if Locations.is_region(location):
        group_regional.add_forecast(fc)
      else:
        group_states.add_forecast(fc)
    return group_regional, group_states

  @staticmethod
  def join(forecast1, forecast2):
    forecast = Forecast(*forecast1.get_metadata())
    for location in forecast1.get_locations():
      forecast.add_forecast(forecast1.get_forecast(location))
    for location in forecast2.get_locations():
      forecast.add_forecast(forecast2.get_forecast(location))
    return forecast

  def __init__(self, season, timestamp, team, epiweek, forecast_type = ForecastType.WILI):
    self.season = season
    self.timestamp = timestamp
    self.team = team
    self.epiweek = epiweek
    self.forecasts = {}
    self.ordered_locations = []
    self.season_length = 33
    self.ili_bin_size = 0.1

    self.num_ili_bins = 131
    if (forecast_type == ForecastType.HOSP):
        self.num_ili_bins = 601

  def get_metadata(self):
    return (self.season, self.timestamp, self.team, self.epiweek)

  def get_or_create_forecast(self, location):
    if location not in self.forecasts:
      self.add_forecast(
        ForecastLocation(location, self.season_length, self.num_ili_bins)
      )
    return self.get_forecast(location)

  def has_forecast(self, location):
    return location in self.forecasts

  def get_forecast(self, location):
    return self.forecasts[location]

  def get_locations(self):
    return self.ordered_locations

  def add_forecast(self, forecast):
    location = forecast.location
    self.forecasts[location] = forecast
    if location not in self.ordered_locations:
      self.ordered_locations.append(location)

  def sanity_check(self):
    for fc in self.forecasts.values():
      try:
        fc.sanity_check()
      except Exception as e:
        print('sanity check failed for location: %s' % fc.location)
        raise e

  def equals(self, other):
    # TODO: this needs to be implemented
    raise NotImplementedError()
