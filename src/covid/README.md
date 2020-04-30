# about

This directory contains sources related to the 2020 COVID-19 adaptation of
Epicast. The Epicast code here is written specifically to forecast wILI during
the Spring 2020 wave of the COVID-19 pandemic in the United States. It is not
generally applicable to other seasons, signals, or locations in its current
form.

# history

In response to the COVID-19 pandemic in early 2020, Delphi adapted the Epicast
flu forecasting website mid-flu-contest to instead collect forecasts
specifically geared toward COVID-19. As part of this shift, the site was
rebranded as "Crowdcast".

The new forecasting targets (e.g. "offset" instead of "onset"), and the timing
of those targets (i.e. spanning the flu off-season), were, in sum, a large
enough deviation from the normal flu contest that surgery on the "actual"
Epicast codebase was considered too time-consuming and error-prone. Instead,
the same Epicast methodology was re-implemented from the ground up, here.

There is one difference to note between the "actual" Epicast and the
implementation here. Both Epicast implementations add noise to recent wILI
values by sampling from a normal distribution based on wILI backfill. The
actual Epicast bases the distribution on empirical backfill observed within a
particular location. For simplicity, this implementation assumes that backfill
noise is IID normal, independent of location, with zero mean and standard
deviation equal to `2 ** -n`, where `n` is age in weeks. In other words, the
most recent wILI has stdev 1, the week before that has stdev 0.5, and so on.

# running

Forecasts are produced with the following command, substituting the appropriate
epiweek, which is normally the the latest epiweek published by CDC (aka
"issue"). This can be determined by the `latest_issue` field returned by the
[Epidata API endpoint `fluview_meta`](https://github.com/cmu-delphi/delphi-epidata/blob/master/docs/api/fluview_meta.md).
As user `automation` in working directory `/home/automation/driver`:

```bash
# find the latest published epiweek
curl 'https://delphi.midas.cs.cmu.edu/epidata/api.php?source=fluview_meta'

# produce a forecast for epiweek 202016
python3 -m delphi.flu_contest.covid.generate_forecast --epiweek 202016

# show the resulting forecast CSVs
ls -l covid-epicast-202016-*.csv
```

# testing

Per the
[backend development guide](https://github.com/cmu-delphi/operations/blob/master/docs/backend_development.md),
run unit tests as follows:

```bash
docker build -t delphi_python \
  -f repos/delphi/operations/dev/docker/python/Dockerfile .

docker run --rm delphi_python \
  python3 -m undefx.py3tester.py3tester --color \
    repos/delphi/flu-contest/tests/covid/
```
