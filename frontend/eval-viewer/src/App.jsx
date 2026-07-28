import { useEffect, useMemo, useState } from 'react';

const BENCHMARKS = [
  { id: 'multibanana', label: 'MultiBanana' },
];

const TASK_LABELS = {
  background_change: '背景替换',
  camera_motion: '镜头运动',
  character_reference: '角色参考',
  chart_editing: '图表编辑',
  color_alteration: '颜色修改',
  enhancement: '图像增强',
  hybrid: '混合编辑',
  in_image_text_translation: '图中文字翻译',
  line2image: '线稿生图',
  material_modification: '材质修改',
  motion_change: '动作变化',
  object_reference: '物体参考',
  openset: '开放集',
  portrait_beautification: '人像美化',
  relation_change: '关系变化',
  size_adjustment: '尺寸调整',
  style_reference: '风格参考',
  style_transfer: '风格迁移',
  subject_addition: '主体添加',
  subject_removal: '主体移除',
  subject_replace: '主体替换',
  text_editing: '文字编辑',
  tone_transfer: '色调迁移',
  temporal_reasoning: '时序推理',
  causal_reasoning: '因果推理',
  spatial_reasoning: '空间推理',
  logical_reasoning: '逻辑推理',
  '3_back': '3参考·背景',
  '3_global': '3参考·全局',
  '3_local': '3参考·局部',
  '3_object': '3参考·物体',
  '4_back': '4参考·背景',
  '4_global': '4参考·全局',
  '4_local': '4参考·局部',
  '4_object': '4参考·物体',
  '5_back': '5参考·背景',
  '5_global': '5参考·全局',
  '5_local': '5参考·局部',
  '5_object': '5参考·物体',
  '6_back': '6参考·背景',
  '6_global': '6参考·全局',
  '6_local': '6参考·局部',
  '6_object': '6参考·物体',
  '7_back': '7参考·背景',
  '7_global': '7参考·全局',
  '7_local': '7参考·局部',
  '7_object': '7参考·物体',
  '8_back': '8参考·背景',
  '8_global': '8参考·全局',
  '8_local': '8参考·局部',
  '8_object': '8参考·物体',
  add: '添加',
  background: '背景',
  color: '颜色',
  hair: '发型',
  makeup: '妆容',
  material: '材质',
  pose: '姿态',
  replace: '替换',
  single: '单参考',
  style: '风格',
  text: '文字',
  tone: '色调',
};

const FIRERED_WINNERS = new Set(['FireRed_Image_Edit_1p1', 'FireRed']);
const BASELINE_WINNERS = new Set(['BAGEL', 'BAGEL_with_cot']);

function fmtScore(v) {
  if (v == null || Number.isNaN(v)) return '—';
  return Number(v).toFixed(2);
}

const DIM_LABELS = {
  instruction_following: 'IF',
  visual_quality: 'VQ',
  visual_consistency: 'VC',
};

function normalizeData(raw, bench) {
  const baselineName = raw.baseline_name || 'BAGEL';
  const fireredName = raw.firered_name || 'FireRed';
  const isGpt = raw.eval_mode === 'gpt';
  const isMultibanana = raw.eval_mode === 'multibanana';
  const isGeditOfficial = raw.eval_mode === 'gedit_official';
  const hasBaseline = raw.has_baseline !== false;
  const baselineIsOfficialRef = Boolean(raw.baseline_is_official_ref);
  const baselineOfficialRef = raw.baseline_official_ref || null;
  const fireredKey = 'FireRed_Image_Edit_1p1';
  const baselineKey = 'BAGEL';

  const items = raw.items.map((item) => {
    const baselineScores = item.baseline_scores || {};
    const fireredScores = item.firered_scores || {};
    const baselineScore = baselineScores.score ?? null;
    const fireredScore = fireredScores.score ?? null;
    let isFireredWin = FIRERED_WINNERS.has(item.winner);
    let isBaselineWin = BASELINE_WINNERS.has(item.winner);
    if (isGpt) {
      if (item.winner === 'firered') isFireredWin = true;
      else if (item.winner === 'baseline') isBaselineWin = true;
      else if (baselineScore != null && fireredScore != null) {
        if (fireredScore > baselineScore) isFireredWin = true;
        else if (baselineScore > fireredScore) isBaselineWin = true;
      }
    }
    if (isGeditOfficial && item.dimension_winners?.visual_consistency) {
      isFireredWin = item.dimension_winners.visual_consistency === fireredKey;
      isBaselineWin = item.dimension_winners.visual_consistency === baselineKey;
    }
    return {
      ...item,
      baselineImg: item.baseline || item.bagel,
      fireredImg: item.firered,
      baselineLabel: item.baseline_label || baselineName,
      fireredLabel: item.firered_label || fireredName,
      baselineScores,
      fireredScores,
      baselineScore,
      fireredScore,
      dimensionWinners: item.dimension_winners || {},
      isFireredWin,
      isBaselineWin,
    };
  });

  let taskStats;
  if (isMultibanana) {
    taskStats = Object.fromEntries(
      Object.entries(raw.task_stats).map(([task, s]) => [
        task,
        {
          baseline: 0,
          firered: s.firered_avg ?? 0,
          total: s.total,
        },
      ]),
    );
  } else if (isGpt) {
    taskStats = Object.fromEntries(
      Object.entries(raw.task_stats).map(([task, s]) => [
        task,
        {
          baseline: s.baseline_avg ?? 0,
          firered: s.firered_avg ?? 0,
          total: s.total,
        },
      ]),
    );
  } else {
    taskStats = Object.fromEntries(
      Object.entries(raw.task_stats).map(([task, s]) => [
        task,
        {
          baseline: s.baseline ?? s.bagel ?? 0,
          firered: s.firered ?? 0,
          total: s.total,
        },
      ]),
    );
  }

  const elo = raw.elo || {};
  const dimensionElo = raw.dimension_elo || {};
  const fireredElo = elo[fireredKey] ?? elo.FireRed ?? '—';
  const baselineElo = baselineOfficialRef?.overall
    ?? elo[baselineKey]
    ?? elo.BAGEL_with_cot
    ?? '—';

  const pickElo = (dim) => {
    const block = dimensionElo[dim] || {};
    return {
      firered: block[fireredKey] ?? block.FireRed ?? '—',
      baseline: block[baselineKey] ?? block.BAGEL_with_cot ?? '—',
    };
  };

  return {
    bench,
    isGpt,
    isMultibanana,
    hasBaseline,
    isGeditOfficial,
    baselineIsOfficialRef,
    baselineOfficialRef,
    title: raw.title || 'MultiBanana',
    subtitle: raw.subtitle || '多参考图文生图评测',
    baselineName,
    fireredName,
    total: raw.total,
    baselineWins: raw.baseline_wins ?? raw.bagel_wins ?? 0,
    fireredWins: raw.firered_wins ?? 0,
    baselineAvg: raw.baseline_avg_score ?? baselineOfficialRef?.overall_score ?? null,
    fireredAvg: raw.firered_avg_score ?? null,
    baselineAvgPct: raw.baseline_avg_pct ?? baselineOfficialRef?.overall_pct ?? null,
    fireredAvgPct: raw.firered_avg_pct ?? null,
    fireredElo,
    baselineElo,
    dimensionElo: {
      overall: pickElo('overall'),
      instruction_following: pickElo('instruction_following'),
      visual_quality: pickElo('visual_quality'),
      visual_consistency: pickElo('visual_consistency'),
    },
    taskStats,
    methodologyNotes: raw.methodology_notes || [],
    items,
  };
}

function MethodologyPanel({ notes }) {
  if (!notes?.length) return null;
  return (
    <section className="panel methodology-panel">
      <h2>评测说明</h2>
      <div className="methodology-grid">
        {notes.map((note) => (
          <div key={note.title} className="methodology-card">
            <h3>{note.title}</h3>
            <p>{note.body}</p>
            {note.link && (
              <a href={note.link} target="_blank" rel="noreferrer">
                {note.link_label || note.link}
              </a>
            )}
          </div>
        ))}
      </div>
    </section>
  );
}

const CARD_REF_PREVIEW = 3;
const GALLERY_PAGE_SIZE = 24;

function imgUrl(bench, path) {
  return `/images/${bench}/${path}`;
}

function RefPreviewStrip({ refs, bench, max = CARD_REF_PREVIEW }) {
  const shown = refs.slice(0, max);
  const extra = refs.length - shown.length;
  return (
    <div className="ref-strip" aria-label={`${refs.length} 张参考图`}>
      {shown.map((ref, i) => (
        <div key={ref} className="thumb-wrap ref-thumb">
          <img src={imgUrl(bench, ref)} alt={`参考${i + 1}`} loading="lazy" decoding="async" />
        </div>
      ))}
      {extra > 0 && <span className="ref-more">+{extra}</span>}
    </div>
  );
}

function StatCard({ label, value, sub, accent }) {
  return (
    <div className="stat-card" style={{ '--accent': accent }}>
      <div className="stat-label">{label}</div>
      <div className="stat-value">{value}</div>
      {sub && <div className="stat-sub">{sub}</div>}
    </div>
  );
}

function TaskBar({ task, baseline, firered, total, baselineName, isGpt, isMultibanana }) {
  if (isMultibanana) {
    const fPct = Math.round((firered / 10) * 100);
    return (
      <div className="task-bar-row">
        <div className="task-bar-label" title={task}>
          {TASK_LABELS[task] || task}
          <span className="task-bar-count">{total}</span>
        </div>
        <div className="task-bar-track dual-score">
          <div className="task-bar-firered" style={{ width: `${fPct}%` }} />
        </div>
        <div className="task-bar-nums">
          <span className="firered-text">F {fmtScore(firered)}</span>
        </div>
      </div>
    );
  }
  if (isGpt) {
    const max = 5;
    const fPct = Math.round((firered / max) * 100);
    const bPct = Math.round((baseline / max) * 100);
    return (
      <div className="task-bar-row">
        <div className="task-bar-label" title={task}>
          {TASK_LABELS[task] || task}
          <span className="task-bar-count">{total}</span>
        </div>
        <div className="task-bar-track dual-score">
          <div className="task-bar-firered" style={{ width: `${fPct}%` }} />
          <div className="task-bar-bagel" style={{ width: `${bPct}%`, marginLeft: '4px' }} />
        </div>
        <div className="task-bar-nums">
          <span className="firered-text">F {fmtScore(firered)}</span>
          <span className="bagel-text">{baselineName[0]} {fmtScore(baseline)}</span>
        </div>
      </div>
    );
  }

  const fPct = total ? Math.round((firered / total) * 100) : 0;
  const bPct = 100 - fPct;
  return (
    <div className="task-bar-row">
      <div className="task-bar-label" title={task}>
        {TASK_LABELS[task] || task}
        <span className="task-bar-count">{total}</span>
      </div>
      <div className="task-bar-track">
        <div className="task-bar-firered" style={{ width: `${fPct}%` }} />
        <div className="task-bar-bagel" style={{ width: `${bPct}%` }} />
      </div>
      <div className="task-bar-nums">
        <span className="firered-text">F {firered}</span>
        <span className="bagel-text">{baselineName[0]} {baseline}</span>
      </div>
    </div>
  );
}

function MultiBananaScorePill({ scores }) {
  if (!scores || scores.score == null) return <span className="score-pill muted">未评分</span>;
  return (
    <span className="score-pill">
      均分 <strong>{fmtScore(scores.score)}</strong>
      <span className="score-dims">
        IA{fmtScore(scores.instruction_alignment)} · RC{fmtScore(scores.reference_consistency)} · VQ{fmtScore(scores.visual_quality)}
      </span>
    </span>
  );
}

function MultiBananaScoreBlock({ label, scores, highlight }) {
  return (
    <div className={`score-block ${highlight ? 'highlight' : ''}`}>
      <div className="score-block-title">{label}</div>
      <div className="score-block-total">{fmtScore(scores?.score)}</div>
      <div className="score-block-grid multibanana-grid">
        <span>指令 {fmtScore(scores?.instruction_alignment)}</span>
        <span>参考 {fmtScore(scores?.reference_consistency)}</span>
        <span>融合 {fmtScore(scores?.background_subject_match)}</span>
        <span>物理 {fmtScore(scores?.physical_realism)}</span>
        <span>画质 {fmtScore(scores?.visual_quality)}</span>
      </div>
    </div>
  );
}

function ScorePill({ scores }) {
  if (!scores || scores.score == null) return <span className="score-pill muted">未评分</span>;
  return (
    <span className="score-pill">
      总分 <strong>{fmtScore(scores.score)}</strong>
      <span className="score-dims">
        R{fmtScore(scores.reasoning)} · C{fmtScore(scores.consistency)} · P{fmtScore(scores.plausibility)}
      </span>
    </span>
  );
}

function fmtElo(v) {
  if (v == null || v === '—' || Number.isNaN(Number(v))) return '—';
  return Math.round(Number(v));
}

function DimensionEloBanner({ fireredName, baselineName, dimensionElo, baselineOfficialRef, baselineIsOfficialRef }) {
  const dims = [
    ['instruction_following', 'IF'],
    ['visual_quality', 'VQ'],
    ['visual_consistency', 'VC'],
    ['overall', 'Overall'],
  ];

  const renderRow = (label, source, accent) => (
    <div className="elo-banner-row" style={{ '--row-accent': accent }}>
      <span className="elo-banner-label">{label}</span>
      <div className="elo-banner-scores">
        {dims.map(([key, short]) => (
          <span key={key} className="elo-banner-chip">
            <em>{short}</em>
            <strong>{fmtElo(source[key]?.firered ?? source[key])}</strong>
          </span>
        ))}
      </div>
    </div>
  );

  return (
    <div className="elo-banner">
      {renderRow(`${fireredName} Elo（smoke）`, dimensionElo, 'var(--firered)')}
      {renderRow(`${baselineName} Elo（smoke 对比）`, {
        instruction_following: { firered: dimensionElo.instruction_following.baseline },
        visual_quality: { firered: dimensionElo.visual_quality.baseline },
        visual_consistency: { firered: dimensionElo.visual_consistency.baseline },
        overall: { firered: dimensionElo.overall.baseline },
      }, 'var(--bagel)')}
      {baselineIsOfficialRef && baselineOfficialRef && (
        <div className="elo-banner-row official" style={{ '--row-accent': 'var(--muted)' }}>
          <span className="elo-banner-label">{baselineName} 官方引用（全量 1200 条）</span>
          <div className="elo-banner-scores">
            {[
              ['instruction_following', 'IF'],
              ['visual_quality', 'VQ'],
              ['visual_consistency', 'VC'],
              ['overall', 'Overall'],
            ].map(([key, short]) => (
              <span key={key} className="elo-banner-chip muted">
                <em>{short}</em>
                <strong>{fmtElo(baselineOfficialRef[key])}</strong>
              </span>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
function DimensionBadges({ winners, fireredLabel, baselineLabel }) {
  const fireredKey = 'FireRed_Image_Edit_1p1';
  const baselineKey = 'BAGEL';
  return (
    <div className="dim-badges">
      {Object.entries(DIM_LABELS).map(([dim, label]) => {
        const w = winners?.[dim];
        let cls = 'tie';
        let text = '平';
        if (w === fireredKey) { cls = 'firered'; text = `F${label}`; }
        else if (w === baselineKey) { cls = 'bagel'; text = `B${label}`; }
        else text = label;
        return <span key={dim} className={`dim-badge ${cls}`} title={`${label}: ${w || '平局'}`}>{text}</span>;
      })}
    </div>
  );
}

function CompareCard({ item, bench, onSelect, isGpt, isMultibanana, isGeditOfficial, baselineIsOfficialRef, hasBaseline }) {
  return (
    <button type="button" className="compare-card" onClick={() => onSelect(item)}>
      <div className="compare-card-header">
        <span className="task-tag">{TASK_LABELS[item.task] || item.task}</span>
        {isMultibanana ? (
          <MultiBananaScorePill scores={item.fireredScores} />
        ) : isGpt ? (
          <span className={`winner-badge ${item.isFireredWin ? 'firered' : item.isBaselineWin ? 'bagel' : 'tie'}`}>
            {item.isFireredWin
              ? `${item.fireredLabel} 更高`
              : item.isBaselineWin
                ? `${item.baselineLabel} 更高`
                : '同分'}
          </span>
        ) : (
          <span className={`winner-badge ${item.isFireredWin ? 'firered' : item.isBaselineWin ? 'bagel' : 'tie'}`}>
            {isGeditOfficial ? 'VC ' : ''}
            {item.isFireredWin ? `${item.fireredLabel} 胜` : item.isBaselineWin ? `${item.baselineLabel} 胜` : '平局'}
          </span>
        )}
      </div>
      {isGeditOfficial && (
        <DimensionBadges
          winners={item.dimensionWinners}
          fireredLabel={item.fireredLabel}
          baselineLabel={item.baselineLabel}
        />
      )}
      {isMultibanana ? (
        <div className="compare-thumbs multibanana-thumbs">
          <RefPreviewStrip refs={item.references || []} bench={bench} />
          {item.fireredImg ? (
            <div className="thumb-wrap firered-thumb">
              <img src={imgUrl(bench, item.fireredImg)} alt={item.fireredLabel} loading="lazy" decoding="async" />
              <span>{item.fireredLabel}</span>
              <div className="thumb-score">{fmtScore(item.fireredScore)}</div>
            </div>
          ) : (
            <div className="thumb-wrap firered-thumb pending">待生成</div>
          )}
        </div>
      ) : (
      <div className="compare-thumbs">
        <div className={`thumb-wrap ${item.isBaselineWin ? 'winner-ring' : ''}`}>
          <img src={imgUrl(bench, item.baselineImg)} alt={item.baselineLabel} loading="lazy" />
          <span>{item.baselineLabel}</span>
          {isGpt && !baselineIsOfficialRef && <div className="thumb-score">{fmtScore(item.baselineScore)}</div>}
          {isGpt && baselineIsOfficialRef && <div className="thumb-score official-ref">官方引用</div>}
        </div>
        <div className={`thumb-wrap ${item.isFireredWin ? 'winner-ring' : ''}`}>
          <img src={imgUrl(bench, item.fireredImg)} alt={item.fireredLabel} loading="lazy" />
          <span>{item.fireredLabel}</span>
          {isGpt && <div className="thumb-score">{fmtScore(item.fireredScore)}</div>}
        </div>
      </div>
      )}
      <p className="compare-instruction">{item.instruction}</p>
    </button>
  );
}

function ScoreBlock({ label, scores, highlight }) {
  return (
    <div className={`score-block ${highlight ? 'highlight' : ''}`}>
      <div className="score-block-title">{label}</div>
      <div className="score-block-total">{fmtScore(scores?.score)}</div>
      <div className="score-block-grid">
        <span>推理 {fmtScore(scores?.reasoning)}</span>
        <span>一致 {fmtScore(scores?.consistency)}</span>
        <span>合理 {fmtScore(scores?.plausibility)}</span>
      </div>
    </div>
  );
}

function DetailModal({ item, bench, onClose, isGpt, isMultibanana, isGeditOfficial, baselineIsOfficialRef, baselineOfficialRef, hasBaseline }) {
  if (!item) return null;

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal" onClick={(e) => e.stopPropagation()}>
        <button type="button" className="modal-close" onClick={onClose}>×</button>
        <div className="modal-header">
          <span className="task-tag">{TASK_LABELS[item.task] || item.task}</span>
          <code className="item-key">{item.key}</code>
        </div>
        <p className="modal-instruction">{item.instruction}</p>
        {isGeditOfficial && (
          <div className="modal-dim-row">
            <span>维度胜负：</span>
            <DimensionBadges winners={item.dimensionWinners} />
          </div>
        )}
        {item.reference && (
          <p className="modal-reference">
            <strong>参考答案：</strong>
            {item.reference}
          </p>
        )}
        {item.difficulty && (
          <p className="modal-reference">
            <strong>难度标签：</strong>
            {item.difficulty}
          </p>
        )}
        {isMultibanana && (
          <div className="modal-scores">
            <MultiBananaScoreBlock label={item.fireredLabel} scores={item.fireredScores} highlight />
          </div>
        )}
        {isGpt && hasBaseline && (
          <div className="modal-scores">
            {baselineIsOfficialRef ? (
              <div className="score-block official-ref-block">
                <div className="score-block-title">{item.baselineLabel}</div>
                <div className="score-block-total">官方 {baselineOfficialRef?.overall_pct ?? '—'}%</div>
                <div className="score-block-grid">
                  <span>论文全量数据</span>
                  <span>未在 smoke 重评</span>
                </div>
              </div>
            ) : (
              <ScoreBlock label={item.baselineLabel} scores={item.baselineScores} highlight={item.isBaselineWin} />
            )}
            <ScoreBlock label={item.fireredLabel} scores={item.fireredScores} highlight={item.isFireredWin} />
          </div>
        )}
        {isMultibanana ? (
          <div className="modal-grid multibanana-refs">
            <div className="multibanana-refs-scroll span-all">
              {(item.references || []).map((ref, i) => (
                <figure key={ref}>
                  <figcaption>参考 {i + 1}</figcaption>
                  <img src={imgUrl(bench, ref)} alt={`ref-${i}`} loading="lazy" decoding="async" />
                </figure>
              ))}
            </div>
            <figure className="winner-panel span-all">
              <figcaption>{item.fireredLabel} 生成</figcaption>
              <img src={imgUrl(bench, item.fireredImg)} alt={item.fireredLabel} loading="lazy" decoding="async" />
            </figure>
          </div>
        ) : (
        <div className="modal-grid">
          <figure>
            <figcaption>原图</figcaption>
            <img src={imgUrl(bench, item.source)} alt="source" />
          </figure>
          <figure className={item.isBaselineWin ? 'winner-panel' : ''}>
            <figcaption>
              {item.baselineLabel} {item.isBaselineWin && <span className="win-tag">{isGpt ? '更高' : '胜'}</span>}
            </figcaption>
            <img src={imgUrl(bench, item.baselineImg)} alt={item.baselineLabel} />
          </figure>
          <figure className={item.isFireredWin ? 'winner-panel' : ''}>
            <figcaption>
              {item.fireredLabel} {item.isFireredWin && <span className="win-tag">{isGpt ? '更高' : '胜'}</span>}
            </figcaption>
            <img src={imgUrl(bench, item.fireredImg)} alt={item.fireredLabel} />
          </figure>
        </div>
        )}
        <div className="modal-footer">
          {isMultibanana ? 'GPT 五维均分：' : isGpt ? 'GPT 评测总分：' : 'PVC-Judge 判定：'}
          <strong>
            {isMultibanana
              ? `${item.fireredLabel} ${fmtScore(item.fireredScore)}/10`
              : isGpt
              ? `${item.baselineLabel} ${fmtScore(item.baselineScore)} / ${item.fireredLabel} ${fmtScore(item.fireredScore)}`
              : (item.winner || '平局')}
          </strong>
        </div>
      </div>
    </div>
  );
}

export default function App() {
  const [bench, setBench] = useState('multibanana');
  const [availableBenches, setAvailableBenches] = useState({});
  const [data, setData] = useState(null);
  const [error, setError] = useState('');
  const [taskFilter, setTaskFilter] = useState('all');
  const [winnerFilter, setWinnerFilter] = useState('all');
  const [search, setSearch] = useState('');
  const [selected, setSelected] = useState(null);
  const [galleryLimit, setGalleryLimit] = useState(GALLERY_PAGE_SIZE);

  useEffect(() => {
    fetch('/api/benchmarks')
      .then((r) => {
        if (!r.ok) throw new Error(`HTTP ${r.status}`);
        return r.json();
      })
      .then((list) => {
        const availability = Object.fromEntries(list.map((b) => [b.id, b.available]));
        setAvailableBenches(availability);
        const firstAvailable = list.find((b) => b.available)?.id;
        setBench((current) => {
          if (current && availability[current]) return current;
          return firstAvailable || 'geditbench';
        });
      })
      .catch(() => setBench('geditbench'));
  }, []);

  useEffect(() => {
    if (!bench) return undefined;

    const controller = new AbortController();
    setData(null);
    setError('');
    setTaskFilter('all');
    setWinnerFilter('all');
    setSearch('');
    setSelected(null);
    setGalleryLimit(GALLERY_PAGE_SIZE);

    fetch(`/api/data?bench=${bench}`, { signal: controller.signal })
      .then((r) => {
        if (!r.ok) throw new Error(`HTTP ${r.status}`);
        return r.json();
      })
      .then((raw) => setData(normalizeData(raw, bench)))
      .catch((e) => {
        if (e.name === 'AbortError') return;
        if (e.message === 'Failed to fetch') {
          setError('server_down');
          return;
        }
        if (e.message.includes('404')) {
          setError('data_missing');
          return;
        }
        setError(e.message);
      });

    return () => controller.abort();
  }, [bench]);

  const tasks = useMemo(() => {
    if (!data) return [];
    return [...new Set(data.items.map((i) => i.task))].sort();
  }, [data]);

  const filtered = useMemo(() => {
    if (!data) return [];
    return data.items.filter((item) => {
      if (taskFilter !== 'all' && item.task !== taskFilter) return false;
      if (winnerFilter === 'firered' && !item.isFireredWin) return false;
      if (winnerFilter === 'baseline' && !item.isBaselineWin) return false;
      if (search && !item.instruction.toLowerCase().includes(search.toLowerCase())
        && !item.key.toLowerCase().includes(search.toLowerCase())) return false;
      return true;
    });
  }, [data, taskFilter, winnerFilter, search]);

  useEffect(() => {
    setGalleryLimit(GALLERY_PAGE_SIZE);
  }, [taskFilter, winnerFilter, search]);

  const visibleItems = useMemo(
    () => (data?.isMultibanana ? filtered.slice(0, galleryLimit) : filtered),
    [data, filtered, galleryLimit],
  );

  if (error) {
    return (
      <div className="page error-page">
        <h1>加载失败</h1>
        {error === 'server_down' ? (
          <>
            <p>无法连接评测后端（<code>/api/data</code> 请求失败）。</p>
            <p>请确认服务已启动：<code>python frontend/server.py</code></p>
            <p>访问地址：<code>http://10.0.3.76:8765</code></p>
          </>
        ) : error === 'data_missing' ? (
          <>
            <p>当前 benchmark 的数据文件不存在（HTTP 404）。</p>
            <p>本机仅有 MultiBanana 数据时，请切换到 <strong>MultiBanana</strong> 标签页。</p>
            <p>或先导出数据到 <code>frontend/viewer_data/</code> 后再刷新。</p>
          </>
        ) : (
          <p>{error}</p>
        )}
      </div>
    );
  }

  if (!bench || !data) {
    return <div className="page loading-page">加载评测数据中…</div>;
  }

  const fireredPct = data.total ? Math.round((data.fireredWins / data.total) * 100) : 0;

  return (
    <div className="page">
      <div className="samples-topbar">
        <a className="samples-back" href="/">← 返回任务控制台</a>
        <span className="samples-tag">样例展示（只读）</span>
      </div>
      <nav className="bench-tabs">
        {BENCHMARKS.map((b) => (
          <button
            key={b.id}
            type="button"
            className={`bench-tab ${bench === b.id ? 'active' : ''}${availableBenches[b.id] === false ? ' unavailable' : ''}`}
            onClick={() => availableBenches[b.id] !== false && setBench(b.id)}
            disabled={availableBenches[b.id] === false}
            title={availableBenches[b.id] === false ? '数据未就绪' : undefined}
          >
            {b.label}
          </button>
        ))}
      </nav>

      <header className="hero">
        <div className="hero-text">
          <p className="eyebrow">{data.title}</p>
          <h1>样例展示</h1>
          <p className="subtitle">
            {data.subtitle} · {data.total} 条样本
          </p>
        </div>
        <div className="hero-stats">
          {data.isGeditOfficial ? (
            <>
              <StatCard label="Overall Elo" value={fmtElo(data.fireredElo)} sub={`${data.baselineName} smoke ${fmtElo(data.dimensionElo.overall.baseline)}`} accent="#f0a500" />
              <StatCard label="IF Elo" value={fmtElo(data.dimensionElo.instruction_following.firered)} sub={`${data.baselineName} ${fmtElo(data.dimensionElo.instruction_following.baseline)}`} accent="#e85d4c" />
              <StatCard label="VQ Elo" value={fmtElo(data.dimensionElo.visual_quality.firered)} sub={`${data.baselineName} ${fmtElo(data.dimensionElo.visual_quality.baseline)}`} accent="#4c8fe8" />
              <StatCard label="VC Elo" value={fmtElo(data.dimensionElo.visual_consistency.firered)} sub={`${data.baselineName} ${fmtElo(data.dimensionElo.visual_consistency.baseline)}`} accent="#9b7fe8" />
            </>
          ) : data.isMultibanana ? (
            <>
              <StatCard
                label={`${data.fireredName} 均分`}
                value={fmtScore(data.fireredAvg)}
                sub="/10 五维平均"
                accent="#e85d4c"
              />
              <StatCard label="参考图数" value="2–8" sub="多参考融合" accent="#4c8fe8" />
              <StatCard label="任务类型" value={Object.keys(data.taskStats).length} sub="36 类 smoke" accent="#f0a500" />
            </>
          ) : data.isGpt ? (
            <>
              <StatCard
                label={`${data.fireredName} 均分`}
                value={fmtScore(data.fireredAvg)}
                sub={data.fireredAvgPct != null ? `${data.fireredAvgPct}%` : null}
                accent="#e85d4c"
              />
              <StatCard
                label={`${data.baselineName} 均分`}
                value={fmtScore(data.baselineAvg)}
                sub={data.baselineIsOfficialRef ? `官方 ${data.baselineAvgPct}%` : (data.baselineAvgPct != null ? `${data.baselineAvgPct}%` : null)}
                accent="#4c8fe8"
              />
              <StatCard label="评分范围" value="1–5" sub="R / C / P 三维度" accent="#f0a500" />
            </>
          ) : (
            <>
              <StatCard label={`${data.fireredName} 胜场`} value={data.fireredWins} sub={`${fireredPct}%`} accent="#e85d4c" />
              <StatCard label={`${data.baselineName} 胜场`} value={data.baselineWins} sub={`${100 - fireredPct}%`} accent="#4c8fe8" />
              <StatCard
                label={`${data.fireredName} Elo`}
                value={data.fireredElo}
                sub={data.baselineIsOfficialRef ? `${data.baselineName} 官方 ${data.baselineElo}` : `${data.baselineName} ${data.baselineElo}`}
                accent="#f0a500"
              />
            </>
          )}
        </div>
      </header>

      {data.isGeditOfficial && (
        <DimensionEloBanner
          fireredName={data.fireredName}
          baselineName={data.baselineName}
          dimensionElo={data.dimensionElo}
          baselineOfficialRef={data.baselineOfficialRef}
          baselineIsOfficialRef={data.baselineIsOfficialRef}
        />
      )}

      <MethodologyPanel notes={data.methodologyNotes} />

      <section className="panel task-panel">
        <h2>{data.isMultibanana || data.isGpt ? '各类别平均分' : '各类别胜负分布'}</h2>
        <div className="task-bars">
          {Object.entries(data.taskStats)
            .sort((a, b) => b[1].total - a[1].total)
            .map(([task, s]) => (
              <TaskBar
                key={task}
                task={task}
                baseline={s.baseline}
                firered={s.firered}
                total={s.total}
                baselineName={data.baselineName}
                isGpt={data.isGpt}
                isMultibanana={data.isMultibanana}
              />
            ))}
        </div>
        {!data.isMultibanana && (
        <div className="legend">
          <span><i className="dot firered" /> {data.fireredName}{data.isGpt ? ' 均分' : ' 胜'}</span>
          <span><i className="dot bagel" /> {data.baselineName}{data.isGpt ? ' 均分' : ' 胜'}</span>
        </div>
        )}
      </section>

      <section className="panel gallery-panel">
        <div className="toolbar">
          <input
            type="search"
            placeholder="搜索 instruction 或 key…"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
          />
          <select value={taskFilter} onChange={(e) => setTaskFilter(e.target.value)}>
            <option value="all">全部类别</option>
            {tasks.map((t) => (
              <option key={t} value={t}>{TASK_LABELS[t] || t}</option>
            ))}
          </select>
          {!data.isMultibanana && (
          <select value={winnerFilter} onChange={(e) => setWinnerFilter(e.target.value)}>
            <option value="all">全部结果</option>
            <option value="firered">{data.fireredName} {data.isGpt ? '更高' : '胜'}</option>
            <option value="baseline">{data.baselineName} {data.isGpt ? '更高' : '胜'}</option>
          </select>
          )}
          <span className="result-count">{filtered.length} 条</span>
        </div>
        <div className={`gallery-grid${data.isMultibanana ? ' multibanana-gallery' : ''}`}>
          {visibleItems.map((item) => (
            <CompareCard key={item.key} item={item} bench={bench} onSelect={setSelected} isGpt={data.isGpt} isMultibanana={data.isMultibanana} isGeditOfficial={data.isGeditOfficial} baselineIsOfficialRef={data.baselineIsOfficialRef} hasBaseline={data.hasBaseline} />
          ))}
        </div>
        {data.isMultibanana && filtered.length > visibleItems.length && (
          <div className="gallery-more">
            <button
              type="button"
              className="gallery-more-btn"
              onClick={() => setGalleryLimit((n) => n + GALLERY_PAGE_SIZE)}
            >
              加载更多（已显示 {visibleItems.length} / {filtered.length}）
            </button>
          </div>
        )}
      </section>

      <DetailModal item={selected} bench={bench} onClose={() => setSelected(null)} isGpt={data.isGpt} isMultibanana={data.isMultibanana} isGeditOfficial={data.isGeditOfficial} baselineIsOfficialRef={data.baselineIsOfficialRef} baselineOfficialRef={data.baselineOfficialRef} hasBaseline={data.hasBaseline} />
    </div>
  );
}
