<!doctype html>
<?php

/*
A website for DELPHI members to upload flu contest forecast files. Uploaded
forecasts will eventually be inserted into the database and be made available
though the Epidata API.

See upload_forecast.py for many more details.
*/

require_once('/var/www/html/secrets.php');
$hmacSecret = Secrets::$flucontest['hmac'];
$dbUser = Secrets::$db['auto'][0];
$dbPass = Secrets::$db['auto'][1];
$dbHost = 'localhost';
$dbPort = 3306;
$dbName = 'utils';
$dbh = mysql_connect("{$dbHost}:{$dbPort}", $dbUser, $dbPass);
if($dbh) {
   mysql_select_db($dbName, $dbh);
}
?>
<html>
  <head>
    <title>Forecast Uploader</title>
    <style>
      th, td {
        padding: 8px;
      }
      .error {
        color: #f00;
      }
    </style>
  </head>
  <body>
    <?php
    if(!$dbh) {
      ?>
      <h3 class="error">no database connection :(</h3><hr>
      <?php
    }
    if(isset($_FILES['file']) && isset($_REQUEST['hmac'])) {
      $file = $_FILES['file'];
      if($file['error'] === 0) {
        $target_file = '/common/forecast_uploads/' . basename($file['name']);
        if(move_uploaded_file($file['tmp_name'], $target_file)) {
          $template = 'openssl dgst -sha256 -hmac "%s" "%s" | cut -d " " -f 2';
          $command = sprintf($template, $hmacSecret, $target_file);
          $hmac = trim(shell_exec($command));
          $expected = substr($hmac, 0, 8) . '...';
          if($hmac === $_REQUEST['hmac']) {
            $sql = 'INSERT INTO `forecast_uploads` (`hmac`, `uploaded`, `name`, `status`, `message`) VALUES ("%s", now(), "%s", 0, "%s")';
            // trust no one...
            $name = mysql_real_escape_string(basename($file['name']));
            // ...not even myself
            $message = mysql_real_escape_string('queued');
            // add to the queue
            mysql_query(sprintf($sql, $hmac, $name, $message));
            // notify that the queue has been updated
            mysql_query('CALL automation.RunStep(44);');
            ?><h3>success: file uploaded and hmac verified</h3><?php
          } else { ?><h3 class="error">hmac mismatch, expected [<?php print($expected); ?>]</h3><?php sleep(5); }
        } else { ?><h3 class="error">filesystem error</h3><?php }
      } else { ?><h3 class="error">upload error</h3><?php }
      print('<hr>');
    }
    ?>
    <h1>upload</h1>
    <p>
      <form method="POST" enctype="multipart/form-data">
        <label>file: <input type="file" name="file"></label><br>
        <label>hmac: <input type="text" name="hmac"></label><br>
        <input type="submit" value="Upload">
      </form>
    </p>
    <hr>
    <h1>recent</h1>
    <table>
      <tr><th>date</th><th>name</th><th>hmac</th><th>result</th></tr>
      <?php
      $result = mysql_query('SELECT concat(substr(`hmac`, 1, 8), \'...\') `hmac`, `uploaded`, `name`, `status`, `message` FROM `forecast_uploads` ORDER BY `uploaded` DESC LIMIT 5');
      while($row = mysql_fetch_array($result)) {
        printf('<tr><td>%s ET</td><td>%s</td><td>%s</td><td>(%d) %s</td></tr>', $row['uploaded'], $row['name'], $row['hmac'], $row['status'], $row['message']);
      }
      ?>
    </table>
    <input type="button" onclick="javascript:window.location.href=window.location.href" value="Refresh"/>
    <hr>
    <h1>about</h1>
    <p>
      Hi! You can upload your flu contest forecasts here. It'll take ~30 seconds for automation to see and process the file. After that, it'll be available through the <a target="_blank" href="https://github.com/cmu-delphi/delphi-epidata">Epidata API</a>.
    </p>
    <p>
      If two forecasts are uploaded for the same system and epiweek, the second will overwrite the first.
    </p>
    <p>
      To compute the hmac of your forecast, run [ <span style="font-family: monospace;">openssl dgst -sha256 -hmac "<span style="color: #888; font-style: italic;">&lt;secret&gt;</span>" "<span style="color: #888; font-style: italic;">&lt;filename&gt;</span>"</spam> ]. The hmac should be a 64 character string of hex digits (32 bytes, 256 bits).
    </p>
  </body>
</html>
