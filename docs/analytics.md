# KPI definitions and statistical methods

## Windows and engagement

UTC [start,end). UI end dates include that date. Queries retain pre-start event history needed for
trailing windows and returning-user checks. Segment filters restrict users, events and requests.
DAU counts distinct users with any accepted event that day; WAU/MAU use trailing 7/30 days ending
after that day. They are not sums of DAU. Stickiness=DAU/MAU. Missing denominators are NA.

Adoption=distinct feature users / distinct active users in the window. Frequency=feature events /
feature users. Monthly-cohort feature adoption divides by active members of each acquisition
month. Retention instead uses every acquired cohort member as denominator.

## Conversion and retention

Eligible signups have registration >=start and <end-7days. Every included user has a complete
seven-day horizon. Funnel stages register/login/dashboard/activate must occur strictly in order
for that user, no earlier than registration and before registration+7days. Every stage shares the
eligible cohort. Stage conversion=current users/previous-stage users; drop-off=1-stage conversion.
Overall activation=final-stage users/eligible signups. Signup-week trends use one observation cutoff;
prior-window comparisons use their own cutoff to avoid future outcome leakage.

Weekly cohorts start Monday UTC. Retention(c,k)=distinct active cohort members in cohort week k /
cohort size. Omit incomplete cohort weeks. Week zero includes signup activity; the dataset's initial
acquisition week is partial because data starts Wednesday. Returning percentage=window-active users
with earlier accepted events/window-active users. Earlier registration alone does not imply returning.

## Reliability

Failure count counts HTTP 4xx/5xx requests. Error rate=failures/all accepted requests, independent
of error-log multiplicity. p50/p95/p99 use all response times in milliseconds, including failures,
with linear interpolation. Incident hours=(end-start) from synthetic records. Unobserved request
days have no reliable error rate and are not imputed as successful traffic.

## Detection and evaluation

Rolling methods use x(t-14)...x(t-1), requiring 14 observations. Z-score uses prior mean and sample
standard deviation. MAD uses prior median and scale 1.4826*median(abs(x-median(x))). Scale floors:
.005 for error rate, 1 for daily counts. Flag |score|>3; high severity |score|>6, otherwise medium.
Warm-up/missing baselines remain unclassified. Negative deviations can flag recovery.

Isolation Forest trains on first 30 days of error rate and mean latency, with 150 trees, seed42,
contamination .05; only later days are evaluated. It rejects nonfinite features or an entirely
constant baseline. Contamination is a modeling parameter, not the known incident frequency.

Precision=TP/(TP+FP); recall=TP/(TP+FN); false positives=flagged nonincident days. Empty precision/
recall denominators return zero. Report evaluated and labeled day counts because method warm-ups
differ. Labels come from persisted synthetic intervals and cover reliability only. Recovery alerts
can be useful yet count as false positives under those labels. Rolling baselines adapt during a
sustained incident, reducing later-day sensitivity. These are synthetic evaluation results, not
production accuracy estimates. Held-out-seed calibration remains future work.

## Investigation and AI grounding

Compare seven days before/after a chosen date: endpoint rates/counts, segment rates, error types,
nearby releases (+/-3days) and up to100 failed requests. Endpoint evidence includes sample request
IDs. Counts reveal partial history; unequal observed exposure limits comparisons. Timing establishes
association only; traffic mix, dependencies and controlled rollback evidence require further work.
The optional model selects allowlisted evidence/template IDs; numerical facts are deterministically
rendered. Missing metrics serialize to null. Raw logs/properties never enter the model context.
