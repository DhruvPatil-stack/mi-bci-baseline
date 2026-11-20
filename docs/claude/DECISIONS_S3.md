# DECISIONS S3

- BandPass default fs changed from SFREQ (160) to None. transform() resolves None to dataset_spec()['sfreq'] at call
  time. sklearn clone/get_params unchanged (fs stays a constructor param). Factories still pass fs explicitly, so
  G8 and every fitted pipeline are identical; explicit fs=160 callers are unaffected.
- data.py: expected n_channels, n_samples, sfreq come from dataset_spec("physionet") (not the active dataset, since
  this loader only reads PhysioNet EDF). Module constants N_CHANNELS/N_SAMPLES/SFREQ kept as names bound to the spec.
  Behaviour for PhysioNet is unchanged. Docstring wording updated only.
