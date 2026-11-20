# Stroke dataset facts (FROZEN, Head chef, Phase 0 v0.3)

Liu et al., "An EEG motor imagery dataset for brain computer interface in acute stroke patients",
Scientific Data 11, 131 (2024). DOI 10.1038/s41597-023-02787-8. Facts only. Each fact has a source line.
Read 2026-11-20. Sources: [P] = paper full text, Europe PMC
`https://www.ebi.ac.uk/europepmc/webservices/rest/PMC10811218/fullTextXML`. [F] = figshare API
`https://api.figshare.com/v2/articles/21679035` (dataset "EEG datasets of stroke patients", version 5,
DOI 10.6084/m9.figshare.21679035.v5, published 2023-09-14). [B] = the BIDS sidecar files downloaded from
that figshare record (file name given). The nature.com page needed a login, and PMC answered with a bot check.

## Download and size
- `sourcedata.zip`: 1874824439 bytes, `https://ndownloader.figshare.com/files/38516555`, md5 4336b1ddbde42f89edb82f513a5c0721. Source: [F]
- `edffile.zip`: 462843633 bytes, `https://ndownloader.figshare.com/files/38516654`, md5 aa4f96a0e8456f377f30d1ee8f41be40. Source: [F]
- Small files: `participants.tsv` (3557 B, files/42345150), `participants.json` (2389 B), `task-motor-imagery_channels.tsv` (709 B), `task-motor-imagery_electrodes.tsv` (761 B), `task-motor-imagery_eeg.json` (569 B), `task-motor-imagery_events.tsv` (3732 B), `task-motor-imagery_events.json` (806 B), `README.md`, `code.zip`, `stimuli.zip`, `dataset_description.json`. Source: [F]
- `dataset_description.json` gives `"DownLoadLinks": "https://doi.org/10.6084/m9.figshare.21393402"`, which is a different figshare id than the record read here (21679035). Source: [B] dataset_description.json

## License
- Dataset: CC BY 4.0 (`https://creativecommons.org/licenses/by/4.0/`). Source: [F] `license.name`; also [B] dataset_description.json `"License": "CC BY 4.0"`
- Article: "This article is licensed under a Creative Commons Attribution 4.0 International License". Source: [P]
- CC BY 4.0 allows redistribution of derived results when attribution is given. Raw data is still never committed to this repo (PRD_v0.3 section 14).

## Subjects and trials
- 50 acute stroke patients ("We collected data from 50 acute stroke patients"). Source: [P]
- 40 trials per patient, one run: "We recorded one run with 40 trials per run." Source: [B] README.md. "the number of trials is 40". Source: [P] Data Records
- The paper's Usage Notes also say "we used a task including only 20 trials per patient". This contradicts the 40 above. Source: [P]
- `task-motor-imagery_events.tsv` lists 40 trials: 20 with trial_type 1 and 20 with trial_type 2 (120 rows, 3 per trial). Source: [B] task-motor-imagery_events.tsv (counted)

## Channels and sampling rate
- 29 EEG + 2 EOG channels, 10-10 system, reference CPz, ground FPz: `"EEGChannelCount": 29`, `"EOGChannelCount": 2`, `"EEGReference": "CPz"`, `"EEGGround": "FPz"`. Source: [B] task-motor-imagery_eeg.json
- Sampling rate 500 Hz: `"SamplingFrequency": 500`. Line frequency 50 Hz. Source: [B] task-motor-imagery_eeg.json; "The sampling frequency was 500 Hz." Source: [P]
- Device: ZhenTec NT1 (Xi'an ZhenTec Intelligence), wireless, Ag/AgCl semi-dry electrodes. Source: [B] task-motor-imagery_eeg.json; [P]
- Channel names in order (all with units uV): FP1, FP2, Fz, F3, F4, F7, F8, FCz, FC3, FC4, FT7, FT8, Cz, C3, C4, T3, T4, CP3, CP4, TP7, TP8, Pz, P3, P4, T5, T6, Oz, O1, O2 (EEG), HEOL, VEOR (EOG). Source: [B] task-motor-imagery_channels.tsv
- The paper's Data Records give a different count: "30 EEG channels (channel 18 is reference channel), 2 EOG channels (31 horizontal EOG channels and 32 vertical EOG channels), and 1 marker event channel". Its Table 2 lists CPz as channel 18 and names FT7 twice (11 and 21). Source: [P]. So the raw `.mat` files may hold 33 channels with CPz at index 17 (0-based). The loader must check the stored channel names or count before it selects the 29 EEG channels.
- Units: uV (`units` column of every channel = "μV"). Source: [B] task-motor-imagery_channels.tsv. The paper does not state units. Source: [P]

## Trial timing and labels
- Each trial is 8 s: instruction 2 s, motor imagery 4 s, break 2 s. events.tsv per trial: value 1 "Instruction beginning" (duration 2000 ms), value 2 "Motor imagery beginning" (duration 4000 ms), value 3 "Break beginning" (2000 ms). Source: [B] task-motor-imagery_events.tsv and task-motor-imagery_events.json (onset and duration in milliseconds)
- Labels: trial_type "1": "Imagining the movement of the left hand", "2": "Imagining the movement of the right hand". Source: [B] task-motor-imagery_events.json. Same in the paper: "(“1” for left-hand MI tasks and “2” for right-hand MI tasks)". Source: [P]
- This repo maps trial_type 1 -> y = 0 (left), 2 -> y = 1 (right), as for PhysioNet (config `stroke.label_map`).
- Window used here (config `stroke.window`, fixed before any data was loaded): 0.5 s to 3.498 s after the motor-imagery onset (value 2), so 1500 samples at 500 Hz. This mirrors the PhysioNet 0.5 s to 3.5 s window.

## Files and formats
- Raw: `sourcedata.zip` holds `sub-xx_task-motor-imagery_eeg.mat` with variables `rawdata` (trials x channels x time-samples; 40 x 33 x 4000) and `labels`. Source: [P]. 4000 samples = 8 s at 500 Hz.
- Pre-processed: `edffile.zip` holds `sub-xx_task-motor-imagery_eeg.edf`. Baseline removal and a 0.5 to 40 Hz filter were applied ("time-domain filtering on the data from 0.5 to 40 Hz"; "baseline removal and FIR filtering"). Source: [P]. `"SoftwareFilter": "N/A"` in the sidecar. Source: [B] task-motor-imagery_eeg.json
- Organized as BIDS. Source: [P]

## Patient characteristics
- `participants.tsv`, columns: Participant_ID, Gender, Age, Duration, ParalysisSide, Handedness, IsFirstTime, StrokeLocation, NIHSS, MBI, mRS. Source: [B] participants.tsv header; meanings in participants.json
- It holds the affected side: `ParalysisSide` = "The side of limb paralysis due to stroke." Source: [B] participants.json. Counts in the file: 28 left, 22 right (50 rows). Source: [B] participants.tsv (counted)
- The paper reports 27 left and 23 right hemiplegia ("Twenty-three patients (46%) had right hemiplegia, 27 patients (54%) had left hemiplegia"). This differs from the file by 1 patient. Source: [P]
- Time from stroke onset to enrolment: 1 to 30 days. Source: article abstract, DOAJ record https://doaj.org/article/74cfbd50848643b4ae48c146046b300f (via web search)
