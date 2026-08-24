import type { Metadata } from "next";
import Link from "next/link";
import styles from "./review.module.css";

export const metadata: Metadata = {
  title: "Recursive Evaluation Review — NYC Taxi Intelligence",
  description: "A visual review of the frozen recursive evaluation plan for candidate v2.",
};

const evaluationBlocks = [
  {
    id: "A",
    dates: "01–24 Jun 2026",
    role: "Ordinary pattern",
    detail: "Weekdays and weekends without a configured major-event route.",
    tone: "blue",
  },
  {
    id: "B",
    dates: "29 Jun–22 Jul 2026",
    role: "Independence Day",
    detail: "Ordinary days plus the configured 4 July event route.",
    tone: "red",
  },
  {
    id: "C",
    dates: "09 Nov–02 Dec 2026",
    role: "Thanksgiving",
    detail: "A later-season block spanning the Thanksgiving route.",
    tone: "orange",
  },
  {
    id: "D",
    dates: "15 Dec 2026–07 Jan 2027",
    role: "Year-end events",
    detail: "Christmas and New Year, plus surrounding ordinary days.",
    tone: "green",
  },
];

const originRotation = Array.from({ length: 24 }, (_, index) => ({
  sequence: index + 1,
  hour: (5 * index) % 24,
}));

const metricGroups = [
  {
    number: "01",
    label: "Proposed criteria",
    title: "Consistency and tail harm",
    metrics: ["Daily win rate", "Worst-day degradation"],
    note: "Reported without a numeric pass threshold.",
    tone: "blue",
  },
  {
    number: "02",
    label: "Advisory evidence",
    title: "Operational drift",
    metrics: ["WAPE < 25%", "|Bias| < 10%", "Recall ≥ 90%"],
    note: "Each check stays visible; the composite cannot hide a failure.",
    tone: "orange",
  },
  {
    number: "03",
    label: "Diagnostic only",
    title: "Horizon versus clock",
    metrics: ["24 horizon hours", "24 UTC clock hours", "4 block replicates"],
    note: "Useful for diagnosis, not a release gate in this evaluation.",
    tone: "green",
  },
];

const reviewItems = [
  "Four fixed, non-overlapping evaluation blocks",
  "One deterministic origin rotation for every block",
  "Metric roles remain unchanged and threshold-free",
  "Manhattan and volume groups are frozen from training data",
  "Evidence remains observational and cannot promote a model",
];

export default function ReviewPage() {
  return (
    <main className={styles.reviewPage} lang="zh-CN">
      <header className={styles.header}>
        <Link className={styles.brand} href="/">
          <span>NYC</span>
          <div>
            <strong>Taxi Intelligence</strong>
            <small>Model governance</small>
          </div>
        </Link>
        <div className={styles.headerActions}>
          <a href="#decision">评审要点</a>
          <a href="#design">评估设计</a>
          <span className={styles.status}><i /> Awaiting review</span>
        </div>
      </header>

      <div className={styles.shell}>
        <section className={styles.hero}>
          <div className={styles.heroCopy}>
            <div className={styles.eyebrow}>
              <span>PRE-REGISTRATION · 24 AUG 2026</span>
              <b>Candidate v2 · HOLD</b>
            </div>
            <h1>先锁定评估方法，<br /><em>再看模型结果。</em></h1>
            <p>
              这不是模型成绩单，而是一份评审界面。它提前固定后续样本、
              递归起点和报告规则，避免根据结果临时改变标准。
            </p>
            <div className={styles.heroStats}>
              <div><strong>4</strong><span>独立评估窗口</span></div>
              <div><strong>96</strong><span>24 小时预测起点</span></div>
              <div><strong>24×24</strong><span>步长与时钟交叉</span></div>
            </div>
          </div>

          <aside className={styles.decisionCard} id="decision">
            <div className={styles.cardHeader}>
              <span>YOUR DECISION</span>
              <b>01</b>
            </div>
            <h2>你现在只需要确认设计。</h2>
            <p>确认不等于运行评估，也不等于批准模型发布。</p>
            <ul>
              {reviewItems.map((item) => (
                <li key={item}><i aria-hidden="true" />{item}</li>
              ))}
            </ul>
            <div className={styles.decisionFooter}>
              <span>当前状态</span>
              <strong>等待维护者评审</strong>
            </div>
          </aside>
        </section>

        <section className={styles.section} id="design">
          <div className={styles.sectionTitle}>
            <span>01 · EVALUATION WINDOWS</span>
            <div>
              <h2>四个窗口，各自回答不同的泛化问题。</h2>
              <p>五月仅用于形成假设，不会混入确认性结果。</p>
            </div>
          </div>

          <div className={styles.timeline}>
            {evaluationBlocks.map((block) => (
              <article className={styles.blockCard} data-tone={block.tone} key={block.id}>
                <div className={styles.blockTop}>
                  <span>BLOCK {block.id}</span>
                  <i aria-hidden="true" />
                </div>
                <time>{block.dates}</time>
                <h3>{block.role}</h3>
                <p>{block.detail}</p>
                <footer><strong>24</strong><span>forecast origins</span></footer>
              </article>
            ))}
          </div>
          <div className={styles.timelineNote}>
            <b>WHY THESE WINDOWS</b>
            <p>覆盖普通日、周末和多个事件制度，同时与截至 2026 年 4 月的训练期保持严格时间隔离。</p>
          </div>
        </section>

        <section className={`${styles.section} ${styles.rotationSection}`}>
          <div className={styles.sectionTitle}>
            <span>02 · STAGGERED ORIGINS</span>
            <div>
              <h2>打散午夜起点，分开“时钟难度”和“递归衰减”。</h2>
              <p>每个窗口的 24 天分别使用不同 UTC 起点，每个小时恰好出现一次。</p>
            </div>
          </div>

          <div className={styles.rotationLayout}>
            <div className={styles.rotationCard}>
              <div className={styles.rotationHeader}>
                <div>
                  <span>ORIGIN ROTATION</span>
                  <strong>origin = (5 × day) mod 24</strong>
                </div>
                <b>UTC</b>
              </div>
              <div className={styles.hourGrid} aria-label="24 staggered UTC origin hours">
                {originRotation.map(({ sequence, hour }) => (
                  <div key={sequence}>
                    <small>{String(sequence).padStart(2, "0")}</small>
                    <strong>{String(hour).padStart(2, "0")}:00</strong>
                  </div>
                ))}
              </div>
            </div>

            <div className={styles.crossingCard}>
              <span>COMPLETE CROSSING · PER BLOCK</span>
              <div className={styles.flow}>
                <div><strong>24</strong><small>origin dates</small></div>
                <i>×</i>
                <div><strong>24</strong><small>recursive hours</small></div>
                <i>=</i>
                <div className={styles.result}><strong>576</strong><small>clock × horizon cells</small></div>
              </div>
              <div className={styles.matrix} aria-hidden="true">
                {Array.from({ length: 144 }, (_, index) => <i key={index} />)}
              </div>
              <p>四个窗口提供四次完整重复；结果仍按区块展示，不假设重叠预测彼此独立。</p>
            </div>
          </div>
        </section>

        <section className={styles.section}>
          <div className={styles.sectionTitle}>
            <span>03 · EVIDENCE ROLES</span>
            <div>
              <h2>同一份结果，不同的决策权重。</h2>
              <p>重要指标不会被一个总分折叠，也不会从五月样本拟合新门槛。</p>
            </div>
          </div>
          <div className={styles.metricGrid}>
            {metricGroups.map((group) => (
              <article className={styles.metricCard} data-tone={group.tone} key={group.number}>
                <header><span>{group.number}</span><b>{group.label}</b></header>
                <h3>{group.title}</h3>
                <ul>{group.metrics.map((metric) => <li key={metric}>{metric}</li>)}</ul>
                <p>{group.note}</p>
              </article>
            ))}
          </div>
        </section>

        <section className={`${styles.section} ${styles.guardrailSection}`}>
          <div className={styles.guardrailCopy}>
            <span>04 · GOVERNANCE BOUNDARY</span>
            <h2>这次批准不会触发任何生产动作。</h2>
            <p>
              页面展示的是设计冻结点。数据获取、实现、实际评估、训练、推广和发布都保留为独立授权。
            </p>
            <div className={styles.boundaryTags}>
              {[
                "No data download",
                "No model run",
                "No threshold selection",
                "No promotion",
                "No publication",
              ].map((tag) => <span key={tag}>{tag}</span>)}
            </div>
          </div>
          <aside className={styles.nextStep}>
            <span>IF YOU APPROVE</span>
            <h3>下一步只实现交错起点评估器。</h3>
            <p>受保护的核心实现仍需要你明确批准以下两个文件：</p>
            <code>src/nyc_taxi/model_validation.py</code>
            <code>tests/test_recursive_shadow_evaluation.py</code>
          </aside>
        </section>

        <section className={styles.auditStrip}>
          <div>
            <span>AUDIT SOURCE</span>
            <code>docs/recursive-evaluation-preregistration-2026-08-24.md</code>
          </div>
          <div>
            <span>CANDIDATE IDENTITY</span>
            <code>29354b38…e334</code>
          </div>
          <div>
            <span>PROMOTION</span>
            <strong>NOT PERMITTED</strong>
          </div>
        </section>

        <footer className={styles.footer}>
          <Link href="/">← 返回项目案例</Link>
          <span>NYC Taxi Intelligence · Evaluation Review</span>
        </footer>
      </div>
    </main>
  );
}
