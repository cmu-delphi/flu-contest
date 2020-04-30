"""
A utility class that handles database operations related to the 2020 COVID-19
adaptation of epicast.
"""

# third party
import mysql.connector

# first party
import delphi.operations.secrets as secrets


class Database:
  """A collection of epicast database operations."""

  DATABASE_NAME = 'epicast2'

  def connect(self, connector_impl=mysql.connector):
    """Establish a connection to the database."""

    u, p = secrets.db.epi
    self._connection = connector_impl.connect(
        host=secrets.db.host,
        user=u,
        password=p,
        database=Database.DATABASE_NAME)
    self._cursor = self._connection.cursor()

  def disconnect(self, commit):
    """Close the database connection.

    commit: if true, commit changes, otherwise rollback
    """

    self._cursor.close()
    if commit:
      self._connection.commit()
    self._connection.close()

  def get_user_predictions(self, epiweek):
    """Return all user predictions submitted on the given epiweek.

    The result is a set of wILI time-series for each location and user.

    Each row is a tuple of (`fluview_name`, `user_id`, `epiweek`, `wili`),
    where:

    - `fluview_name`: name of the location being predicted
    - `user_id`: unique identifier for the user
    - `epiweek`: the x-axis value of the time-series
    - `wili`: the y-axis value of the time-series
    """

    sql = '''
      SELECT
        lower(r.`fluview_name`), u.`id` `user_id`, f.`epiweek`, f.`wili`
      FROM (
        SELECT
          u.*
        FROM
          `ec_fluv_users` u
        JOIN
          `ec_fluv_defaults` d
        ON TRUE
        LEFT JOIN
          `ec_fluv_user_preferences` p
        ON
          p.`user_id` = u.`id` AND
          p.`name` = d.`name`
        WHERE
          d.`name` = '_debug' AND
          coalesce(p.`value`, d.`value`) = '0'
      ) u
      JOIN
        `ec_fluv_submissions` s
      ON
        s.`user_id` = u.`id`
      JOIN
        `ec_fluv_forecast` f
      ON
        f.`user_id` = u.`id` AND
        f.`region_id` = s.`region_id` AND
        f.`epiweek_now` = s.`epiweek_now`
      JOIN
        `ec_fluv_regions` r
      ON
        r.`id` = s.`region_id`
      WHERE
        s.`epiweek_now` = %s AND
        f.`epiweek` <= 202040 AND
        f.`wili` > 0
      ORDER BY
        r.`fluview_name` ASC,
        u.`id` ASC,
        f.`epiweek` ASC
    '''

    self._cursor.execute(sql, (epiweek,))

    return list(self._cursor)
