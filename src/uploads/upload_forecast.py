"""
===============
=== Purpose ===
===============

Takes uploaded DELPHI flu contest forecasts, and puts them in the database.
This makes them available through the Epidata API via method `delphi`.

See also:
 - upload_forecast.php
 - submission_loader.py


=======================
=== Data Dictionary ===
=======================

`forecast_uploads` is a queue of uploaded forecast files that need to be parsed
and inserted into the database. See submission_loader.py for storage details of
forecast data.
+----------+-------------+------+-----+---------+----------------+
| Field    | Type        | Null | Key | Default | Extra          |
+----------+-------------+------+-----+---------+----------------+
| id       | int(11)     | NO   | PRI | NULL    | auto_increment |
| hmac     | char(64)    | NO   | UNI | NULL    |                |
| uploaded | datetime    | NO   | MUL | NULL    |                |
| name     | varchar(64) | NO   |     | NULL    |                |
| status   | int(11)     | NO   |     | NULL    |                |
| message  | text        | NO   |     | NULL    |                |
+----------+-------------+------+-----+---------+----------------+
id: unique identifier for each record
hmac: HMAC-SHA256 used for authentication and integrity checks
uploaded: date and time of file upload
name: the original file name
status: a numeric indicator of success or failure. known values are:
  0: file received and hmac verified; queued for insertion
  1: success
  -1, -2: error
message: an HTML string to be displayed on the website (see
  upload_forecast.php)

Note that there is a uniqueness constraint on `hmac` to prevent accidental
uploading of identical files.


=================
=== Changelog ===
=================

2016-12-01
  + first version
"""

# built-in
import os.path
# external
import mysql.connector
# local
import secrets
import submission_loader


def handle_upload(filename):
  try:
    submission_loader.load_submission(filename, verbose=True)
  except Exception as ex:
    return 'failed to upload submission (%s)' % str(ex), -1
  return 'looks ok', 1


def main():
  # connect to the database
  u, p = secrets.db.auto
  cnx = mysql.connector.connect(user=u, password=p, database='utils')
  cur = cnx.cursor()

  # get all pending uploads
  cur.execute('''
    SELECT
      `id`, `name`
    FROM
      `forecast_uploads`
    WHERE
      `status` = 0
    ''')
  for (row_id, name) in cur:
    # get the path to the forecast file
    filename = os.path.join('/common/forecast_uploads', name)
    # attempt to upload
    print('uploading', filename)
    try:
      message, status = handle_upload(filename)
    except Exception as ex:
      print(ex)
      message, status = 'exception: ' + str(ex), -2
    # store the result
    print(status, message)
    args = (status, message, row_id)
    cur.execute('''
      UPDATE
        `forecast_uploads`
      SET
        `status` = %s, `message` = %s
      WHERE
        `id` = %s
    ''', args)

  # cleanup
  cur.close()
  cnx.commit()
  cnx.close()


if __name__ == '__main__':
  main()
