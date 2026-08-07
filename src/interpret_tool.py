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

# SWIR1/NIR/red. Forest is deep red-brown, tea a flatter olive, bare soil
# cyan-white, water near black. Reflectance is already in [0, 1] after
# preprocess.clamp_reflectance, so the stretch is in reflectance units.
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
    """Main sample plus any stratum top-ups drawn separately."""
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
        stem = path.stem.replace("reference_sample_", "")
        frame["out_file"] = f"interpretation_{stem}_author_{author}.csv"
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


PAGE = """<title>{district} \u2014 reference interpretation, author {author}</title>
<style>
:root{{--bg:#12151a;--fg:#e8eaed;--dim:#8b93a1;--line:#2a2f38;--hl:#5aa9e6}}
*{{box-sizing:border-box}}
body{{margin:0;background:var(--bg);color:var(--fg);
  font:14px/1.5 system-ui,-apple-system,Segoe UI,sans-serif}}
header{{position:sticky;top:0;background:var(--bg);border-bottom:1px solid var(--line);
  padding:10px 18px;display:flex;gap:18px;align-items:center;flex-wrap:wrap;z-index:9}}
#bar{{flex:1;height:5px;background:var(--line);border-radius:3px;min-width:140px}}
#fill{{height:100%;width:0;background:var(--hl);border-radius:3px}}
main{{padding:18px;max-width:1000px;margin:0 auto}}
.chips{{display:grid;grid-template-columns:repeat(4,1fr);gap:12px;margin:14px 0}}
.chip{{text-align:center}}
.chip img{{width:100%;image-rendering:pixelated;border:1px solid var(--line);
  border-radius:4px;display:block}}
.chip .cap{{color:var(--dim);font-size:12px;margin-top:5px}}
.cross{{position:relative}}
.cross:after{{content:"";position:absolute;left:50%;top:50%;width:15px;height:15px;
  margin:-8px 0 0 -8px;border:1.5px solid #ffe066;border-radius:50%;
  box-shadow:0 0 0 1px rgba(0,0,0,.6)}}
.ask{{margin:16px 0 8px;font-size:16px}}
.ask b{{color:var(--hl)}}
.opts{{display:flex;gap:10px;flex-wrap:wrap}}
.opt{{border:1px solid var(--line);border-radius:6px;padding:9px 14px;cursor:pointer;
  background:#1a1e25}}
.opt:hover{{border-color:var(--hl)}}
.opt kbd{{background:#2a2f38;border-radius:3px;padding:1px 6px;margin-right:7px}}
.meta{{color:var(--dim);font-size:13px}}
.meta a{{color:var(--hl)}}
svg{{width:100%;height:110px;background:#1a1e25;border-radius:4px;border:1px solid var(--line)}}
button{{background:#1a1e25;color:var(--fg);border:1px solid var(--line);
  border-radius:6px;padding:7px 13px;cursor:pointer;font-size:13px}}
button:hover{{border-color:var(--hl)}}
.done{{color:#7bd88f}}
.opt.on{{border-color:var(--hl);background:#1f2a35}}
input#notes{{width:100%;margin:8px 0 4px;padding:9px 11px;background:#1a1e25;
  color:var(--fg);border:1px solid var(--line);border-radius:6px;font-size:14px}}
input#notes:focus{{outline:none;border-color:var(--hl)}}
</style>
<header>
  <b>{district}</b><span class="meta">author {author}</span>
  <div id="bar"><div id="fill"></div></div>
  <span id="count" class="meta"></span>
  <button onclick="exportCsv()">Export CSV</button>
  <button onclick="jump()">Go to\u2026</button>
</header>
<main>
  <div class="meta" id="hdr"></div>
  <div class="chips" id="chips"></div>
  <div id="traj"></div>
  <div class="ask" id="ask"></div>
  <div class="opts" id="opts"></div>
  <div class="ask">Confidence</div>
  <div class="opts" id="conf"></div>
  <div class="ask">Notes</div>
  <div class="opts" id="tags"></div>
  <input id="notes" placeholder="reason for a low call, boundary cases, anything reconciliation will need">
  <p class="meta">
    <kbd>0</kbd>-<kbd>3</kbd> classify &nbsp; <kbd>h</kbd>/<kbd>m</kbd>/<kbd>l</kbd> confidence &nbsp;
    <kbd>u</kbd> undo &nbsp; <kbd>\u2190</kbd><kbd>\u2192</kbd> navigate &nbsp;
    <kbd>Esc</kbd> leave the notes box.
    Progress saves in this browser automatically \u2014 export before closing.
  </p>
</main>
<script>
const POINTS={points};
const CHIPS={chips};
const TRAJ={traj};
const EPOCHS={epochs};
const CLASSES={classes};
const TAGS={tags};
const KEY="ecovision-{district}-{author}";
let store=JSON.parse(localStorage.getItem(KEY)||"{{}}");
let i=0,stage=0;
const typing=()=>document.activeElement===document.getElementById("notes");

function save(){{localStorage.setItem(KEY,JSON.stringify(store))}}
function rec(p){{return store[p.point_id]||(store[p.point_id]={{}})}}

function spark(t){{
  if(!t)return"";
  const w=960,h=110,pad=8;
  const ys=t.years,n=ys.length;
  let out=`<svg viewBox="0 0 ${{w}} ${{h}}">`;
  for(const[k,col]of[["ndvi","#7bd88f"],["nbr","#e6a45a"]]){{
    const v=t[k];let d="",started=false;
    for(let j=0;j<n;j++){{
      if(v[j]==null)continue;
      const x=pad+j*(w-2*pad)/(n-1);
      const y=h-pad-((v[j]+1)/2)*(h-2*pad);
      d+=(started?"L":"M")+x.toFixed(1)+" "+y.toFixed(1);started=true;
    }}
    out+=`<path d="${{d}}" fill="none" stroke="${{col}}" stroke-width="1.6"/>`;
  }}
  for(const e of Object.keys(EPOCHS)){{
    const j=ys.indexOf(EPOCHS[e]);if(j<0)continue;
    const x=pad+j*(w-2*pad)/(n-1);
    out+=`<line x1="${{x}}" y1="0" x2="${{x}}" y2="${{h}}" stroke="#5aa9e6" stroke-width="1" stroke-dasharray="3 3"/>`;
    out+=`<text x="${{x+3}}" y="13" fill="#8b93a1" font-size="11">${{e}}</text>`;
  }}
  out+=`<text x="8" y="${{h-4}}" fill="#8b93a1" font-size="11">${{ys[0]}}</text>`;
  out+=`<text x="${{w-40}}" y="${{h-4}}" fill="#8b93a1" font-size="11">${{ys[n-1]}}</text>`;
  out+=`<text x="${{w-190}}" y="13" fill="#7bd88f" font-size="11">NDVI</text>`;
  out+=`<text x="${{w-140}}" y="13" fill="#e6a45a" font-size="11">NBR</text>`;
  return out+"</svg>";
}}

function render(){{
  const p=POINTS[i],r=rec(p),c=CHIPS[p.point_id]||{{}};
  document.getElementById("hdr").innerHTML=
    `<b>${{p.point_id}}</b> &nbsp; stratum <b>${{p.stratum}}</b> &nbsp; `+
    `${{p.lat.toFixed(5)}}, ${{p.lon.toFixed(5)}} &nbsp; `+
    `<a target="_blank" href="https://www.google.com/maps/@?api=1&map_action=map&center=${{p.lat}},${{p.lon}}&zoom=17&basemap=satellite">high-res \u2197</a>`+
    (r.flag?' &nbsp; <span style="color:#e6a45a">flagged</span>':'');
  document.getElementById("chips").innerHTML=Object.keys(EPOCHS).map(e=>
    `<div class="chip"><div class="cross">`+
    (c[e]?`<img src="data:image/png;base64,${{c[e]}}">`:`<div style="height:150px;border:1px dashed #2a2f38;border-radius:4px"></div>`)+
    `</div><div class="cap">${{e}} \u00b7 ${{EPOCHS[e]}}</div></div>`).join("");
  document.getElementById("traj").innerHTML=spark(TRAJ[p.point_id]);

  const field=stage===0?"class_t0":"class_t3";
  const ep=stage===0?"T0":"T3";
  document.getElementById("ask").innerHTML=
    `Class at <b>${{ep}} (${{EPOCHS[ep]}})</b>`+
    (r[field]!=null?` &nbsp;<span class="done">\u2713 ${{CLASSES[r[field]]}}</span>`:"");
  document.getElementById("opts").innerHTML=Object.keys(CLASSES).map(k=>
    `<div class="opt" onclick="pick(${{k}})"><kbd>${{k}}</kbd>${{CLASSES[k]}}</div>`).join("");

  // Confidence defaults to high so the common case costs no keystrokes.
  // The protocol says use `low` freely — a forced confident-looking call
  // turns a known limitation into a hidden error — so m and l are one key.
  const conf=r.confidence||"high";
  document.getElementById("conf").innerHTML=
    [["h","high"],["m","medium"],["l","low"]].map(([k,v])=>
      `<div class="opt ${{conf===v?"on":""}}" onclick="setConf('${{v}}')">`+
      `<kbd>${{k}}</kbd>${{v}}</div>`).join("");
  document.getElementById("tags").innerHTML=TAGS.map(t=>
    `<div class="opt ${{(r.notes||"").includes(t[1])?"on":""}}" `+
    `onclick="tag('${{t[1]}}')"><kbd>${{t[0]}}</kbd>${{t[1]}}</div>`).join("");
  document.getElementById("notes").value=r.notes||"";

  const n=POINTS.filter(q=>(store[q.point_id]||{{}}).class_t3!=null).length;
  document.getElementById("fill").style.width=(100*n/POINTS.length)+"%";
  document.getElementById("count").textContent=`${{i+1}}/${{POINTS.length}} \u00b7 ${{n}} complete`;
}}

function pick(k){{
  const p=POINTS[i],r=rec(p);
  r[stage===0?"class_t0":"class_t3"]=k;save();
  if(stage===0){{stage=1}}else{{stage=0;if(i<POINTS.length-1)i++}}
  render();
}}
function setConf(v){{rec(POINTS[i]).confidence=v;save();render()}}
function tag(t){{
  const r=rec(POINTS[i]);
  const parts=(r.notes||"").split(";").map(s=>s.trim()).filter(Boolean);
  const at=parts.indexOf(t);
  if(at>=0)parts.splice(at,1);else parts.push(t);
  r.notes=parts.join("; ");save();render();
}}
document.getElementById("notes").addEventListener("input",e=>{{
  rec(POINTS[i]).notes=e.target.value;save();
}});
document.getElementById("notes").addEventListener("keydown",e=>{{
  if(e.key==="Escape"||e.key==="Enter")e.target.blur();
}});
function go(d){{i=Math.max(0,Math.min(POINTS.length-1,i+d));stage=0;render()}}
function jump(){{
  const v=prompt("point number or id");if(!v)return;
  const n=parseInt(v,10);
  if(!isNaN(n)&&String(n)===v.trim()){{i=Math.max(0,Math.min(POINTS.length-1,n-1))}}
  else{{const j=POINTS.findIndex(p=>p.point_id===v.trim().toUpperCase());if(j>=0)i=j}}
  stage=0;render();
}}
document.addEventListener("keydown",e=>{{
  // Every shortcut is a printable character, so without this guard the
  // notes box is unusable: typing "low canopy" would reclassify the point.
  if(typing())return;
  if(e.key>="0"&&e.key<="3")pick(+e.key);
  else if(e.key==="h"||e.key==="m"||e.key==="l")
    setConf({{h:"high",m:"medium",l:"low"}}[e.key]);
  else if(e.key==="n"){{e.preventDefault();document.getElementById("notes").focus()}}
  else if(TAGS.some(t=>t[0]===e.key))tag(TAGS.find(t=>t[0]===e.key)[1]);
  else if(e.key==="u"){{const r=rec(POINTS[i]);
    if(stage===1){{delete r.class_t0;stage=0}}else{{delete r.class_t3}}save();render()}}
  else if(e.key==="ArrowRight")go(1);
  else if(e.key==="ArrowLeft")go(-1);
}});

function exportCsv(){{
  // One file per source sample, not one merged file. A top-up is a
  // separate second-stage sample and merging it into the main file
  // corrupts the Olofsson weights silently.
  const head=["point_id","district","stratum","lon","lat","class_t0","class_t3","confidence","notes"];
  const groups={{}};
  for(const p of POINTS){{
    (groups[p.out_file]=groups[p.out_file]||[]).push(p);
  }}
  for(const [name,points] of Object.entries(groups)){{
    const rows=[head.join(",")];
    for(const p of points){{
      const r=store[p.point_id]||{{}};
      const done=r.class_t3!=null;
      // Quoted: notes contain semicolons and commas by design.
      rows.push([p.point_id,p.district,p.stratum,p.lon,p.lat,
        r.class_t0!=null?CLASSES[r.class_t0]:"",
        done?CLASSES[r.class_t3]:"",
        done?(r.confidence||"high"):"",
        '"'+(r.notes||"").replace(/"/g,'""')+'"'].join(","));
    }}
    const blob=new Blob([rows.join("\\n")],{{type:"text/csv"}});
    const a=document.createElement("a");
    a.href=URL.createObjectURL(blob);
    a.download=name;a.click();
  }}
}}
render();
</script>
"""


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--district", choices=pp.DISTRICTS, required=True)
    parser.add_argument("--author", choices=["a", "b"], required=True)
    parser.add_argument("--trajectory", action="store_true",
                        help="annual NDVI/NBR series — slow, and required for Bandarban (rule 9)")
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
    if not args.trajectory and args.district == "bandarban":
        print("\n  WARNING: Bandarban without --trajectory. Jhum cannot be told from\n"
              "  permanent conversion by a pair of dates (CLAUDE.md rule 9), so the\n"
              "  interpreter has no way to make that call from the chips alone.")

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    out = OUT_DIR / f"{args.district}_author_{args.author}.html"
    cols = ["point_id", "district", "stratum", "lon", "lat", "out_file"]
    out.write_text(
        PAGE.format(
            district=args.district,
            author=args.author,
            points=json.dumps(points[cols].to_dict("records")),
            chips=json.dumps(chips),
            traj=json.dumps(traj),
            epochs=json.dumps(pp.EPOCHS),
            classes=json.dumps({str(k): v for k, v in CLASSES.items()}),
            tags=json.dumps(TAGS.get(args.district, [])),
        ),
        encoding="utf-8",
    )
    print(f"\nWritten: {out.relative_to(REPO)}  ({out.stat().st_size / 1e6:.1f} MB)")
    print("Open it in a browser. Progress is kept in that browser's local")
    print("storage — export to CSV before closing, and keep author a and")
    print("author b in different browser profiles so they cannot see each")
    print("other's calls (that is what makes the kappa meaningful).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
