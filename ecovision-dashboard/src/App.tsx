import MapExplorer from "./components/MapExplorer";
import {
  CHANGE_DETECTION,
  DISTRICTS,
  GATE_4_THRESHOLD,
  JHUM,
  KAPPA,
  LINKS,
  MODEL_COMPARISON,
  NEGATIVE_RESULTS,
  STUDY,
  TEXTURE_ABLATION,
} from "./data/findings";

import studyArea from "./assets/study_area.png";
import jhumMap from "./assets/bandarban_jhum_map.png";
import adjustedLoss from "./assets/adjusted_loss.png";
import harmonisation from "./assets/harmonisation.png";
import sceneAvailability from "./assets/scene_availability.png";

const pct = (x: number) => `${(x * 100).toFixed(1)}%`;

export default function App() {
  return (
    <div className="wrap">
      <header className="masthead">
        <p className="eyebrow">
          Undergraduate thesis · Remote sensing · {STUDY.startYear}–{STUDY.endYear}
        </p>
        <h1>
          Most of what looks like deforestation in the Chittagong Hills is not
          deforestation.
        </h1>
        <p className="standfirst">
          We measured forest cover change across three districts of Bangladesh
          using Landsat, and compared classical machine learning against deep
          learning at each one. <strong>No single method won everywhere.</strong>{" "}
          Which method works depends on whether the thing you are trying to see
          is spectral, spatial, or temporal — and in Bandarban it is temporal,
          which is why the standard approach reports roughly four times the
          forest loss that actually occurred.
        </p>
        <div className="byline">
          <span>Sheikh Sulaiman Sony</span>
          <span>Jalal Uddin Mohammad Akbar</span>
          <span>Dept. of Educational Technology &amp; Engineering, UFTB</span>
        </div>
      </header>

      <div className="notice">
        <span className="tag">Provisional</span>
        <p>
          Every figure on this site derived from the reference sample is
          provisional. Two trained interpreters working from the same written
          protocol agreed at close to chance on where forest begins (Cohen's κ of{" "}
          {KAPPA[0].kappa} and {KAPPA[1].kappa} against a {GATE_4_THRESHOLD}{" "}
          threshold). Until that is reconciled these numbers are indicative, not
          final. We report them anyway, because an unreported κ is
          indistinguishable from an unmeasured one.
        </p>
      </div>

      <section id="design">
        <p className="eyebrow">The design</p>
        <h2>Three districts, chosen because forest is lost three different ways</h2>
        <p>
          Most method comparisons hold the landscape constant and vary the model.
          This one varies both. Each district contributes a different loss
          mechanism, which is what makes the interaction between the structure of
          a land-cover class and the capability of a model visible at all.
        </p>

        <div className="mechanisms">
          {DISTRICTS.map((d) => (
            <div className="mech" key={d.id}>
              <span className="district">{d.name}</span>
              <span className="area">{d.areaKm2.toLocaleString()} km²</span>
              <span className={`signal signal-${d.signal}`}>{d.signal}</span>
              <p>{d.blurb}</p>
            </div>
          ))}
        </div>

        <figure>
          <img
            src={studyArea}
            alt="Map of Bangladesh showing Gazipur, Sylhet and Bandarban districts, each also drawn at a common scale for comparison."
          />
          <figcaption>
            The three study districts in national context, drawn at a common
            scale. Total study area {STUDY.totalAreaKm2.toLocaleString()} km², about
            10.9 million Landsat pixels at 30 m.
          </figcaption>
        </figure>
      </section>

      <section id="explore">
        <p className="eyebrow">Explore</p>
        <h2>Pick a district</h2>
        <p>
          Select a district to see its measured forest extent, adjusted loss and
          whether that loss is statistically distinguishable from zero. Click the
          map or use the tabs.
        </p>
        <MapExplorer />
      </section>

      <section id="jhum">
        <p className="eyebrow">The main result</p>
        <h2>
          Of {JHUM.totalDisturbedHa.toLocaleString()} ha disturbed in Bandarban,
          only a sixth is permanent
        </h2>
        <p>
          A two-date comparison cannot tell a cleared <i>jhum</i> plot from a
          permanently converted one. It scores the same ground as loss, as gain,
          or as no change depending only on where the two dates happen to fall in
          the cycle. Fitting a trajectory to the full annual series instead —
          thirty-seven dry-season composites, {STUDY.startYear} to {STUDY.endYear}{" "}
          — separates the two, because only the trajectory shows whether the
          canopy came back.
        </p>

        <div className="headline">
          <div className="bignum">
            {(JHUM.permanentShareOfDisturbed * 100).toFixed(1)}
            <span className="unit">%</span>
          </div>
          <p>
            of disturbed land in Bandarban is permanent conversion. The remaining{" "}
            {pct(JHUM.cyclicalShareOfDisturbed)} is cyclical <i>jhum</i> that
            regrows, and {pct(JHUM.undeterminedShareOfDisturbed)} is undetermined
            because it happened too close to the end of the series to judge
            recovery. <b>A bitemporal comparison would have reported roughly four
            times the deforestation that occurred.</b>
          </p>

          <div
            className="split"
            role="img"
            aria-label={`Of disturbed land: ${pct(JHUM.permanentShareOfDisturbed)} permanent conversion, ${pct(JHUM.cyclicalShareOfDisturbed)} cyclical jhum, ${pct(JHUM.undeterminedShareOfDisturbed)} undetermined.`}
          >
            <span className="s-perm" style={{ flex: JHUM.permanentShareOfDisturbed }}>
              {pct(JHUM.permanentShareOfDisturbed)}
            </span>
            <span className="s-cyc" style={{ flex: JHUM.cyclicalShareOfDisturbed }}>
              {pct(JHUM.cyclicalShareOfDisturbed)}
            </span>
            <span className="s-und" style={{ flex: JHUM.undeterminedShareOfDisturbed }}>
              {pct(JHUM.undeterminedShareOfDisturbed)}
            </span>
          </div>
          <div className="splitkey">
            <span>Permanent conversion · 14,457 ha</span>
            <span>Cyclical jhum · 56,235 ha</span>
            <span>Undetermined · 17,431 ha</span>
          </div>
        </div>

        <figure>
          <img
            src={jhumMap}
            alt="Classified map of Bandarban. Cyclical jhum disturbance appears green, concentrated in the western hills; permanent conversion appears sparsely in red; most of the district is stable."
          />
          <figcaption>
            Disturbance classified from the annual NBR trajectory. Green is
            cyclical <i>jhum</i>, red is permanent conversion.{" "}
            <b>Displayed at 100 m by majority class; the areas quoted are
            tabulated at the native 30 m</b> — patches smaller than a display cell
            are generalised away, so the map shows where each class occurs, not
            how much.
          </figcaption>
        </figure>
      </section>

      <section id="models">
        <p className="eyebrow">Model comparison</p>
        <h2>The best model changes with the district, and it tracks training data</h2>
        <p>
          Random Forest, a U-Net, and a stacked ensemble of the two, scored on
          spatially disjoint test blocks. The ordering follows training-set size
          exactly: Random Forest wins decisively where data is scarce, loses where
          there is enough to fit a deep model, and ties in between.
        </p>

        <div className="scroll">
          <table>
            <caption>Patch-test macro F1, against Hansen-derived training labels</caption>
            <thead>
              <tr>
                <th scope="col">District</th>
                <th scope="col" className="n">Random Forest</th>
                <th scope="col" className="n">U-Net</th>
                <th scope="col" className="n">Ensemble</th>
                <th scope="col" className="n">Training patches</th>
              </tr>
            </thead>
            <tbody>
              {MODEL_COMPARISON.map((r) => (
                <tr key={r.district}>
                  <th scope="row">{r.district}</th>
                  <td className={`n ${r.winner === "rf" ? "win" : ""}`}>{r.rf.toFixed(4)}</td>
                  <td className={`n ${r.winner === "unet" ? "win" : ""}`}>{r.unet.toFixed(4)}</td>
                  <td className={`n ${r.winner === "ensemble" ? "win" : ""}`}>{r.ensemble.toFixed(4)}</td>
                  <td className="n">{r.patches}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        <h3>Texture is what makes tea visible, and only to a model that can see shape</h3>
        <p>
          Holding the architecture and the data constant and switching only the
          three GLCM texture bands in and out moves plantation F1 by{" "}
          +{TEXTURE_ABLATION.gain.toFixed(4)}, a{" "}
          {Math.round(TEXTURE_ABLATION.relativeGain * 100)}% relative gain — and
          the improvement is almost entirely confined to that one class. Random
          Forest, working pixel by pixel, scores{" "}
          {TEXTURE_ABLATION.randomForestPlantation.toFixed(4)} on the same class.
          It has no access to the planted rows and uniform canopy that define a
          tea estate, because those are properties of a neighbourhood, not a
          pixel.
        </p>

        <div className="scroll">
          <table>
            <caption>Sylhet per-class F1 — texture ablation</caption>
            <thead>
              <tr>
                <th scope="col">Run</th>
                <th scope="col" className="n">Non-forest</th>
                <th scope="col" className="n">Natural forest</th>
                <th scope="col" className="n">Plantation</th>
                <th scope="col" className="n">Water</th>
              </tr>
            </thead>
            <tbody>
              {TEXTURE_ABLATION.rows.map((r, i) => (
                <tr key={r.run}>
                  <th scope="row">{r.run}</th>
                  <td className="n">{r.nonForest.toFixed(4)}</td>
                  <td className="n">{r.forest.toFixed(4)}</td>
                  <td className={`n ${i === 0 ? "win" : ""}`}>{r.plantation.toFixed(4)}</td>
                  <td className="n">{r.water.toFixed(4)}</td>
                </tr>
              ))}
              <tr>
                <th scope="row">Random Forest (per-pixel)</th>
                <td className="n">—</td>
                <td className="n">—</td>
                <td className="n">{TEXTURE_ABLATION.randomForestPlantation.toFixed(4)}</td>
                <td className="n">—</td>
              </tr>
            </tbody>
          </table>
        </div>

        <h3>Change detection is structurally weak here</h3>
        <p>
          F1 on the change class, the headline metric because overall accuracy is
          uninformative for a minority class. NDVI differencing equals or beats
          post-classification comparison in every district — PCC accumulates error
          from both dates, so two maps agreeing with the reference at around 0.55
          cannot produce a reliable change map between them.
        </p>

        <div className="scroll">
          <table>
            <caption>Change-class F1</caption>
            <thead>
              <tr>
                <th scope="col">District</th>
                <th scope="col" className="n">Post-classification</th>
                <th scope="col" className="n">NDVI differencing</th>
                <th scope="col" className="n">Reference loss points</th>
              </tr>
            </thead>
            <tbody>
              {CHANGE_DETECTION.map((r) => (
                <tr key={r.district}>
                  <th scope="row">{r.district}</th>
                  <td className="n">{r.pcc.toFixed(3)}</td>
                  <td className={`n ${r.ndvi > r.pcc ? "win" : ""}`}>{r.ndvi.toFixed(3)}</td>
                  <td className="n">{r.referenceLoss}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>

      <section id="area">
        <p className="eyebrow">Area estimation</p>
        <h2>Two of three districts show no statistically detectable loss</h2>
        <p>
          Areas are reported through the Olofsson stratified estimator with 95%
          confidence intervals, never as raw pixel counts. The reference sample
          was reduced from a planned{" "}
          {STUDY.plannedReferencePoints.toLocaleString()} points to{" "}
          {STUDY.referencePoints} under schedule pressure, and the cost of that
          reduction is visible in the intervals rather than hidden.
        </p>

        <div className="scroll">
          <table>
            <caption>Adjusted forest loss, 1990–2024</caption>
            <thead>
              <tr>
                <th scope="col">District</th>
                <th scope="col" className="n">Adjusted loss</th>
                <th scope="col" className="n">Reference change points</th>
                <th scope="col">Excludes zero</th>
              </tr>
            </thead>
            <tbody>
              {DISTRICTS.map((d) => (
                <tr key={d.id}>
                  <th scope="row">{d.name}</th>
                  <td className="n">{d.adjustedLoss}</td>
                  <td className="n">{d.referenceChangePoints}</td>
                  <td>
                    <span className={`flag ${d.lossExcludesZero ? "yes" : "no"}`}>
                      {d.lossExcludesZero ? "Yes" : "No"}
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        <figure>
          <img
            src={adjustedLoss}
            alt="Interval plot of adjusted forest loss for the three districts. Gazipur and Sylhet straddle the zero line; Bandarban's interval sits entirely above it."
          />
          <figcaption>
            Adjusted loss with 95% confidence intervals against a dashed zero
            line. Only Bandarban's interval clears it.
          </figcaption>
        </figure>

        <p style={{ marginTop: "2rem" }}>
          One further result came out of the over-sampled loss stratum and is
          arguably more interesting than the loss figure itself: Gazipur drew 40
          points from it, and the interpreter judged only <b>2</b> to be genuine
          forest-to-non-forest transitions. That is a direct measurement of
          commission error in the global product used to train the classifiers.
        </p>
      </section>

      <section id="negatives">
        <p className="eyebrow">Negative results</p>
        <h2>What did not work, reported at the same volume as what did</h2>
        <p>
          Mapping tea plantation in Bangladesh is not merely difficult; on the
          evidence here it is currently unsolved. Five independent measurements
          point the same way, and each one is a method that was tried properly and
          failed.
        </p>

        <div className="negatives">
          {NEGATIVE_RESULTS.map((n) => (
            <div className="neg" key={n.value}>
              <span className="val">{n.value}</span>
              <p>
                <b>{n.headline}</b> {n.detail}
              </p>
            </div>
          ))}
        </div>

        <p style={{ marginTop: "2rem" }}>
          Because of the fourth of those, the plantation stratum is reported as{" "}
          <b>not usable for validation</b>. A reference sample whose interpreters
          agree at chance is not an independent yardstick, and scoring against it
          would present a disagreement as a measurement.
        </p>
      </section>

      <section id="method">
        <p className="eyebrow">Method</p>
        <h2>Measured rather than assumed</h2>
        <p>
          Landsat Collection 2 Level-2 surface reflectance, dry season only
          (1 November – 31 March), cloud and shadow masked, median reduced into a{" "}
          {STUDY.bands}-band stack. Train, validation and test splits are whole
          disjoint 10 km blocks, never random pixels, because random splitting on
          spatially autocorrelated data inflates accuracy silently.
        </p>
        <p>
          Two standard practices were tested rather than adopted on authority, and
          one of them failed. Published cross-sensor harmonisation coefficients,
          fitted over the continental United States, performed <b>worse here than
          applying no correction at all</b> (held-out residual 0.0168 against
          0.0158 raw). They would have degraded NIR by 8.5% and SWIR2 by 69.8% —
          the two bands NBR is built from, and NBR is what the entire Bandarban
          result depends on.
        </p>

        <figure>
          <img
            src={harmonisation}
            alt="Grouped bar chart of residual RMSE per spectral band for four candidate transforms, with the adopted transform marked for each band."
          />
          <figcaption>
            Residual RMSE per band for each candidate transform, adopted choice
            marked. The published coefficients are beaten by the raw data on four
            of six bands.
          </figcaption>
        </figure>

        <figure>
          <img
            src={sceneAvailability}
            alt="Heatmap of usable Landsat scenes per district per year from 1985 to 2024, showing zero coverage before 1988 and the Landsat 7 scan-line failure in 2012 and 2013."
          />
          <figcaption>
            Usable scenes per district-year, {STUDY.districtYearsAudited}{" "}
            district-years audited with zero failures. The study starts in{" "}
            <b>{STUDY.startYear}</b> because 1985–87 returned zero scenes across
            all three districts — an acquisition gap, not cloud.{" "}
            {STUDY.slcOffYears.join(" and ")} are entirely Landsat 7 SLC-off, so
            neither can serve as an epoch anchor.
          </figcaption>
        </figure>
      </section>

      <section id="links">
        <p className="eyebrow">Go deeper</p>
        <h2>The data, the code, and the live map</h2>

        <div className="links">
          <a
            className="link"
            href={LINKS.earthEngineApp || undefined}
            aria-disabled={!LINKS.earthEngineApp}
          >
            <span className="what">Interactive map</span>
            <span className="desc">
              Every epoch as a layer, NDVI change, and the annual trajectory at any
              pixel you click. Runs live on Earth Engine.
            </span>
            {!LINKS.earthEngineApp && (
              <span className="todo">Set earthEngineApp in findings.ts</span>
            )}
          </a>
          <a className="link" href={LINKS.thesisPdf || undefined} aria-disabled={!LINKS.thesisPdf}>
            <span className="what">Full thesis</span>
            <span className="desc">
              Seven chapters: study area, data, methodology, results and
              discussion, with the complete accuracy assessment.
            </span>
            {!LINKS.thesisPdf && <span className="todo">Set thesisPdf in findings.ts</span>}
          </a>
          <a className="link" href={LINKS.repository || undefined} aria-disabled={!LINKS.repository}>
            <span className="what">Code and data</span>
            <span className="desc">
              Earth Engine scripts, the preprocessing and modelling pipeline, the
              reference sample, and every figure on this page.
            </span>
            {!LINKS.repository && <span className="todo">Set repository in findings.ts</span>}
          </a>
        </div>
      </section>

      <footer>
        <p>EcoVision — deep learning for deforestation detection in Bangladesh.</p>
        <p>
          Sheikh Sulaiman Sony and Jalal Uddin Mohammad Akbar, supervised by Rubel
          Sheikh.
        </p>
        <p>
          Department of Educational Technology and Engineering, University of
          Frontier Technology, Bangladesh.
        </p>
        <p style={{ marginTop: "1rem" }}>
          Imagery: Landsat Collection 2 via Google Earth Engine, courtesy of the
          U.S. Geological Survey.
        </p>
      </footer>
    </div>
  );
}
