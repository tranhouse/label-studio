# Label Studio patch: progress bar for Retrieve Predictions

**Work in progress, not tested yet.**

A change to Label Studio 1.23.2 itself (not this pipeline). In the Data Manager,
**Actions > Retrieve Predictions** sends the selected tasks to the ML backend 10 at a
time and shows a progress dialog (bar, elapsed time, time left, new / skipped / missing
predictions, Stop button) instead of a spinner.

`retrieve-predictions-progress.patch` applies to the `1.23.2` tag of
https://github.com/HumanSignal/label-studio. Build and install instructions will be
added once it has been tested.
