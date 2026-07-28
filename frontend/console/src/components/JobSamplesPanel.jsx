import { useEffect, useMemo, useRef, useState } from 'react';

function fmt(v) {
  if (v == null || Number.isNaN(v)) return '—';
  return Number(v).toFixed(2);
}

function imgUrl(benchmark, path) {
  if (!path) return '';
  if (path.startsWith('http')) return path;
  const bench = benchmark || 'multibanana';
  const clean = path.startsWith('/') ? path.slice(1) : path;
  return `/images/${bench}/${clean.split('/').map(encodeURIComponent).join('/')}`;
}

function itemScores(item) {
  return item.model_scores || item.firered_scores || {};
}

function itemOutput(item) {
  return item.model_output || item.firered;
}

function cacheKey(jobId, filter) {
  return `${jobId}:${filter || 'all'}`;
}

function SampleCard({ item, modelLabel, scoreScale, benchmark, onSelect }) {
  const refs = (item.references || []).slice(0, 3);
  const scores = itemScores(item);
  const output = itemOutput(item);
  return (
    <button type="button" className="sample-card" onClick={() => onSelect(item)}>
      <div className="sample-card-head">
        <span className="task-tag">{item.task}</span>
        <span className="score-pill">{fmt(scores.score)}/{scoreScale}</span>
      </div>
      <div className="sample-thumbs">
        {refs.map((ref, i) => (
          <img key={ref} src={imgUrl(benchmark, ref)} alt={`ref-${i}`} loading="lazy" />
        ))}
        {output ? (
          <img className="gen-thumb" src={imgUrl(benchmark, output)} alt={modelLabel} loading="lazy" />
        ) : (
          <div className="gen-thumb pending">待生成</div>
        )}
      </div>
      <p className="sample-instruction">{item.instruction}</p>
    </button>
  );
}

function SampleDetail({ item, modelLabel, dimensions, scoreScale, benchmark, onClose }) {
  if (!item) return null;
  const scores = itemScores(item);
  const output = itemOutput(item);
  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal sample-detail-modal" onClick={(e) => e.stopPropagation()}>
        <button type="button" className="modal-close" onClick={onClose}>×</button>
        <div className="modal-header">
          <span className="task-tag">{item.task}</span>
          <code>{item.key}</code>
        </div>
        <p className="modal-instruction">{item.instruction}</p>
        <div className="dim-grid">
          {dimensions.map(({ key, label }) => (
            <span key={key}>{label} <b>{fmt(scores[key])}</b></span>
          ))}
        </div>
        <div className="modal-grid viewer-refs">
          {(item.references || []).map((ref, i) => (
            <figure key={ref}>
              <figcaption>参考 {i + 1}</figcaption>
              <img src={imgUrl(benchmark, ref)} alt={`ref-${i}`} loading="lazy" />
            </figure>
          ))}
          {output && (
            <figure className="span-all">
              <figcaption>{modelLabel} 生成</figcaption>
              <img src={imgUrl(benchmark, output)} alt={modelLabel} loading="lazy" />
            </figure>
          )}
        </div>
      </div>
    </div>
  );
}

export default function JobSamplesPanel({ job }) {
  const [data, setData] = useState(null);
  const [taskFilter, setTaskFilter] = useState('all');
  const [selected, setSelected] = useState(null);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  const [benchmarkTasks, setBenchmarkTasks] = useState([]);
  const cacheRef = useRef(new Map());
  const requestIdRef = useRef(0);

  const jobTaskTypes = useMemo(() => {
    const types = job?.params?.task_types;
    return Array.isArray(types) && types.length ? [...types].sort() : null;
  }, [job?.params?.task_types]);

  useEffect(() => {
    if (!job?.benchmark) {
      setBenchmarkTasks([]);
      return undefined;
    }
    let cancelled = false;
    fetch(`/api/console/benchmark-options?benchmark=${encodeURIComponent(job.benchmark)}`)
      .then((r) => (r.ok ? r.json() : {}))
      .then((opts) => {
        if (!cancelled) setBenchmarkTasks(opts.task_types || []);
      })
      .catch(() => {
        if (!cancelled) setBenchmarkTasks([]);
      });
    return () => { cancelled = true; };
  }, [job?.benchmark]);

  const taskTabs = useMemo(() => {
    const stats = data?.task_stats || {};
    const labelFor = (id) => stats[id]?.label || benchmarkTasks.find((o) => o.value === id)?.label || id;
    const fromParams = jobTaskTypes;
    if (fromParams?.length) {
      return fromParams.map((id) => ({ id, label: labelFor(id) }));
    }
    const statIds = Object.keys(stats);
    if (statIds.length) {
      return statIds.sort().map((id) => ({ id, label: labelFor(id) }));
    }
    return benchmarkTasks.map((o) => ({ id: o.value, label: o.label }));
  }, [jobTaskTypes, data, benchmarkTasks]);

  const canShow = job && ['running', 'completed', 'interrupted', 'cancelled', 'failed'].includes(job.status);
  const progress = job?.progress || {};
  const hasOutputs = (progress.gen_done || 0) > 0
    || job?.status === 'completed'
    || job?.status === 'interrupted'
    || job?.status === 'cancelled'
    || job?.status === 'failed';
  const canFetchSamples = canShow && hasOutputs;

  useEffect(() => {
    setTaskFilter('all');
    setData(null);
    setSelected(null);
    setError('');
    setLoading(false);
    cacheRef.current = new Map();
    requestIdRef.current = 0;
  }, [job?.id]);

  useEffect(() => {
    if (!canFetchSamples || !job?.id) return undefined;

    const filter = taskFilter;
    const key = cacheKey(job.id, filter);
    const cached = cacheRef.current.get(key);
    if (cached) {
      setData(cached);
      setLoading(false);
      setError('');
    } else {
      setLoading(true);
    }

    const requestId = ++requestIdRef.current;
    const q = filter !== 'all' ? `?task=${encodeURIComponent(filter)}` : '';

    fetch(`/api/jobs/${job.id}/viewer-data${q}`)
      .then((r) => (r.ok ? r.json() : r.json().then((d) => Promise.reject(new Error(d.detail || r.status)))))
      .then((payload) => {
        if (requestId !== requestIdRef.current) return;
        cacheRef.current.set(key, payload);
        setData(payload);
        setError('');
      })
      .catch((e) => {
        if (requestId !== requestIdRef.current) return;
        setError(e.message);
      })
      .finally(() => {
        if (requestId === requestIdRef.current) setLoading(false);
      });

    return undefined;
  }, [job?.id, taskFilter, canFetchSamples]);

  useEffect(() => {
    if (!canFetchSamples || job?.status !== 'running' || !job?.id) return undefined;
    const timer = setInterval(() => {
      const filter = taskFilter;
      const q = filter !== 'all' ? `?task=${encodeURIComponent(filter)}` : '';
      fetch(`/api/jobs/${job.id}/viewer-data${q}`)
        .then((r) => (r.ok ? r.json() : null))
        .then((payload) => {
          if (!payload) return;
          cacheRef.current.set(cacheKey(job.id, filter), payload);
          if (filter === taskFilter) setData(payload);
        })
        .catch(() => {});
    }, 5000);
    return () => clearInterval(timer);
  }, [job?.id, job?.status, taskFilter, canFetchSamples]);

  const onTaskFilter = (task) => {
    if (task === taskFilter) return;
    setTaskFilter(task);
    setSelected(null);
    setError('');
    const key = cacheKey(job.id, task);
    const cached = cacheRef.current.get(key);
    if (cached) {
      setData(cached);
      setLoading(false);
    } else {
      setLoading(true);
    }
  };

  const tasks = taskTabs;

  if (!canShow) return null;

  const modelLabel = data?.model_label || job.weight_label || 'Model';
  const benchmark = job.benchmark || data?.benchmark_id || 'multibanana';
  const scoreScale = data?.score_scale ?? 10;
  const dimensions = data?.dimensions?.length ? data.dimensions : [];
  const perAll = data?.gallery?.per_task_all ?? 3;
  const perFiltered = data?.gallery?.per_task_filtered ?? 6;
  const avgScore = data?.model_avg_score ?? data?.firered_avg_score;
  const expectedFilter = taskFilter === 'all' ? 'all' : taskFilter;
  const avgLabel = expectedFilter !== 'all' ? '均分（当前类）' : '均分（任务范围）';
  const dataMatchesFilter = data && (data.task_filter || 'all') === expectedFilter;
  const samples = dataMatchesFilter ? (data?.samples || []) : [];
  const isRunning = job?.status === 'running';
  const isPaused = job?.status === 'cancelled' || job?.status === 'interrupted' || job?.status === 'failed';
  const phase = job?.progress?.phase;
  const genActive = (progress.gen_total ?? 0) > 0 && (progress.gen_done ?? 0) < (progress.gen_total ?? 0);
  const pipeline = phase === 'pipeline' || (phase === 'evaluating' && genActive);
  const judgedDone = (isRunning || isPaused) ? (progress.eval_done ?? 0) : (data?.judged_total ?? '—');
  const judgedTotal = (isRunning || isPaused) ? (progress.gen_total ?? progress.eval_total ?? '—') : (data?.total ?? '—');
  const generatedReady = data?.samples_total ?? samples.length;
  const showLoading = hasOutputs && loading && !samples.length;
  const showEmpty = hasOutputs && !showLoading && dataMatchesFilter && samples.length === 0;
  const showWarmup = !hasOutputs;

  return (
    <div className="param-group samples-panel">
      <div className="group-title">样例与评分</div>
      {showWarmup ? (
        <p className="field-hint">
          {isRunning
            ? `模型预热 / 排队中… 出图后将在此展示（${progress.gen_done ?? 0}/${progress.gen_total ?? '—'}）`
            : '生成开始后将在此展示样例与评分。'}
        </p>
      ) : (
        <p className="field-hint">
          全部类别：每类 {perAll} 条；点选类别标签后，该类最多 {perFiltered} 条。
          {expectedFilter !== 'all' && dataMatchesFilter && <> 当前：<b>{tasks.find((t) => t.id === expectedFilter)?.label || expectedFilter}</b></>}
          {(isRunning || isPaused) && (
            <> · {isPaused ? '任务已暂停' : pipeline ? '流水线并行' : '任务进行中'}，以下为<strong>本任务</strong>已生成图片的样例（共 {generatedReady} 张，不必等整类跑完；生成 {progress.gen_done ?? 0}/{progress.gen_total ?? '—'}，评测 {progress.eval_done ?? 0}/{progress.eval_total ?? '—'}）</>
          )}
        </p>
      )}
      {error && <div className="banner error compact">{error}</div>}
      {tasks.length > 0 && (
        <div className="task-filters">
          <button type="button" className={taskFilter === 'all' ? 'on' : ''} onClick={() => onTaskFilter('all')}>全部</button>
          {tasks.map(({ id, label }) => (
            <button key={id} type="button" className={taskFilter === id ? 'on' : ''} onClick={() => onTaskFilter(id)}>{label}</button>
          ))}
        </div>
      )}
      {hasOutputs && (
        <>
          <div className="score-summary">
            <div className="score-chip">
              <span>权重</span>
              <b>{modelLabel}</b>
            </div>
            <div className="score-chip">
              <span>裁判</span>
              <b>{data?.judge_model || data?.judge?.judge_model || '—'}</b>
            </div>
            <div className="score-chip accent">
              <span>{avgLabel}</span>
              <b>{fmt(avgScore)}/{scoreScale}</b>
            </div>
            <div className="score-chip">
              <span>已评测</span>
              <b>{judgedDone}/{judgedTotal}</b>
            </div>
          </div>
          {showLoading ? (
            <div className="boot-empty compact">正在加载样例…</div>
          ) : (
            <div className="sample-grid">
              {samples.map((item) => (
                <SampleCard
                  key={item.key}
                  item={item}
                  modelLabel={modelLabel}
                  scoreScale={scoreScale}
                  benchmark={benchmark}
                  onSelect={setSelected}
                />
              ))}
            </div>
          )}
          {showEmpty && (
            <div className="empty-panel">
              {isRunning
                ? '暂无已生成样例，生成开始后会在此展示。'
                : isPaused
                  ? '暂停时尚无已生成样例。'
                  : '该类别暂无样例（本次任务未包含此类别）。'}
            </div>
          )}
          {data?.samples_truncated && (
            <p className="field-hint">仅展示部分样例（共 {data.samples_total} 条）。完整结果见输出目录。</p>
          )}
        </>
      )}
      <SampleDetail
        item={selected}
        modelLabel={modelLabel}
        dimensions={dimensions}
        scoreScale={scoreScale}
        benchmark={benchmark}
        onClose={() => setSelected(null)}
      />
    </div>
  );
}
