"""Contains email templates for Epicast and helper functions for using them.

Email categories include:

- `alerts`: custom, one-time `notifications`-type email for a manual user group
- `notifications`: for all users, says that the CDC published new data
- `reminders`: for users with missing forecasts, a reminder that the deadline
is soon
"""


class EpicastEmails:
  """Templating for Epicast emails."""

  class Template:
    """Namespace for email template text."""

    # TODO: update to literal template strings after upgrade to Python 3.6+
    # see https://www.python.org/dev/peps/pep-0498/

    # a tag which precedes the subject in all emails
    SUBJECT_TAG = '[Crowdcast]'

    # the unsubscribe section embedded in all emails
    UNSUBSCRIBE = {
      'text': '''
        ----------

        [This is an automated message. To edit your email preferences or to
        stop receiving these emails, follow the unsubscribe link below.]

        Unsubscribe: https://delphi.cmu.edu/crowdcast/preferences.php?user=%s
      ''',
      'html': '''
        <hr>
        <p style="color: #666; font-size: 0.8em;">
          [This is an automated message. To edit your email preferences or to
          stop receiving these emails, click the unsubscribe link below.]
          <br>
          <a href="https://delphi.cmu.edu/crowdcast/preferences.php?user=%s">
          Unsubscribe</a>
        </p>
      ''',
    }

    # placeholder for one-off emails sent on special occasions
    ALERT = {
      'subject': 'End of flu forecasting round',
      'text': '''
        Dear %s,

        This past week was the last week of CDC’s initiative to forecast Influenza
        Like Illness (ILI) this year.  Our Crowdcasting activity is therefore halting
        for now.  Accordingly, you will not receive any more weekly reminders.
        
        The exact extent of ILI activity this year will not become fully known for a
        few more months, once all reporting has stabilized.  We plan to analyze
        Crowdcast’s accuracy and publish the results thereafter.
        
        In the coming Fall, our plan (as well as CDC’s) is to focus on tracking and
        forecasting COVID-19 activity.  Although one can never be sure how the coming
        flu season will unfold, we suspect (and hope) that flu activity will be
        considerably diminished in the coming Fall and Winter, due both to heightened
        flu vaccination and diminished spread as a spillover benefit from COVID-19
        mitigation efforts.
        
        Our strategy for forecasting COVID-19 is still evolving.  If we decide to apply
        the Crowdcasting method to COVID-19 forecasting, we will certainly invite you 
        to participate again. In the meantime, we invite you to check out what we have
        created so far, including our interactive map for tracking COVID-19 in the U.S.
        and our COVIDcast API, which makes a variety of traditional and alternative
        indicators of disease activity conveniently available through Python and R
        packages.

        We are very grateful for your participation in our Crowdcast project.
        Thank you for your contributions.
        
        -The DELPHI group
        
        DELPHI homepage: https://delphi.cmu.edu/
        Interactive COVID-19 map: https://covidcast.cmu.edu/
        COVIDcast API: https://cmu-delphi.github.io/delphi-epidata/api/covidcast.html
        
        Carnegie Mellon University
      ''',
      'html': '''
        <p>
          Dear %s,
        </p><p>
        This past week was the last week of CDC’s initiative to forecast Influenza
        Like Illness (ILI) this year.  Our Crowdcasting activity is therefore halting
        for now.  Accordingly, you will not receive any more weekly reminders.
        </p><p>
        The exact extent of ILI activity this year will not become fully known for a
        few more months, once all reporting has stabilized.  We plan to analyze
        Crowdcast’s accuracy and publish the results thereafter.
        </p><p>
        In the coming Fall, our plan (as well as CDC’s) is to focus on tracking and
        forecasting COVID-19 activity.  Although one can never be sure how the coming
        flu season will unfold, we suspect (and hope) that flu activity will be
        considerably diminished in the coming Fall and Winter, due both to heightened
        flu vaccination and diminished spread as a spillover benefit from COVID-19
        mitigation efforts.
        </p><p>
        Our strategy for forecasting COVID-19 is still evolving.  If we decide to apply
        the Crowdcasting method to COVID-19 forecasting, we will certainly invite you 
        to participate again. In the meantime, we invite you to check out what we have
        created so far, including our <a href="https://covidcast.cmu.edu/">interactive
        map</a> for tracking COVID-19 in the U.S.and our <a 
        href="https://cmu-delphi.github.io/delphi-epidata/api/covidcast.html">COVIDcast
        API</a>, which makes a variety of traditional and alternative indicators of
        disease activity conveniently available through Python and R packages.
        </p><p>
        We are very grateful for your participation in our Crowdcast project.
        Thank you for your contributions.
        </p><p>
        -<a href="https://delphi.cmu.edu/">The DELPHI group</a>
        <br>
        Carnegie Mellon University
        </p>
      ''',
    }

    # the optional scoring section embedded in weekly notifications
    SCORE = {
      'text': '''
        Your overall score is: %d (ranked #%d)

        Note: To be listed on the leaderboards, simply enter your initials on
        the preferences page at
        https://delphi.cmu.edu/crowdcast/preferences.php?user=%s

        You can find the leaderboards at
        https://delphi.cmu.edu/crowdcast/scores.php
      ''',
      'html': '''
        <p>
          Your overall score is: %d (<i>ranked #%d</i>)
          <br>
          Note: To be listed on the <a
          href="https://delphi.cmu.edu/crowdcast/scores.php">leaderboards</a>,
          simply enter your initials on the preferences page <a
          href="https://delphi.cmu.edu/crowdcast/preferences.php?user=%s">
          here</a>.
        </p>
      ''',
    }

    # the weekly "new data available" notification
    NOTIFICATION = {
      'subject': 'New Data Available (Deadline: Monday 10 AM)',
      'text': '''
        Dear %s,

        The CDC has released another week of influenza-like-illness (ILI)
        surveillance data. A new round of covid19-related forecasting is now
        underway, and we need your forecasts! We are asking you to please
        submit your forecasts by 10:00 AM (ET) this coming Monday. Thank you so
        much for your support and cooperation!

        To login and submit your forecasts, visit
        https://delphi.cmu.edu/crowdcast/
        and enter your User ID: %s

        {SCORE}

        Thank you again for your participation, and good luck on your
        forecasts!

        Happy Forecasting!
        -The DELPHI Team
      ''',
      'html': '''
        <p>
          Dear %s,
        </p><p>
          The CDC has released another week of influenza-like-illness (ILI)
          surveillance data. A new round of covid19-related forecasting is now
          underway, and we need your forecasts! We are asking you to please
          submit your forecasts by <b>10:00 AM (ET)</b> this coming Monday.
          Thank you so much for your support and cooperation!
        </p><p>
          To login and submit your forecasts, click <a
          href="https://delphi.cmu.edu/crowdcast/launch.php?user=%s">here</a>
          or visit https://delphi.cmu.edu/crowdcast/ and enter your User ID: %s
        </p>{SCORE}<p>
          Thank you again for your participation, and good luck on your
          forecasts!
        </p><p>
          Happy Forecasting!
          <br>
          -The DELPHI Team
        </p>
      ''',
    }

    # the weekly "forecast due soon" reminder
    REMINDER = {
      'subject': 'Forecasts Needed (Deadline: Monday 10AM)',
      'text': '''
        Dear %s,

        This is just a friendly reminder that your influenza-like-illness (ILI)
        forecasts are due by 10:00AM (ET) on Monday. Thank you so much for your
        support and cooperation!

        To login and submit your forecasts, visit
        https://delphi.cmu.edu/crowdcast and enter your User ID: %s.

        Happy Forecasting!

        -The DELPHI Team
      ''',
      'html': '''
        <p>
          Dear %s,
        </p><p>
          This is just a friendly reminder that your influenza-like-illness
          (ILI) forecasts are due by <b>10:00AM (ET) on Monday</b>. Thank you
          so much for your support and cooperation!
        </p><p>
          To login and submit your forecasts, click <a
          href="https://delphi.cmu.edu/crowdcast/launch.php?user=%s">here</a>
          or visit https://delphi.cmu.edu/crowdcast/ and enter your User ID: %s
        </p><p>
          Happy Forecasting!
          <br>
          -The DELPHI Team
        </p>
      ''',
    }

  @staticmethod
  def prepare(text):
    """Trim surrounding whitespace and use network-style CRLF line endings."""
    return '\r\n'.join([line.strip() for line in text.split('\n')]).strip()

  @staticmethod
  def compose(
      user_id,
      subject,
      text_template,
      html_template,
      text_values,
      html_values):
    """Create final subject and body from templates and values."""

    final_subject = EpicastEmails.Template.SUBJECT_TAG + ' ' + subject

    text_template += EpicastEmails.Template.UNSUBSCRIBE['text']
    text_values += (user_id,)
    final_text = EpicastEmails.prepare(text_template) % text_values

    html_template += EpicastEmails.Template.UNSUBSCRIBE['html']
    html_values += (user_id,)
    temp_html = EpicastEmails.prepare(html_template) % html_values
    final_html = '<html><body>' + temp_html + '</body></html>'

    return final_subject, final_text, final_html

  @staticmethod
  def get_alert(user_id, user_name):
    """Fill out and return the alert email."""

    template = EpicastEmails.Template.ALERT
    values = (user_name,)
    return EpicastEmails.compose(
        user_id,
        template['subject'],
        template['text'],
        template['html'],
        values,
        values)

  @staticmethod
  def get_notification(
      user_id, user_name, last_score, last_rank, total_score, total_rank):
    """Fill out and return the notification email."""

    template = EpicastEmails.Template.NOTIFICATION
    subject = template['subject']
    text = template['text']
    html = template['html']

    text_values = (user_name, user_id)
    html_values = (user_name, user_id, user_id)

    if last_score > 0:
      # include the embedded scoring section
      text = text.replace('{SCORE}', EpicastEmails.Template.SCORE['text'])
      html = html.replace('{SCORE}', EpicastEmails.Template.SCORE['html'])
      score_values = (total_score, total_rank, user_id)
      text_values += score_values
      html_values += score_values
    else:
      # omit the embedded scoring section
      text = text.replace('{SCORE}', '')
      html = html.replace('{SCORE}', '')

    return EpicastEmails.compose(
        user_id, subject, text, html, text_values, html_values)

  @staticmethod
  def get_reminder(user_id, user_name):
    """Fill out and return the reminder email."""

    template = EpicastEmails.Template.REMINDER

    text_values = (user_name, user_id)
    html_values = (user_name, user_id, user_id)

    return EpicastEmails.compose(
        user_id,
        template['subject'],
        template['text'],
        template['html'],
        text_values,
        html_values)
