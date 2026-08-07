"""Pre-render the evidence for every reference point into one HTML page.

The human still makes every call. This only removes the part that was
never interpretation in the first place.

    python src/interpret_tool.py --district sylhet --author a
    python src/interpret_tool.py --district bandarban --author a --trajectory

Output: outputs/interpret/{district}_author_{a|b}.html  (self-contained)
        data/interpret_cache/  (chips, so a re-run costs nothing)

WHY THIS IS NOT A LABELLING MODEL
---------------------------------
CLAUDE.md rule 3. The reference sample is the only independent yardstick
in the thesis; if a model produces it, every accuracy figure — including
the ensemble's — measures a model against a model, and the headline claim
that model choice matters more as landscape complexity rises becomes
unobservable. So nothing here predicts a class, ranks a class, orders the
points by anything a classifier said, or shows the interpreter a hint.

What it does is fetch. Interpretation was ~90 s per point, of which the
decision was maybe 20: the rest was flying Earth Pro to a coordinate,
finding historical imagery near the right date, and squinting at it. All
of that is mechanical, and all of it is done here in advance.

WHAT THE INTERPRETER SEES
-------------------------
Four false-colour chips, one per epoch anchor, same footprint and same
stretch. SWIR1/NIR/red rather than true colour because it separates
forest from tea from bare soil far better at 30 m — true colour makes
both tea and forest a similar green, which is the exact confusion RQ3 is
about.

Optionally an NDVI/NBR trajectory 1988-2024. That is what makes jhum
legible: shifting cultivation is a sawtooth, permanent conversion is a
step that never recovers. No pair of dates can show the difference
(rule 9), so for Bandarban the trajectory is not a nicety.

Also a link that opens the coordinate in Google Earth / Maps at sub-metre
resolution. Rule 1 permits that for visual reference interpretation of
the validation sample and for nothing else.
"""

from __future__ import annotations

import argparse
import base64
import json
import sys
import threading
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import ee
import pandas as pd

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))
import preprocess as pp  # noqa: E402

REF_DIR = REPO / "data" / "reference"
CACHE_DIR = REPO / "data" / "interpret_cache"
OUT_DIR = REPO / "outputs" / "interpret"

# Half-width of the chip footprint. 750 m gives a 1.5 km box: wide enough
# to read the context a point sits in (is this a garden, a village edge, a
# valley), narrow enough that the point is not a speck.
CHIP_HALF_M = 750
CHIP_PX = 128

# SWIR1 -> red, NIR -> green, red -> blue. So vegetation reads GREEN and
# brighter with denser canopy, bare soil and harvested field read tan or
# pink, water and deep shadow read near black, and plantation tends to a
# flat uniform olive. Chosen over true colour because true colour makes
# tea and forest a similar green, which is the exact confusion RQ3 is
# about. Reflectance is already in [0, 1] after clamp_reflectance, so the
# stretch is in reflectance units.
VIS = {"bands": ["swir1", "nir", "red"], "min": 0.0, "max": 0.40, "gamma": 1.1}

MAX_WORKERS = 12
RETRIES = 3

CLASSES = {0: "non_forest", 1: "natural_forest", 2: "plantation", 3: "water"}

# One-key notes, per district, for the calls the protocol says cost kappa
# (docs/interpretation_protocol.md §4). These are not classes and must not
# become classes.
#
# Bandarban's pair is the important one. A jhum plot's CLASS is decided by
# its canopy at the observation date, never by its land-use history — but
# whether the loss is cyclical or permanent still has to be recorded, and
# it belongs in notes. Without it RQ6 has nothing to validate the
# LandTrendr separation against.
TAGS = {
    "bandarban": [("c", "cyclical"), ("p", "permanent"), ("x", "cloud at T0")],
    "sylhet": [("t", "tea/forest boundary"), ("x", "cloud at T0")],
    "gazipur": [("v", "homestead vegetation"), ("x", "cloud at T0")],
}

# Files the CSV asks for two calls per point: what it was at T0 and what
# it is at T3. Change is derived from the pair, never interpreted directly
# — an interpreter asked "did this change" anchors on the answer they want.
EPOCH_KEYS = [("class_t0", "T0"), ("class_t3", "T3")]


def sample_files(district: str) -> list[Path]:
    """Main sample plus any stratum top-ups drawn separately.

    Prefers the reduced design when it exists (src/subsample_reference.py).
    Reduced files carry a kappa_subset column; the full ones do not, and
    the page treats its absence as "every point is mine to interpret",
    which is what the full two-author design means.
    """
    reduced = [REF_DIR / f"reference_sample_{district}_reduced.csv"]
    reduced += sorted(REF_DIR.glob(f"reference_sample_{district}_*_topup_reduced.csv"))
    if any(f.exists() for f in reduced):
        return [f for f in reduced if f.exists()]
    files = [REF_DIR / f"reference_sample_{district}.csv"]
    files += sorted(REF_DIR.glob(f"reference_sample_{district}_*_topup.csv"))
    return [f for f in files if f.exists()]


def load_points(district: str, author: str) -> pd.DataFrame:
    """Every point for a district, tagged with the file its answers go back to.

    Top-ups are a separate second-stage sample with their own inclusion
    probabilities, so their interpretations cannot be merged into the main
    file — the Olofsson weights would be wrong and nothing would say so.
    They are rendered together because it would be absurd to make someone
    open two pages, but the export splits them back apart, which is why
    each point carries its destination rather than the page assuming one.
    """
    frames = []
    for path in sample_files(district):
        frame = pd.read_csv(path)
        stem = path.stem.replace("reference_sample_", "").replace("_reduced", "")
        frame["out_file"] = f"interpretation_{stem}_author_{author}.csv"
        if "kappa_subset" not in frame.columns:
            frame["kappa_subset"] = False
        frames.append(frame)
    return pd.concat(frames, ignore_index=True)


def epoch_images(district: str) -> dict[str, ee.Image]:
    aoi = ee.FeatureCollection(f"{pp.ASSET_ROOT}{district}_shp").geometry()
    return {
        name: pp.build_composite(aoi, year, with_stack=False).visualize(**VIS)
        for name, year in pp.EPOCHS.items()
    }


def fetch_chip(image: ee.Image, lon: float, lat: float) -> bytes | None:
    """One chip, retried. A dropped TLS handshake is not a missing chip.

    At twelve concurrent connections a few handshakes time out per
    thousand. Without the retry those points reach the interpreter with a
    blank panel, and a blank panel is answered by guessing.
    """
    region = ee.Geometry.Point([lon, lat]).buffer(CHIP_HALF_M).bounds()
    for attempt in range(RETRIES):
        try:
            url = image.getThumbURL(
                {"region": region, "dimensions": CHIP_PX, "format": "png"}
            )
            with urllib.request.urlopen(url, timeout=120) as response:
                return response.read()
        except Exception as exc:
            if attempt == RETRIES - 1:
                print(f"    chip failed at {lon:.4f},{lat:.4f}: {str(exc)[:60]}")
    return None


def build_chips(district: str, points: pd.DataFrame) -> dict[str, dict[str, str]]:
    """{point_id: {epoch: base64 png}} — cached on disk between runs."""
    images = epoch_images(district)
    cache = CACHE_DIR / district
    cache.mkdir(parents=True, exist_ok=True)

    tasks = [
        (row.point_id, epoch, row.lon, row.lat)
        for row in points.itertuples()
        for epoch in pp.EPOCHS
        if not (cache / f"{row.point_id}_{epoch}.png").exists()
    ]
    done = threading.Semaphore(0)
    total = len(tasks)
    if total:
        print(f"  fetching {total:,} chips ({MAX_WORKERS} workers)")

    counter = {"n": 0}
    lock = threading.Lock()

    def work(task):
        point_id, epoch, lon, lat = task
        blob = fetch_chip(images[epoch], lon, lat)
        if blob:
            (cache / f"{point_id}_{epoch}.png").write_bytes(blob)
        with lock:
            counter["n"] += 1
            if counter["n"] % 200 == 0:
                print(f"    {counter['n']:,}/{total:,}")

    if tasks:
        with ThreadPoolExecutor(max_workers=MAX_WORKERS) as pool:
            list(pool.map(work, tasks))

    chips: dict[str, dict[str, str]] = {}
    for row in points.itertuples():
        entry = {}
        for epoch in pp.EPOCHS:
            path = cache / f"{row.point_id}_{epoch}.png"
            if path.exists():
                entry[epoch] = base64.b64encode(path.read_bytes()).decode()
        chips[row.point_id] = entry
    return chips


def build_trajectory(district: str, points: pd.DataFrame) -> dict[str, dict]:
    """Annual NDVI and NBR at every point, START_YEAR to END_YEAR.

    Sampled one year at a time. A single request covering the whole series
    is one expression spanning 37 dry-season composites and times out; per
    year it is slow but it finishes, and a year that fails degrades that
    year to null rather than losing the series.
    """
    aoi = ee.FeatureCollection(f"{pp.ASSET_ROOT}{district}_shp").geometry()
    features = [
        ee.Feature(ee.Geometry.Point([row.lon, row.lat]), {"pid": row.point_id})
        for row in points.itertuples()
    ]
    collection = ee.FeatureCollection(features)

    years = list(range(pp.START_YEAR, pp.END_YEAR + 1))
    series: dict[str, dict] = {
        row.point_id: {"years": years, "ndvi": [None] * len(years),
                       "nbr": [None] * len(years)}
        for row in points.itertuples()
    }
    lock = threading.Lock()

    def work(index_year):
        index, year = index_year
        try:
            composite = pp.build_composite(aoi, year, with_stack=False)
            ndvi = composite.normalizedDifference(["nir", "red"]).rename("ndvi")
            nbr = composite.normalizedDifference(["nir", "swir2"]).rename("nbr")
            sampled = (
                ndvi.addBands(nbr)
                .sampleRegions(collection=collection, scale=pp.NATIVE_SCALE,
                               properties=["pid"], geometries=False)
                .getInfo()
            )
        except Exception as exc:
            print(f"    {year}: {str(exc)[:60]}")
            return
        with lock:
            for feat in sampled.get("features", []):
                prop = feat["properties"]
                entry = series.get(prop.get("pid"))
                if entry is None:
                    continue
                entry["ndvi"][index] = prop.get("ndvi")
                entry["nbr"][index] = prop.get("nbr")
        print(f"    {year} done")

    print(f"  sampling {len(years)} annual composites at {len(points)} points")
    with ThreadPoolExecutor(max_workers=6) as pool:
        list(pool.map(work, enumerate(years)))
    return series




# Per-district cues for the calls docs/interpretation_protocol.md §4 says
# cost kappa. Shown on the page, always, because the alternative was
# discovering after 500 points that "plantation" had been read as
# "agricultural land" — which is what happened, and which cost 123 points.
#
# This is protocol, not an answer key. It says what the classes MEAN. It
# never says what any particular point is, and it never shows where the
# digitised tea polygons are: those are training-label data, and letting
# them steer the reference sample would make class 2 circular exactly
# where RQ3 needs it independent.
LEGEND = {
    "_all": [
        ["0 non_forest", "Cropland, paddy, bare soil, built-up, roads, sand. "
                         "ALSO homestead gardens, betel and areca, and village "
                         "tree cover — dense green does not make it forest."],
        ["1 natural_forest", "Contiguous canopy ≥ 30%, structurally chaotic, "
                             "no settlement grid inside it. Boundaries follow "
                             "terrain and are ragged."],
        ["2 plantation", "Tea or rubber ESTATE only. Planted rows visible, "
                         "uniform canopy height and colour, pale service tracks "
                         "in a grid, hard geometric boundary. If it is a crop "
                         "field or a village garden it is 0, not 2."],
        ["3 water", "River, haor, pond, reservoir at the observation date."],
    ],
    "sylhet": [
        ["Tea is RARE", "Tea is a small fraction of Sylhet's area. If you are "
                        "calling plantation often, re-read the definition — "
                        "cropland and homestead gardens are class 0."],
        ["Judge the pixel", "Estates keep natural forest on steep ground inside "
                            "their boundaries. Those patches are 1, not 2."],
    ],
    "bandarban": [
        ["Canopy at the date", "A jhum plot is 0 or 1 by its canopy AT THE "
                               "OBSERVATION DATE, never by land-use history. "
                               "Cleared → 0. Fallow regrown to ≥ 30% → 1."],
        ["Cyclical vs permanent", "Read it off the trajectory and record it in "
                                  "notes, never in the class. Sawtooth that "
                                  "recovers = cyclical. Step that never "
                                  "recovers = permanent."],
    ],
    "gazipur": [
        ["Homestead vegetation", "Houses, ponds and a road grid under the "
                                 "canopy → class 0. Bhawal sal forest is "
                                 "contiguous with no settlement grid."],
    ],
}

# False-colour reading guide. The band order is SWIR1/NIR/red, so this is
# NOT the usual true-colour intuition, and stating it wrongly sends every
# call in the wrong direction.
COLOUR_GUIDE = [
    ["green", "vegetation — brighter and more saturated with denser canopy"],
    ["tan / pink", "bare soil, harvested field, dry fallow"],
    ["flat olive", "often plantation — uniform where forest is mottled"],
    ["near black", "water or deep shadow"],
]


PAGE = r"""<title>__DISTRICT__ — reference interpretation, author __AUTHOR__</title>
<style>
:root{--bg:#12151a;--fg:#e8eaed;--dim:#8b93a1;--line:#2a2f38;--hl:#5aa9e6;
      --ok:#7bd88f;--warn:#e6a45a;--panel:#1a1e25}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--fg);
  font:14px/1.5 system-ui,-apple-system,Segoe UI,sans-serif}
header{position:sticky;top:0;background:var(--bg);border-bottom:1px solid var(--line);
  padding:9px 16px;display:flex;gap:12px;align-items:center;flex-wrap:wrap;z-index:20}
#bar{flex:1;height:5px;background:var(--line);border-radius:3px;min-width:120px}
#fill{height:100%;width:0;background:var(--hl);border-radius:3px;transition:width .2s}
.wrap{display:grid;grid-template-columns:1fr 320px;gap:18px;padding:16px;
  max-width:1400px;margin:0 auto}
@media(max-width:1000px){.wrap{grid-template-columns:1fr}}
.chips{display:grid;grid-template-columns:repeat(4,1fr);gap:10px;margin:12px 0}
.chip{text-align:center}
.chip img{width:100%;image-rendering:pixelated;border:1px solid var(--line);
  border-radius:4px;display:block;cursor:zoom-in}
.chip .cap{color:var(--dim);font-size:12px;margin-top:4px}
.cross{position:relative}
.cross:after{content:"";position:absolute;left:50%;top:50%;width:15px;height:15px;
  margin:-8px 0 0 -8px;border:1.5px solid #ffe066;border-radius:50%;
  box-shadow:0 0 0 1px rgba(0,0,0,.6);pointer-events:none}
.ask{margin:14px 0 7px;font-size:15px}
.ask b{color:var(--hl)}
.opts{display:flex;gap:8px;flex-wrap:wrap}
.opt{border:1px solid var(--line);border-radius:6px;padding:8px 13px;cursor:pointer;
  background:var(--panel)}
.opt:hover{border-color:var(--hl)}
.opt.on{border-color:var(--hl);background:#1f2a35}
kbd{background:#2a2f38;border-radius:3px;padding:1px 6px;margin-right:6px;
  font:12px ui-monospace,monospace}
.meta{color:var(--dim);font-size:13px}
.meta a{color:var(--hl)}
svg.spark{width:100%;height:104px;background:var(--panel);border-radius:4px;
  border:1px solid var(--line)}
button,select{background:var(--panel);color:var(--fg);border:1px solid var(--line);
  border-radius:6px;padding:6px 11px;cursor:pointer;font-size:13px}
button:hover,select:hover{border-color:var(--hl)}
input#notes{width:100%;margin:7px 0 3px;padding:8px 11px;background:var(--panel);
  color:var(--fg);border:1px solid var(--line);border-radius:6px;font-size:14px}
input#notes:focus{outline:none;border-color:var(--hl)}
.panel{background:var(--panel);border:1px solid var(--line);border-radius:8px;
  padding:12px 14px;margin-bottom:14px}
.panel h3{margin:0 0 8px;font-size:13px;text-transform:uppercase;
  letter-spacing:.06em;color:var(--dim)}
.panel dl{margin:0}
.panel dt{font-weight:600;margin-top:8px;font-size:13px}
.panel dt:first-child{margin-top:0}
.panel dd{margin:2px 0 0;color:var(--dim);font-size:12.5px;line-height:1.45}
.swatch{display:inline-block;width:11px;height:11px;border-radius:2px;
  margin-right:6px;border:1px solid #0006}
.tally td{padding:2px 0;font-size:12.5px}
.tally td:last-child{text-align:right;color:var(--dim)}
.flag{color:var(--warn)}
#zoom{position:fixed;inset:0;background:#000d;display:none;z-index:60;
  align-items:center;justify-content:center;cursor:zoom-out}
#zoom img{max-width:88vw;max-height:82vh;image-rendering:pixelated;
  border:1px solid var(--line);border-radius:6px}
#zoom .z{position:relative}
#zoom .z:after{content:"";position:absolute;left:50%;top:50%;width:34px;height:34px;
  margin:-18px 0 0 -18px;border:2px solid #ffe066;border-radius:50%}
#help{position:fixed;inset:0;background:#000d;display:none;z-index:70;
  align-items:center;justify-content:center;padding:24px}
#help .box{background:var(--panel);border:1px solid var(--line);border-radius:10px;
  padding:20px 24px;max-width:560px}
#help table{border-collapse:collapse}
#help td{padding:4px 10px 4px 0;font-size:13px}
</style>

<header>
  <b>__DISTRICT__</b><span class="meta">author __AUTHOR__</span>
  <div id="bar"><div id="fill"></div></div>
  <span id="count" class="meta"></span>
  <select id="filter" onchange="applyFilter()">
    <option value="all">all points</option>
    <option value="todo">not yet done</option>
    <option value="kappa">only the shared subset</option>
    <option value="plantation">called plantation</option>
    <option value="natural_forest">called natural forest</option>
    <option value="low">low confidence</option>
  </select>
  <button onclick="document.getElementById('file').click()">Import CSV</button>
  <input type="file" id="file" accept=".csv" style="display:none"
         onchange="importCsv(this)">
  <button onclick="exportCsv()">Export CSV</button>
  <button onclick="jump()">Go to&hellip;</button>
  <button onclick="toggleHelp()">?</button>
</header>

<div class="wrap">
  <div>
    <div class="meta" id="hdr"></div>
    <div class="chips" id="chips"></div>
    <div id="traj"></div>
    <div class="ask" id="ask"></div>
    <div class="opts" id="opts"></div>
    <div class="ask">Confidence</div>
    <div class="opts" id="conf"></div>
    <div class="ask">Notes</div>
    <div class="opts" id="tags"></div>
    <input id="notes" placeholder="why it was hard — reconciliation reads this">
    <p class="meta">
      <kbd>0</kbd>&ndash;<kbd>3</kbd> class &nbsp; <kbd>h</kbd><kbd>m</kbd><kbd>l</kbd>
      confidence &nbsp; <kbd>n</kbd> notes &nbsp; <kbd>z</kbd> zoom &nbsp;
      <kbd>&larr;</kbd><kbd>&rarr;</kbd> move &nbsp; <kbd>?</kbd> help.
      Saved in this browser &mdash; export before closing.
    </p>
  </div>

  <aside>
    <div class="panel" id="legend"></div>
    <div class="panel" id="colours"></div>
    <div class="panel" id="tally"></div>
  </aside>
</div>

<div id="zoom" onclick="this.style.display='none'"><div class="z"><img id="zimg"></div></div>
<div id="help" onclick="this.style.display='none'"><div class="box">
  <h3>Keys</h3>
  <table>
    <tr><td><kbd>0</kbd><kbd>1</kbd><kbd>2</kbd><kbd>3</kbd></td><td>class &mdash; asked twice, T0 then T3</td></tr>
    <tr><td><kbd>h</kbd><kbd>m</kbd><kbd>l</kbd></td><td>confidence, defaults to high</td></tr>
    <tr><td><kbd>n</kbd></td><td>jump into notes, <kbd>Esc</kbd> to leave</td></tr>
    <tr><td><kbd>z</kbd></td><td>zoom the chips</td></tr>
    <tr><td><kbd>u</kbd></td><td>undo the last class on this point</td></tr>
    <tr><td><kbd>&larr;</kbd><kbd>&rarr;</kbd></td><td>previous / next</td></tr>
  </table>
  <p class="meta">Use <b>low</b> confidence freely and say why in notes. A forced
  confident answer you do not believe turns a known limitation into a hidden error.</p>
</div></div>

<script>
const ALL_POINTS=__POINTS__, CHIPS=__CHIPS__, TRAJ=__TRAJ__;
const EPOCHS=__EPOCHS__, CLASSES=__CLASSES__, TAGS=__TAGS__;
const LEGEND=__LEGEND__, COLOURS=__COLOURS__, DISTRICT="__DISTRICT__";
const KEY="ecovision-__DISTRICT__-__AUTHOR__";
const NAME2CODE=Object.fromEntries(Object.entries(CLASSES).map(([k,v])=>[v,+k]));

let store=JSON.parse(localStorage.getItem(KEY)||"{}");
let POINTS=ALL_POINTS, i=0, stage=0;
const typing=()=>document.activeElement===document.getElementById("notes");
const save=()=>localStorage.setItem(KEY,JSON.stringify(store));
const rec=p=>store[p.point_id]||(store[p.point_id]={});

function applyFilter(){
  const v=document.getElementById("filter").value;
  const keep=p=>{
    const r=store[p.point_id]||{};
    if(v==="all")return true;
    if(v==="todo")return r.class_t3==null;
    if(v==="kappa")return !!p.kappa_subset;
    if(v==="low")return r.confidence==="low";
    return CLASSES[r.class_t3]===v;
  };
  const next=ALL_POINTS.filter(keep);
  if(!next.length){alert("nothing matches that filter");
    document.getElementById("filter").value="all";return}
  POINTS=next;i=0;stage=0;render();
}

function spark(t){
  if(!t)return"";
  const w=960,h=104,pad=8,ys=t.years,n=ys.length;
  let out='<svg class="spark" viewBox="0 0 '+w+' '+h+'">';
  for(const pair of [["ndvi","#7bd88f"],["nbr","#e6a45a"]]){
    const v=t[pair[0]];let d="",started=false;
    for(let j=0;j<n;j++){
      if(v[j]==null)continue;
      const x=pad+j*(w-2*pad)/(n-1), y=h-pad-((v[j]+1)/2)*(h-2*pad);
      d+=(started?"L":"M")+x.toFixed(1)+" "+y.toFixed(1);started=true;
    }
    out+='<path d="'+d+'" fill="none" stroke="'+pair[1]+'" stroke-width="1.6"/>';
  }
  for(const e of Object.keys(EPOCHS)){
    const j=ys.indexOf(EPOCHS[e]);if(j<0)continue;
    const x=pad+j*(w-2*pad)/(n-1);
    out+='<line x1="'+x+'" y1="0" x2="'+x+'" y2="'+h+'" stroke="#5aa9e6" stroke-width="1" stroke-dasharray="3 3"/>';
    out+='<text x="'+(x+3)+'" y="12" fill="#8b93a1" font-size="11">'+e+'</text>';
  }
  out+='<text x="8" y="'+(h-4)+'" fill="#8b93a1" font-size="11">'+ys[0]+'</text>';
  out+='<text x="'+(w-42)+'" y="'+(h-4)+'" fill="#8b93a1" font-size="11">'+ys[n-1]+'</text>';
  out+='<text x="'+(w-190)+'" y="12" fill="#7bd88f" font-size="11">NDVI</text>';
  out+='<text x="'+(w-142)+'" y="12" fill="#e6a45a" font-size="11">NBR</text>';
  return out+"</svg>";
}

function panels(){
  const rows=(LEGEND._all||[]).concat(LEGEND[DISTRICT]||[]);
  document.getElementById("legend").innerHTML=
    "<h3>What the classes mean</h3><dl>"+
    rows.map(r=>"<dt>"+r[0]+"</dt><dd>"+r[1]+"</dd>").join("")+"</dl>";
  const sw={"green":"#4a8f3c","tan / pink":"#c9a07a","flat olive":"#77803f",
            "near black":"#14181d"};
  document.getElementById("colours").innerHTML=
    "<h3>Reading the false colour</h3><dl>"+
    COLOURS.map(r=>'<dt><span class="swatch" style="background:'+(sw[r[0]]||"#555")+
      '"></span>'+r[0]+"</dt><dd>"+r[1]+"</dd>").join("")+"</dl>";
}

/* Your own running tally. It shows what YOU have called, never what any
   map says — a distribution that is obviously wrong becomes visible after
   thirty points instead of after five hundred, and it does so without
   handing you the answer. */
function tally(){
  const done=ALL_POINTS.filter(p=>(store[p.point_id]||{}).class_t3!=null);
  const c={};
  for(const p of done){const n=CLASSES[store[p.point_id].class_t3];c[n]=(c[n]||0)+1}
  const low=done.filter(p=>store[p.point_id].confidence==="low").length;
  let html="<h3>Your calls so far (T3)</h3><table class='tally' width='100%'>";
  for(const n of Object.values(CLASSES)){
    const v=c[n]||0, pct=done.length?100*v/done.length:0;
    html+="<tr><td>"+n+"</td><td>"+v+" &middot; "+pct.toFixed(0)+"%</td></tr>";
  }
  html+='<tr><td class="flag">low confidence</td><td>'+low+"</td></tr>";
  html+="<tr><td>interpreted</td><td>"+done.length+" / "+ALL_POINTS.length+"</td></tr>";
  document.getElementById("tally").innerHTML=html+"</table>";
}

function render(){
  const p=POINTS[i],r=rec(p),c=CHIPS[p.point_id]||{};
  document.getElementById("hdr").innerHTML=
    "<b>"+p.point_id+"</b> &nbsp; stratum <b>"+p.stratum+"</b> &nbsp; "+
    p.lat.toFixed(5)+", "+p.lon.toFixed(5)+" &nbsp; "+
    '<a target="_blank" href="https://www.google.com/maps/@?api=1&map_action=map&center='+
      p.lat+","+p.lon+'&zoom=17&basemap=satellite">high-res now (T3) &#8599;</a> &nbsp; '+
    '<a target="_blank" href="https://earth.google.com/web/@'+p.lat+","+p.lon+
      ',0a,1200d,35y,0h,0t,0r">Earth history &#8599;</a>'+
    (p.kappa_subset?' &nbsp; <span class="flag">shared &mdash; both authors</span>':"");

  document.getElementById("chips").innerHTML=Object.keys(EPOCHS).map(e=>
    '<div class="chip"><div class="cross">'+
    (c[e]?'<img src="data:image/png;base64,'+c[e]+'" onclick="zoom(\''+e+'\')">'
        :'<div style="height:140px;border:1px dashed #2a2f38;border-radius:4px"></div>')+
    '</div><div class="cap">'+e+" &middot; "+EPOCHS[e]+"</div></div>").join("");
  document.getElementById("traj").innerHTML=spark(TRAJ[p.point_id]);

  const field=stage===0?"class_t0":"class_t3", ep=stage===0?"T0":"T3";
  document.getElementById("ask").innerHTML=
    "Class at <b>"+ep+" ("+EPOCHS[ep]+")</b>"+
    (r[field]!=null?' &nbsp;<span style="color:var(--ok)">&#10003; '+
      CLASSES[r[field]]+"</span>":"");
  document.getElementById("opts").innerHTML=Object.keys(CLASSES).map(k=>
    '<div class="opt '+(r[field]==k?"on":"")+'" onclick="pick('+k+')">'+
    "<kbd>"+k+"</kbd>"+CLASSES[k]+"</div>").join("");

  const conf=r.confidence||"high";
  document.getElementById("conf").innerHTML=
    [["h","high"],["m","medium"],["l","low"]].map(kv=>
      '<div class="opt '+(conf===kv[1]?"on":"")+'" onclick="setConf(\''+kv[1]+'\')">'+
      "<kbd>"+kv[0]+"</kbd>"+kv[1]+"</div>").join("");
  document.getElementById("tags").innerHTML=TAGS.map(t=>
    '<div class="opt '+((r.notes||"").includes(t[1])?"on":"")+'" '+
    "onclick=\"tag('"+t[1]+"')\"><kbd>"+t[0]+"</kbd>"+t[1]+"</div>").join("");
  document.getElementById("notes").value=r.notes||"";

  const n=POINTS.filter(q=>(store[q.point_id]||{}).class_t3!=null).length;
  document.getElementById("fill").style.width=(100*n/POINTS.length)+"%";
  document.getElementById("count").textContent=(i+1)+"/"+POINTS.length+" · "+n+" done";
  tally();
}

function pick(k){
  const r=rec(POINTS[i]);
  r[stage===0?"class_t0":"class_t3"]=k;save();
  if(stage===0){stage=1}else{stage=0;if(i<POINTS.length-1)i++}
  render();
}
function setConf(v){rec(POINTS[i]).confidence=v;save();render()}
function tag(t){
  const r=rec(POINTS[i]);
  const parts=(r.notes||"").split(";").map(s=>s.trim()).filter(Boolean);
  const at=parts.indexOf(t);
  if(at>=0)parts.splice(at,1);else parts.push(t);
  r.notes=parts.join("; ");save();render();
}
function zoom(e){
  const c=CHIPS[POINTS[i].point_id]||{};
  if(!c[e])return;
  document.getElementById("zimg").src="data:image/png;base64,"+c[e];
  document.getElementById("zoom").style.display="flex";
}
function toggleHelp(){
  const h=document.getElementById("help");
  h.style.display=h.style.display==="flex"?"none":"flex";
}
function go(d){i=Math.max(0,Math.min(POINTS.length-1,i+d));stage=0;render()}
function jump(){
  const v=prompt("point number or id");if(!v)return;
  const n=parseInt(v,10);
  if(!isNaN(n)&&String(n)===v.trim()){i=Math.max(0,Math.min(POINTS.length-1,n-1))}
  else{const j=POINTS.findIndex(p=>p.point_id===v.trim().toUpperCase());if(j>=0)i=j}
  stage=0;render();
}

document.getElementById("notes").addEventListener("input",function(e){
  rec(POINTS[i]).notes=e.target.value;save();
});
document.getElementById("notes").addEventListener("keydown",function(e){
  if(e.key==="Escape"||e.key==="Enter")e.target.blur();
});
document.addEventListener("keydown",function(e){
  if(typing())return;
  if(e.key>="0"&&e.key<="3")pick(+e.key);
  else if(e.key==="h")setConf("high");
  else if(e.key==="m")setConf("medium");
  else if(e.key==="l")setConf("low");
  else if(e.key==="n"){e.preventDefault();document.getElementById("notes").focus()}
  else if(e.key==="z")zoom("T3");
  else if(e.key==="?")toggleHelp();
  else if(e.key==="Escape"){
    document.getElementById("zoom").style.display="none";
    document.getElementById("help").style.display="none";
  }
  else if(TAGS.some(t=>t[0]===e.key))tag(TAGS.find(t=>t[0]===e.key)[1]);
  else if(e.key==="u"){const r=rec(POINTS[i]);
    if(stage===1){delete r.class_t0;stage=0}else{delete r.class_t3}save();render()}
  else if(e.key==="ArrowRight")go(1);
  else if(e.key==="ArrowLeft")go(-1);
});

function splitCsvLine(line){
  const out=[];let cur="",q=false;
  for(let k=0;k<line.length;k++){
    const ch=line[k];
    if(q){
      if(ch==='"'&&line[k+1]==='"'){cur+='"';k++}
      else if(ch==='"'){q=false}
      else cur+=ch;
    }
    else if(ch==='"')q=true;
    else if(ch===","){out.push(cur);cur=""}
    else cur+=ch;
  }
  out.push(cur);return out;
}

/* Import exists so earlier work is never retyped. Points are matched by
   point_id and anything not in this sample is ignored, which is what lets
   a full-sample CSV be loaded into a reduced-sample page. */
function importCsv(input){
  const f=input.files[0];if(!f)return;
  const reader=new FileReader();
  reader.onload=function(){
    const lines=reader.result.split(/\r?\n/).filter(Boolean);
    const head=splitCsvLine(lines[0]);
    const col=function(n){return head.indexOf(n)};
    const known=new Set(ALL_POINTS.map(p=>p.point_id));
    let hit=0,skip=0;
    for(const line of lines.slice(1)){
      const fields=splitCsvLine(line);
      const id=fields[col("point_id")];
      if(!known.has(id)){skip++;continue}
      const r=store[id]||(store[id]={});
      const t0=NAME2CODE[fields[col("class_t0")]];
      const t3=NAME2CODE[fields[col("class_t3")]];
      if(t0!=null)r.class_t0=t0;
      if(t3!=null)r.class_t3=t3;
      const cf=fields[col("confidence")]; if(cf)r.confidence=cf;
      const nt=col("notes")>=0?fields[col("notes")]:""; if(nt)r.notes=nt;
      hit++;
    }
    save();i=0;stage=0;render();
    alert("imported "+hit+" points ("+skip+" not in this sample)");
  };
  reader.readAsText(f);
}

function exportCsv(){
  const head=["point_id","district","stratum","lon","lat","class_t0","class_t3",
              "confidence","notes"];
  const groups={};
  for(const p of ALL_POINTS){(groups[p.out_file]=groups[p.out_file]||[]).push(p)}
  for(const name of Object.keys(groups)){
    const rows=[head.join(",")];
    for(const p of groups[name]){
      const r=store[p.point_id]||{},done=r.class_t3!=null;
      rows.push([p.point_id,p.district,p.stratum,p.lon,p.lat,
        r.class_t0!=null?CLASSES[r.class_t0]:"",
        done?CLASSES[r.class_t3]:"",
        done?(r.confidence||"high"):"",
        '"'+(r.notes||"").replace(/"/g,'""')+'"'].join(","));
    }
    const a=document.createElement("a");
    a.href=URL.createObjectURL(new Blob([rows.join("\n")],{type:"text/csv"}));
    a.download=name;a.click();
  }
}

panels();render();
</script>
"""


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--district", choices=pp.DISTRICTS, required=True)
    parser.add_argument("--author", choices=["a", "b"], required=True)
    parser.add_argument("--no-trajectory", dest="trajectory", action="store_false",
                        help="skip the annual NDVI/NBR series (faster, weakens every T0 call)")
    parser.add_argument("--limit", type=int, help="first N points only, for a quick look")
    args = parser.parse_args()

    try:
        ee.Initialize(project=pp.PROJECT)
    except Exception as exc:
        sys.exit(f"Earth Engine init failed: {exc}")

    points = load_points(args.district, args.author)
    if args.limit:
        points = points.head(args.limit)
    print(f"{args.district}: {len(points):,} points from "
          f"{len(sample_files(args.district))} sample file(s)")

    chips = build_chips(args.district, points)
    missing = sum(1 for v in chips.values() if len(v) < len(pp.EPOCHS))
    if missing:
        print(f"  {missing} points have an incomplete chip set — re-run to fill them")

    traj = build_trajectory(args.district, points) if args.trajectory else {}

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    out = OUT_DIR / f"{args.district}_author_{args.author}.html"
    cols = ["point_id", "district", "stratum", "lon", "lat", "out_file", "kappa_subset"]

    # Token replacement rather than str.format: the template is mostly
    # JavaScript and CSS, and doubling every brace to survive format() is
    # how a page silently stops working.
    tokens = {
        "__POINTS__": json.dumps(points[cols].to_dict("records")),
        "__CHIPS__": json.dumps(chips),
        "__TRAJ__": json.dumps(traj),
        "__EPOCHS__": json.dumps(pp.EPOCHS),
        "__CLASSES__": json.dumps({str(k): v for k, v in CLASSES.items()}),
        "__TAGS__": json.dumps(TAGS.get(args.district, [])),
        "__LEGEND__": json.dumps(LEGEND),
        "__COLOURS__": json.dumps(COLOUR_GUIDE),
        "__DISTRICT__": args.district,
        "__AUTHOR__": args.author,
    }
    page = PAGE
    for token, value in tokens.items():
        page = page.replace(token, value)
    out.write_text(page, encoding="utf-8")

    print(f"\nWritten: {out.relative_to(REPO)}  ({out.stat().st_size / 1e6:.1f} MB)")
    print("Open in a browser. Progress is kept in that browser's local storage —")
    print("export before closing, and keep author a and author b in different")
    print("browser profiles so they cannot see each other's calls.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
