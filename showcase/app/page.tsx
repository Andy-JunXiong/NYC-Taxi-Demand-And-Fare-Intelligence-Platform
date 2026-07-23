const questions = [
  ["01", "Can the raw TLC data be trusted?", "Yes—after schema validation, checksum lineage, Bronze–Silver reconciliation, product-specific quality gates, and an atomic Gold release.", "37 monthly partitions passed"],
  ["02", "Where is demand concentrated?", "Manhattan dominates the operating footprint. JFK and LaGuardia form a distinct, high-volume segment that needs specialist treatment.", "89.1% Manhattan · 1.56M airport pickups"],
  ["03", "When does demand peak?", "The strongest recurring pattern sits in weekday late afternoons. Thursday at 18:00 is the largest weekday-hour cell.", "250,454 pickups in the peak cell"],
  ["04", "Does the model beat simple baselines?", "Across seven expanding-window test months, the event-aware model beats the previous-week baseline every time.", "17.4–20.9% candidate WAPE"],
  ["05", "Why use an airport specialist?", "JFK and LaGuardia produced the largest absolute errors in the global model. A dedicated model improved every test month.", "15–29% relative WAPE improvement"],
  ["06", "What failed on New Year’s Day?", "The live forecast missed the midnight surge. Monitoring blocked publication and preserved the original production release.", "Original WAPE 52.34%"],
  ["07", "Did the replacement really improve?", "The first candidate still failed recall. A weighted event specialist then passed every ordinary, event, and airport gate.", "New Year WAPE 33.82% · recall 81.87%"],
];

const pipeline = [
  ["Source", "Official TLC", "Resumable monthly Parquet"],
  ["Bronze", "Immutable", "Source files + checksums"],
  ["Silver", "Observable", "Enrichment + quality flags"],
  ["Gold", "Governed", "Zone-hour demand product"],
  ["Models", "Specialised", "Global + airport + event"],
  ["Operate", "Auditable", "Archive + monitor + ledger"],
];

export default function Home() {
  return (
    <main id="top">
      <header className="topbar">
        <a className="brand" href="#top"><span>NYC</span> Taxi Intelligence</a>
        <nav>
          <a href="#overview">Overview</a>
          <a href="#questions">Questions</a>
          <a href="#evidence">Evidence</a>
          <a href="#model">Model</a>
          <a href="#system">System</a>
        </nav>
        <span className="live"><i /> Production approved</span>
      </header>

      <div className="page-shell">
        <aside className="rail" aria-label="Page sections">
          <span>CASE STUDY</span>
          <a href="#overview">01 · Overview</a>
          <a href="#questions">02 · Questions</a>
          <a href="#evidence">03 · Evidence</a>
          <a href="#model">04 · Model</a>
          <a href="#system">05 · System</a>
        </aside>

        <div className="content">
          <section className="hero" id="overview">
            <div className="hero-label">Data product case study · 2022–2025</div>
            <h1>NYC taxi demand,<br />made defensible.</h1>
            <p className="lead">How 100M+ public records became a governed urban-demand product—through reliable data engineering, time-aware forecasting, and failure-safe operations.</p>
            <div className="hero-actions">
              <a className="button" href="#questions">Read the case study</a>
              <a className="text-link" href="#model">Jump to model evidence →</a>
            </div>
            <div className="metric-row">
              <div><small>Governed history</small><strong>37</strong><span>monthly partitions</span></div>
              <div><small>Gold product</small><strong>2.92M</strong><span>zone-hour rows</span></div>
              <div><small>Forecast output</small><strong>6,312</strong><span>zone × hour predictions</span></div>
              <div><small>Release validation</small><strong>32/32</strong><span>checks passed</span></div>
            </div>
          </section>

          <section className="chapter" id="questions">
            <div className="chapter-intro">
              <span>02 · DECISION QUESTIONS</span>
              <h2>Start with the decisions,<br />not the charts.</h2>
              <p>Each question connects a business claim to governed evidence and a measurable operational outcome.</p>
            </div>
            <div className="question-grid">
              {questions.map(([n, q, a, proof]) => (
                <article className="question-card" key={n}>
                  <span className="number">{n}</span>
                  <h3>{q}</h3>
                  <p>{a}</p>
                  <strong>{proof}</strong>
                </article>
              ))}
            </div>
          </section>

          <section className="chapter" id="evidence">
            <div className="chapter-intro">
              <span>03 · GOVERNED EVIDENCE</span>
              <h2>Demand has an<br />operational shape.</h2>
              <p>Every view is generated from checksum-verified Gold data with declared Silver lineage—not notebook wildcards.</p>
            </div>
            <div className="insight">
              <div><span>Finding 01</span><h3>Seasonality is visible, but not sufficient.</h3><p>May reached the first-half peak. Month-level seasonality informs planning; it does not replace zone-hour modelling.</p></div>
              <figure><img src="/monthly-demand.png" alt="Monthly Yellow Taxi pickup demand in the first half of 2024" /></figure>
            </div>
            <div className="chart-pair">
              <figure><figcaption><span>Finding 02</span><b>Manhattan dominates pickup activity</b></figcaption><img src="/borough-demand.png" alt="Taxi pickup demand by borough" /></figure>
              <figure><figcaption><span>Finding 03</span><b>Distance drives a right-skewed fare mix</b></figcaption><img src="/distance-fare.png" alt="Median fare by trip distance band" /></figure>
            </div>
            <div className="insight reverse">
              <figure><img src="/weekday-hour-demand.png" alt="Taxi demand heatmap by weekday and pickup hour" /></figure>
              <div><span>Finding 04</span><h3>Weekday evenings form the recurring peak.</h3><p>The pattern is stable enough to model, yet special events can overwhelm it—making monitoring and specialist routing essential.</p></div>
            </div>
          </section>

          <section className="chapter" id="model">
            <div className="chapter-intro">
              <span>04 · MODEL EVIDENCE</span>
              <h2>The model had to earn<br />its production label.</h2>
              <p>Seven expanding-window folds. No random split. No hiding the failed live forecast.</p>
            </div>
            <div className="model-grid">
              <div className="score-card">
                <div className="table-head"><span>Test month</span><span>Previous week</span><span>Candidate</span></div>
                {[
                  ["Jul 2024", "31.27%", "19.47%"], ["Aug 2024", "23.20%", "19.08%"],
                  ["Sep 2024", "24.28%", "18.49%"], ["Oct 2024", "21.07%", "17.40%"],
                  ["Nov 2024", "27.03%", "18.82%"], ["Dec 2024", "35.17%", "19.19%"],
                  ["Jan 2025", "29.18%", "20.89%"],
                ].map(row => <div className="table-row" key={row[0]}><b>{row[0]}</b><span>{row[1]}</span><strong>{row[2]}</strong></div>)}
                <small>Metric: WAPE · lower is better</small>
              </div>
              <div className="takeaway">
                <span>DECISION</span>
                <strong>7 / 7</strong>
                <h3>Candidate beats the baseline in every fold.</h3>
                <p>The result is consistent across demand regimes, not dependent on one lucky holdout month.</p>
              </div>
            </div>
            <div className="failure-story">
              <div className="failure-copy"><span>THE FAILURE THAT IMPROVED THE SYSTEM</span><h3>New Year’s Day exposed an event blind spot.</h3><p>The gate blocked a bad forecast. Instead of relaxing the threshold, the pipeline added event-specific evaluation and routing.</p></div>
              <div className="steps">
                <div className="bad"><small>Live failure</small><strong>52.34%</strong><span>WAPE</span></div>
                <div className="warn"><small>Candidate rejected</small><strong>78.36%</strong><span>recall</span></div>
                <div className="good"><small>Replacement approved</small><strong>81.87%</strong><span>recall</span></div>
              </div>
            </div>
          </section>

          <section className="chapter" id="system">
            <div className="chapter-intro">
              <span>05 · PRODUCTION SYSTEM</span>
              <h2>Built to fail safely,<br />recover, and explain why.</h2>
              <p>Every stage has an explicit trust boundary, version, gate, and recoverable handoff.</p>
            </div>
            <div className="pipeline">
              {pipeline.map(([label, title, copy], i) => (
                <div key={label}><span>{String(i + 1).padStart(2, "0")} · {label}</span><strong>{title}</strong><p>{copy}</p></div>
              ))}
            </div>
            <div className="system-note">
              <div><small>MODEL ROUTING</small><strong>Global · Airport · Event</strong></div>
              <div><small>FORECAST ARCHIVE</small><strong>Immutable versions + latest pointer</strong></div>
              <div><small>FAILURE SAFETY</small><strong>Atomic writes · production preserved</strong></div>
            </div>
          </section>

          <section className="closing">
            <span>THE OUTCOME</span>
            <h2>Not just a taxi model.<br />A governed decision product.</h2>
            <p>263 zones × 24 hours · Global, airport, and event-aware routing · All publication gates passed.</p>
            <a className="button" href="#top">Back to overview ↑</a>
          </section>

          <footer><span>NYC Taxi Demand & Fare Intelligence</span><span>Data Engineering · EDA · Forecasting · MLOps</span></footer>
        </div>
      </div>
    </main>
  );
}
