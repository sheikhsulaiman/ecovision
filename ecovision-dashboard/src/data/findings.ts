/**
 * Every number the site displays, in one place.
 *
 * All of these are read out of the thesis pipeline's own outputs --
 * outputs/tables/*.csv and the chapters in docs/thesis/ -- not typed from
 * memory. When the pipeline is rerun, this file is what changes.
 *
 * Reference-based figures are PROVISIONAL: inter-interpreter agreement
 * failed its threshold, so every accuracy and area estimate here is
 * indicative pending reconciliation. `provisional: true` marks the ones
 * that carry that caveat, and the UI is expected to show it.
 */

export type Signal = "spectral" | "spatial" | "temporal";
export type DistrictId = "gazipur" | "sylhet" | "bandarban";

export interface District {
  id: DistrictId;
  name: string;
  areaKm2: number;
  signal: Signal;
  mechanism: string;
  blurb: string;
  /** Map centre, [lat, lon]. */
  centre: [number, number];
  zoom: number;
  forest2024: string;
  nonForest2024: string;
  adjustedLoss: string;
  referenceChangePoints: number;
  lossExcludesZero: boolean;
  landCoverOverall: number;
}

export const DISTRICTS: District[] = [
  {
    id: "gazipur",
    name: "Gazipur",
    areaKm2: 1819,
    signal: "spectral",
    mechanism: "Abrupt permanent conversion",
    blurb:
      "Industrial and urban expansion pushing north out of Dhaka. Cleared land looks different from forest and stays different, which makes this the easy case and the useful baseline.",
    centre: [24.09, 90.42],
    zoom: 10,
    forest2024: "45,530 ± 25,723 ha",
    nonForest2024: "134,252 ± 25,723 ha",
    adjustedLoss: "443 ± 849 ha",
    referenceChangePoints: 2,
    lossExcludesZero: false,
    landCoverOverall: 0.57,
  },
  {
    id: "sylhet",
    name: "Sylhet",
    areaKm2: 3416,
    signal: "spatial",
    mechanism: "Gradual degradation with plantation confusion",
    blurb:
      "Tea estates are as green and as dense as natural forest at 30 m. What separates them is pattern — planted rows, uniform canopy height, hard geometric edges — which a per-pixel model cannot see at all.",
    centre: [24.9, 91.87],
    zoom: 9,
    forest2024: "41,681 ± 23,420 ha",
    nonForest2024: "254,993 ± 31,210 ha",
    adjustedLoss: "5,547 ± 10,755 ha",
    referenceChangePoints: 7,
    lossExcludesZero: false,
    landCoverOverall: 0.533,
  },
  {
    id: "bandarban",
    name: "Bandarban",
    areaKm2: 4592,
    signal: "temporal",
    mechanism: "Cyclical clearing and regrowth (jhum)",
    blurb:
      "Shifting cultivation on a five-to-seven year cycle: clear, crop, abandon, regrow, repeat. Any single pair of dates catches the cycle mid-swing and reports something that did not happen.",
    centre: [21.82, 92.35],
    zoom: 9,
    forest2024: "365,272 ± 43,291 ha",
    nonForest2024: "73,620 ± 41,822 ha",
    adjustedLoss: "71,011 ± 41,629 ha",
    referenceChangePoints: 18,
    lossExcludesZero: true,
    landCoverOverall: 0.317,
  },
];

export const byId = (id: DistrictId): District =>
  DISTRICTS.find((d) => d.id === id)!;

/** LandTrendr on the annual NBR series, 1988-2024, Bandarban, at 30 m. */
export const JHUM = {
  totalDisturbedHa: 88122,
  permanentShareOfDisturbed: 0.164,
  cyclicalShareOfDisturbed: 0.638,
  undeterminedShareOfDisturbed: 0.198,
  classes: [
    { label: "Stable", areaHa: 371380, shareOfDistrict: 0.808, tone: "neutral" },
    { label: "Permanent conversion", areaHa: 14457, shareOfDistrict: 0.0315, tone: "loss" },
    { label: "Cyclical jhum", areaHa: 56235, shareOfDistrict: 0.1224, tone: "recover" },
    { label: "Undetermined", areaHa: 17431, shareOfDistrict: 0.0379, tone: "muted" },
  ],
} as const;

/**
 * Patch-test macro F1, scored against Hansen-derived training labels.
 *
 * `winner` is typed as the full ModelKey union rather than inferred from
 * the current values. Inferring it narrows the type to whichever models
 * happen to win today, and the UI's highlight check for the others then
 * becomes a compile error the next time the pipeline is rerun.
 */
export type ModelKey = "rf" | "unet" | "ensemble";

export interface ModelRow {
  district: string;
  rf: number;
  unet: number;
  ensemble: number;
  patches: number;
  winner: ModelKey;
}

export const MODEL_COMPARISON: ModelRow[] = [
  { district: "Gazipur", rf: 0.4125, unet: 0.3157, ensemble: 0.4443, patches: 55, winner: "ensemble" },
  { district: "Sylhet", rf: 0.5028, unet: 0.5895, ensemble: 0.5187, patches: 167, winner: "unet" },
  { district: "Bandarban", rf: 0.4632, unet: 0.4607, ensemble: 0.4754, patches: 260, winner: "ensemble" },
];

/** Sylhet texture ablation: same architecture, texture bands in and out. */
export const TEXTURE_ABLATION = {
  rows: [
    { run: "U-Net, 23 bands (texture)", nonForest: 0.9389, forest: 0.3163, plantation: 0.452, water: 0.6508 },
    { run: "U-Net, 20 bands (no texture)", nonForest: 0.9368, forest: 0.3172, plantation: 0.3696, water: 0.6244 },
  ],
  randomForestPlantation: 0.0286,
  gain: 0.0824,
  relativeGain: 0.22,
} as const;

/** Change-class F1. Overall accuracy is uninformative for a minority class. */
export const CHANGE_DETECTION = [
  { district: "Gazipur", pcc: 0.0, ndvi: 0.0, referenceLoss: 2 },
  { district: "Sylhet", pcc: 0.0, ndvi: 0.148, referenceLoss: 7 },
  { district: "Bandarban", pcc: 0.138, ndvi: 0.357, referenceLoss: 18 },
] as const;

/** Cohen's kappa at T3. Gate 4 threshold is 0.75. All three fail. */
export const KAPPA = [
  { sample: "Gazipur", points: 100, rawAgreement: 0.5, kappa: 0.157 },
  { sample: "Sylhet", points: 180, rawAgreement: 0.439, kappa: 0.038 },
  { sample: "Sylhet plantation stratum", points: 40, rawAgreement: 0.3, kappa: 0.067 },
] as const;

export const GATE_4_THRESHOLD = 0.75;

/** Methods that were tried properly on the plantation problem and failed. */
export const NEGATIVE_RESULTS = [
  {
    value: "83%",
    headline: "Manual digitising was wrong at sub-metre resolution.",
    detail:
      "A polygon drawn as 1,906 ha of tea turned out to be roughly 1,600 ha of hill forest. Corrected to 321 ha, and only because somebody independently checked it.",
  },
  {
    value: "1 / 19",
    headline: "No open dataset locates these estates.",
    detail:
      "The global planted-trees database carried no Bangladesh layer in the version tested. OpenStreetMap has one usable polygon district-wide. Public gazetteers resolve one estate in nineteen under strict name matching.",
  },
  {
    value: "p = 0.55",
    headline: "A purpose-built row detector found nothing.",
    detail:
      "An FFT periodicity and Hough line detector, built to catch the planted-row signature, returned 4.36 for forest against 4.27 for tea. No separation.",
  },
  {
    value: "κ 0.067",
    headline: "Two trained people could not agree on what tea looks like.",
    detail:
      "On 40 points drawn deliberately inside the tea-growing upazilas, the interpreters agreed on 12. One called 25 plantation; the other called 14, and called 20 of them natural forest.",
  },
  {
    value: "1,303 ha",
    headline: "The layer we did draw is incomplete, and we bound it.",
    detail:
      "Against a district total reported in excess of 10,000 ha. Tea outside those polygons is labelled natural forest, so the Sylhet confusion is reduced rather than eliminated.",
  },
] as const;

export const STUDY = {
  startYear: 1988,
  endYear: 2024,
  epochs: [1990, 2000, 2010, 2024],
  districtYearsAudited: 120,
  bands: 23,
  patches: 706,
  patchPx: 128,
  referencePoints: 400,
  plannedReferencePoints: 1650,
  slcOffYears: [2012, 2013],
  totalAreaKm2: 9827,
} as const;

/**
 * Filled in once the Earth Engine App is published from the Code Editor
 * (Apps > Publish app). Until then the UI shows the map section without
 * the live embed rather than pointing at a URL that does not resolve.
 */
export const LINKS = {
  earthEngineApp:
    "https://ecovision-503602.projects.earthengine.app/view/ecovision",
  thesisPdf: "",
  repository: "",
} as const;
