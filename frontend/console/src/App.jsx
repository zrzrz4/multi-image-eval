import { useCallback, useEffect, useMemo, useState } from 'react';
import JudgeConfigModal from './components/JudgeConfigModal.jsx';
import JobDetailView from './components/JobDetailView.jsx';
import SubmitWeightForm from './components/SubmitWeightForm.jsx';
import VersionListView from './components/VersionListView.jsx';

const VIEWS = {
  WEIGHTS: 'weights',
  BENCHMARKS: 'benchmarks',
  VERSIONS: 'versions',
  JOB: 'job',
  SUBMIT: 'submit',
};

const DEFAULT_GROUPS = {
  data: '数据范围',
  inference: '生成参数',
  eval: '评测参数',
  advanced: '高级',
};

function fieldVisible(field, params) {
  if (!field.show_when) return true;
  return Object.entries(field.show_when).every(([k, v]) => params[k] === v);
}

function resolveOptions(field, dynamicOptions) {
  if (field.dynamic_options && dynamicOptions[field.dynamic_options]) {
    return dynamicOptions[field.dynamic_options];
  }
  return field.options || [];
}

function ParamField({ field, value, onChange, params, dynamicOptions }) {
  if (!fieldVisible(field, params)) return null;
  const { key, label, type, min, max, step, hint } = field;
  const options = resolveOptions(field, dynamicOptions);

  if (type === 'multiselect') {
    const selected = Array.isArray(value) ? value : [];
    const toggle = (optValue) => {
      if (selected.includes(optValue)) {
        onChange(key, selected.filter((v) => v !== optValue));
      } else {
        onChange(key, [...selected, optValue]);
      }
    };
    const selectAll = () => onChange(key, options.map((o) => o.value));
    const clearAll = () => onChange(key, []);
    return (
      <div className="form-field multiselect-field">
        <div className="multiselect-head">
          <span className="field-label">{label}</span>
          <div className="multiselect-actions">
            <button type="button" onClick={selectAll}>全选</button>
            <button type="button" onClick={clearAll}>清空</button>
            <span className="multiselect-count">
              {selected.length ? `已选 ${selected.length} 类` : `未选 = 全部 ${options.length || '?'} 类`}
            </span>
          </div>
        </div>
        <div className="multiselect-grid">
          {options.map((o) => (
            <label key={o.value} className={`multiselect-item ${selected.includes(o.value) ? 'on' : ''}`}>
              <input
                type="checkbox"
                checked={selected.includes(o.value)}
                onChange={() => toggle(o.value)}
              />
              <span>{o.label}</span>
            </label>
          ))}
        </div>
        {hint && <p className="field-hint">{hint}</p>}
      </div>
    );
  }

  if (type === 'select') {
    return (
      <label className="form-field">
        <span className="field-label">{label}</span>
        <select value={value} onChange={(e) => onChange(key, e.target.value)}>
          {(options || []).map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
        </select>
        {hint && <p className="field-hint">{hint}</p>}
      </label>
    );
  }
  if (type === 'bool') {
    return (
      <label className="form-field checkbox-field">
        <input type="checkbox" checked={Boolean(value)} onChange={(e) => onChange(key, e.target.checked)} />
        <span>{label}</span>
        {hint && <p className="field-hint">{hint}</p>}
      </label>
    );
  }
  if (type === 'float') {
    return (
      <label className="form-field">
        <span className="field-label">{label}</span>
        <input type="number" min={min} max={max} step={step || 0.1} value={value} onChange={(e) => onChange(key, parseFloat(e.target.value))} />
        {hint && <p className="field-hint">{hint}</p>}
      </label>
    );
  }
  return (
    <label className="form-field">
      <span className="field-label">{label}</span>
      <input type="number" min={min} max={max} value={value} onChange={(e) => onChange(key, parseInt(e.target.value, 10))} />
      {hint && <p className="field-hint">{hint}</p>}
    </label>
  );
}

function GpuCard({ gpu, selected, onToggle }) {
  const memPct = gpu.memory_total_mb ? Math.round((gpu.memory_used_mb / gpu.memory_total_mb) * 100) : 0;
  const busy = gpu.utilization_pct > 10 || memPct > 15;
  return (
    <div className={`gpu-card ${selected ? 'selected' : ''} ${busy ? 'busy' : 'available'}`}>
      <input type="checkbox" className="gpu-check" checked={selected} onChange={() => onToggle(gpu.index)} />
      <label onClick={() => onToggle(gpu.index)}>
        <div className="gpu-card-top">
          <span className="gid">GPU {gpu.index}</span>
          <span className={`gpu-badge ${busy ? 'busy' : 'free'}`}>{busy ? '占用中' : '空闲'}</span>
        </div>
        <div className="gpu-name">{gpu.name}</div>
        <div className="gmeta-row">
          <span>显存 {gpu.memory_used_mb}/{gpu.memory_total_mb} MB</span>
          <span>{gpu.utilization_pct}%</span>
        </div>
        <div className="gpu-mem-bar"><i style={{ width: `${memPct}%`, background: memPct > 80 ? '#dc2626' : '#2563eb' }} /></div>
      </label>
    </div>
  );
}

function defaultParams(benchmark) {
  const defaults = {};
  for (const p of benchmark?.params || []) {
    defaults[p.key] = p.default ?? (p.type === 'multiselect' ? [] : p.type === 'bool' ? false : '');
  }
  return defaults;
}

function paramsFromJob(job, benchmark) {
  if (!job?.params) return defaultParams(benchmark);
  return { ...defaultParams(benchmark), ...job.params };
}

function groupParams(benchmark) {
  const groups = { ...DEFAULT_GROUPS, ...(benchmark?.param_groups || {}) };
  const buckets = Object.fromEntries(Object.keys(groups).map((k) => [k, []]));
  for (const field of benchmark?.params || []) {
    const g = field.group || 'inference';
    if (!buckets[g]) buckets[g] = [];
    buckets[g].push(field);
  }
  return { groups, buckets };
}

export default function App() {
  const [models, setModels] = useState([]);
  const [benchmarks, setBenchmarks] = useState([]);
  const [gpus, setGpus] = useState([]);
  const [hostLabel, setHostLabel] = useState('');
  const [jobs, setJobs] = useState([]);
  const [datasetInfo, setDatasetInfo] = useState(null);
  const [dynamicOptions, setDynamicOptions] = useState({});
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState('');
  const [message, setMessage] = useState('');

  const [selectedModelId, setSelectedModelId] = useState(null);
  const [selectedWeightId, setSelectedWeightId] = useState(null);
  const [selectedBenchmarkId, setSelectedBenchmarkId] = useState(null);
  const [view, setView] = useState(VIEWS.WEIGHTS);
  const [selectedJobId, setSelectedJobId] = useState(null);
  const [selectedJobLabel, setSelectedJobLabel] = useState('');
  const [selectedGpus, setSelectedGpus] = useState([]);
  const [params, setParams] = useState({});
  const [judgeOpen, setJudgeOpen] = useState(false);
  const [judgeHint, setJudgeHint] = useState('');
  const [showWeightForm, setShowWeightForm] = useState(false);

  const selectedModel = useMemo(() => models.find((m) => m.id === selectedModelId) || null, [models, selectedModelId]);
  const selectedWeight = useMemo(
    () => selectedModel?.weights?.find((w) => w.id === selectedWeightId) || null,
    [selectedModel, selectedWeightId],
  );
  const benchmark = useMemo(
    () => benchmarks.find((b) => b.id === selectedBenchmarkId) || null,
    [benchmarks, selectedBenchmarkId],
  );
  const scopedJobCount = useMemo(() => {
    if (!selectedModelId || !selectedWeightId) return {};
    const counts = {};
    for (const b of benchmarks) {
      counts[b.id] = jobs.filter(
        (j) => j.model_id === selectedModelId && j.weight_id === selectedWeightId && j.benchmark === b.id,
      ).length;
    }
    return counts;
  }, [jobs, benchmarks, selectedModelId, selectedWeightId]);

  const selectedJob = useMemo(
    () => jobs.find((j) => j.id === selectedJobId) || null,
    [jobs, selectedJobId],
  );

  const refreshGpus = useCallback(async () => {
    const g = await fetch('/api/console/gpus').then((r) => r.json());
    setGpus(g.gpus || []);
    if (g.hostname) setHostLabel(g.hostname);
  }, []);

  const refreshJobs = useCallback(async () => {
    const j = await fetch('/api/jobs').then((r) => r.json());
    setJobs(j);
    return j;
  }, []);

  const refresh = useCallback(async () => {
    const [m, b] = await Promise.all([
      fetch('/api/console/models').then((r) => r.json()),
      fetch('/api/console/benchmarks').then((r) => r.json()),
    ]);
    setModels(m);
    setBenchmarks(b);
    await Promise.all([refreshGpus(), refreshJobs()]);
    setLoading(false);
  }, [refreshGpus, refreshJobs]);

  const hasRunningJob = useMemo(
    () => jobs.some((j) => j.status === 'running'),
    [jobs],
  );

  useEffect(() => {
    refresh().catch((e) => setError(e.message));
    const pollMs = hasRunningJob ? 2000 : 5000;
    const timer = setInterval(() => {
      refreshJobs().catch(() => {});
      refreshGpus().catch(() => {});
    }, pollMs);
    return () => clearInterval(timer);
  }, [refresh, refreshJobs, refreshGpus, hasRunningJob]);

  useEffect(() => {
    fetch('/api/console/judge-config')
      .then((r) => r.json())
      .then((cfg) => setJudgeHint(cfg.model || ''))
      .catch(() => {});
  }, [judgeOpen]);

  useEffect(() => {
    if (!models.length || selectedModelId) return;
    setSelectedModelId(models[0].id);
  }, [models, selectedModelId]);

  useEffect(() => {
    if (!benchmark) return;
    setParams(defaultParams(benchmark));
    fetch(`/api/console/benchmark-options?benchmark=${benchmark.id}`)
      .then((r) => r.json())
      .then(setDynamicOptions)
      .catch(() => setDynamicOptions({}));
  }, [selectedBenchmarkId]); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    if (!benchmark) return;
    fetch('/api/console/dataset-info', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ benchmark: benchmark.id, params }),
    })
      .then((r) => r.json())
      .then(setDatasetInfo)
      .catch(() => setDatasetInfo(null));
  }, [benchmark, params]);

  const selectModel = (id) => {
    setSelectedModelId(id);
    setSelectedWeightId(null);
    setSelectedBenchmarkId(null);
    setView(VIEWS.WEIGHTS);
    setSelectedJobId(null);
  };

  const openWeight = (weightId) => {
    setSelectedWeightId(weightId);
    setSelectedBenchmarkId(null);
    setSelectedJobId(null);
    setView(VIEWS.BENCHMARKS);
  };

  const openBenchmark = (benchId) => {
    setSelectedBenchmarkId(benchId);
    setSelectedJobId(null);
    setView(VIEWS.VERSIONS);
  };

  const openNewRun = () => {
    const b = benchmarks.find((x) => x.id === selectedBenchmarkId);
    const scoped = jobs
      .filter(
        (j) => j.model_id === selectedModelId
          && j.weight_id === selectedWeightId
          && j.benchmark === selectedBenchmarkId,
      )
      .sort((a, c) => (a.created_at || '').localeCompare(c.created_at || ''));
    const source = scoped.find((j) => j.id === selectedJobId) || scoped[scoped.length - 1];
    if (b) setParams(source ? paramsFromJob(source, b) : defaultParams(b));
    setSelectedJobId(null);
    setView(VIEWS.SUBMIT);
  };

  const selectJob = (jobId, label = '') => {
    setSelectedJobId(jobId);
    setSelectedJobLabel(label);
    setView(VIEWS.JOB);
  };

  const backToVersions = () => {
    setView(VIEWS.VERSIONS);
  };

  useEffect(() => {
    document.querySelector('main')?.scrollTo({ top: 0, behavior: 'instant' in window ? 'instant' : 'auto' });
  }, [view, selectedBenchmarkId, selectedWeightId, selectedJobId]);

  const toggleGpu = (idx) => {
    setSelectedGpus((prev) => (prev.includes(idx) ? prev.filter((g) => g !== idx) : [...prev, idx].sort((a, b) => a - b)));
  };

  const submit = async () => {
    setError('');
    setMessage('');
    if (!selectedWeight) return setError('请先选择权重');
    if (!benchmark) return setError('请先选择评测方法');
    if (!selectedGpus.length) return setError('请至少选择一张 GPU');
    setSubmitting(true);
    try {
      const res = await fetch('/api/jobs', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          model_id: selectedModelId,
          weight_id: selectedWeightId,
          benchmark: benchmark.id,
          model_path: selectedWeight.path,
          gpus: selectedGpus,
          params,
        }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || `HTTP ${res.status}`);
      setMessage(`任务已提交：${data.id}`);
      setSelectedJobId(data.id);
      setSelectedJobLabel('第1次测试');
      setView(VIEWS.JOB);
      await refresh();
    } catch (e) {
      setError(e.message);
    } finally {
      setSubmitting(false);
    }
  };

  const deleteJob = async (item) => {
    if (selectedJobId === item.id) {
      setSelectedJobId(null);
      setSelectedJobLabel('');
      setView(VIEWS.VERSIONS);
    }
    setMessage(`已删除：${item.id}`);
    await refresh();
  };

  const cancelJob = async (id) => {
    if (!window.confirm('确定终止当前测试？\n已生成的图片会保留，之后可点「继续测试」从断点恢复。')) return;
    await fetch(`/api/jobs/${id}/cancel`, { method: 'POST' });
    await refresh();
  };

  const resumeJob = async (id, gpuList) => {
    setError('');
    if (!gpuList?.length) return setError('请至少选择一张 GPU');
    try {
      const res = await fetch(`/api/jobs/${id}/resume`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ gpus: gpuList }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || `HTTP ${res.status}`);
      setMessage(`继续测试已启动：${id}`);
      setSelectedJobId(id);
      setView(VIEWS.JOB);
      await refresh();
    } catch (e) {
      setError(e.message);
    }
  };

  if (loading) return <div className="boot-empty">正在加载…</div>;

  const crumb = (
    <div className="crumb">
      🧠 <a onClick={() => { setView(VIEWS.WEIGHTS); setSelectedWeightId(null); setSelectedBenchmarkId(null); }}>{selectedModel?.label}</a>
      {selectedWeight && (
        <>
          <span className="sep">›</span>
          <a onClick={() => { setView(VIEWS.BENCHMARKS); setSelectedBenchmarkId(null); }}>⚖️ {selectedWeight.label}</a>
        </>
      )}
      {benchmark && (view === VIEWS.VERSIONS || view === VIEWS.SUBMIT || view === VIEWS.JOB) && (
        <>
          <span className="sep">›</span>
          {view === VIEWS.JOB || view === VIEWS.SUBMIT ? (
            <a onClick={() => { if (view === VIEWS.SUBMIT) setView(VIEWS.VERSIONS); else backToVersions(); }}>📋 {benchmark.title}</a>
          ) : (
            <b>📋 {benchmark.title}</b>
          )}
        </>
      )}
      {view === VIEWS.JOB && selectedJob && (
        <>
          <span className="sep">›</span>
          <b>{selectedJobLabel || selectedJob.id}</b>
        </>
      )}
      {view === VIEWS.SUBMIT && (
        <>
          <span className="sep">›</span>
          <b>重新评测</b>
        </>
      )}
    </div>
  );

  return (
    <>
      <header>
        <div className="header-top">
          <h1>多图生图评测看板</h1>
          <span className="sub">流程：左侧选模型 → 选权重 → 选评测方法 → 提交参数</span>
        </div>
        <div className="header-tools">
          <span className="ver-chip">{hostLabel || '…'}</span>
          {judgeHint && <span className="ver-chip muted">裁判 {judgeHint}</span>}
          <button type="button" className="tool-btn" onClick={() => setJudgeOpen(true)}>裁判配置</button>
        </div>
      </header>

      <JudgeConfigModal
        open={judgeOpen}
        onClose={() => setJudgeOpen(false)}
        onSaved={(cfg) => setJudgeHint(cfg.model || '')}
      />

      {error && <div className="banner error">{error}</div>}
      {message && <div className="banner ok">{message}</div>}

      <div className="layout">
        <aside className="sidebar">
          <h2>模型</h2>
          {models.map((m) => (
            <button
              key={m.id}
              type="button"
              className={`run-card ${selectedModelId === m.id ? 'active' : ''}`}
              onClick={() => selectModel(m.id)}
            >
              <div className="rname">🧠 {m.label}</div>
              <div className="rmeta">{m.weights?.length || 0} 个权重 · {m.description}</div>
            </button>
          ))}
        </aside>

        <main>
          <>
            {crumb}
              {view === VIEWS.WEIGHTS && (
                <>
                  <div className="scopebar">当前模型：<b>{selectedModel?.label}</b>。请选择权重版本，再选择测评方法。</div>
                  <div className="section-title">选择权重版本</div>
                  <div className="benchgrid">
                    {(selectedModel?.weights || []).map((w) => (
                      <button key={w.id} type="button" className="bench-card" onClick={() => openWeight(w.id)}>
                        <div className="bname">⚖️ {w.label}{!w.builtin && <span className="tag-custom"> 自定义</span>}</div>
                        <div className="bench-intro">{w.available === false ? '路径不可用' : w.path}</div>
                        <div className="rmeta">选择测评方法 →</div>
                      </button>
                    ))}
                  </div>
                  <div className="section-title" style={{ marginTop: 24 }}>上传新权重</div>
                  {showWeightForm ? (
                    <SubmitWeightForm
                      modelId={selectedModelId}
                      onRegistered={async () => {
                        setShowWeightForm(false);
                        setMessage('权重已注册');
                        await refresh();
                      }}
                      onCancel={() => setShowWeightForm(false)}
                    />
                  ) : (
                    <button type="button" className="bench-card hub-card" onClick={() => setShowWeightForm(true)}>
                      <div className="bname">➕ 提交新权重</div>
                      <div className="bench-intro">填写服务器路径或上传 .safetensors / .bin 权重文件</div>
                    </button>
                  )}
                </>
              )}

              {view === VIEWS.BENCHMARKS && selectedWeight && (
                <>
                  <div className="scopebar">权重：<b>{selectedWeight.label}</b> · 请选择测评方法，再选测试版本。</div>
                  <div className="section-title">选择测评方法</div>
                  <div className="benchgrid">
                    {benchmarks.map((b) => (
                      <button key={b.id} type="button" className="bench-card" onClick={() => openBenchmark(b.id)}>
                        <div className="bname">📋 {b.title}</div>
                        <div className="bench-intro">{b.intro || b.description}</div>
                        <div className="rmeta">
                          {(scopedJobCount[b.id] || 0) > 0
                            ? `${scopedJobCount[b.id]} 次测试 · 查看版本 →`
                            : '暂无测试 · 点击进入 →'}
                        </div>
                      </button>
                    ))}
                  </div>
                </>
              )}

              {view === VIEWS.JOB && benchmark && selectedWeight && (
                <JobDetailView
                  job={selectedJob}
                  versionLabel={selectedJobLabel}
                  benchmarkTitle={benchmark.title}
                  weightLabel={selectedWeight.label}
                  gpus={gpus}
                  selectedGpus={selectedGpus}
                  toggleGpu={toggleGpu}
                  onCancel={cancelJob}
                  onResume={resumeJob}
                  onBack={backToVersions}
                />
              )}

              {view === VIEWS.VERSIONS && benchmark && selectedWeight && (
                <VersionListView
                  key={`${selectedModelId}-${selectedWeightId}-${selectedBenchmarkId}`}
                  modelId={selectedModelId}
                  weightId={selectedWeightId}
                  weightLabel={selectedWeight.label}
                  benchmark={benchmark}
                  selectedJobId={selectedJobId}
                  onSelectJob={selectJob}
                  onDeleteJob={deleteJob}
                  onNewRun={openNewRun}
                  onBackBenchmarks={() => {
                    setSelectedJobId(null);
                    setSelectedBenchmarkId(null);
                    setView(VIEWS.BENCHMARKS);
                  }}
                />
              )}

              {view === VIEWS.SUBMIT && benchmark && selectedWeight && (
                <SubmitForm
                  benchmark={benchmark}
                  params={params}
                  setParam={(k, v) => setParams((p) => ({ ...p, [k]: v }))}
                  datasetInfo={datasetInfo}
                  dynamicOptions={dynamicOptions}
                  gpus={gpus}
                  selectedGpus={selectedGpus}
                  toggleGpu={toggleGpu}
                  selectAllGpus={() => setSelectedGpus(gpus.map((g) => g.index))}
                  clearGpus={() => setSelectedGpus([])}
                  submitting={submitting}
                  onSubmit={submit}
                  onBack={() => setView(VIEWS.VERSIONS)}
                />
              )}
          </>
        </main>
      </div>
    </>
  );
}

function SubmitForm({
  benchmark, params, setParam, datasetInfo, dynamicOptions, gpus, selectedGpus,
  toggleGpu, selectAllGpus, clearGpus, submitting, onSubmit, onBack,
}) {
  const { groups, buckets } = groupParams(benchmark);
  const groupOrder = ['data', 'inference', 'eval', 'advanced'];

  return (
    <>
      <div className="version-head">
        <div className="section-title">提交评测参数</div>
        {onBack && (
          <button type="button" className="action-btn secondary" onClick={onBack}>← 返回版本列表</button>
        )}
      </div>
      <form className="formpanel" onSubmit={(e) => { e.preventDefault(); onSubmit(); }}>
        {groupOrder.map((groupKey) => {
          const fields = buckets[groupKey] || [];
          if (!fields.length) return null;
          const isData = groupKey === 'data';
          return (
            <div className="param-group" key={groupKey}>
              <div className="group-title">{groups[groupKey] || groupKey}</div>
              <div className={`form-grid ${isData ? 'form-grid-wide' : ''}`}>
                {fields.map((field) => (
                  <ParamField
                    key={field.key}
                    field={field}
                    value={params[field.key]}
                    onChange={setParam}
                    params={params}
                    dynamicOptions={dynamicOptions}
                  />
                ))}
              </div>
              {isData && datasetInfo && (
                <div className="scopebar dataset-scope">
                  预计 <b>{datasetInfo.label}</b>
                  {datasetInfo.metadata_total != null && (
                    <> · metadata 共 <b>{datasetInfo.metadata_total}</b> 条</>
                  )}
                  {' · '}{datasetInfo.task_count ?? '—'} 类 · 约 <b>{datasetInfo.total_samples}</b> 条
                </div>
              )}
            </div>
          );
        })}

        <div className="gpu-section">
          <div className="gpu-section-head">
            <div>
              <div className="gpu-title">GPU 选择</div>
              <div className="gpu-subtitle">多卡自动分片并行</div>
            </div>
            <div className="gpu-quick">
              <button type="button" onClick={selectAllGpus}>全选</button>
              <button type="button" onClick={clearGpus}>清空</button>
            </div>
          </div>
          <div className="gpu-section-body">
            <div className={`gpu-sel-summary ${selectedGpus.length ? '' : 'empty'}`}>
              {selectedGpus.length ? `已选 GPU：${selectedGpus.join(', ')}` : '请至少选择 1 张 GPU'}
            </div>
            <div className="gpu-grid">
              {gpus.map((g) => (
                <GpuCard key={g.index} gpu={g} selected={selectedGpus.includes(g.index)} onToggle={toggleGpu} />
              ))}
            </div>
          </div>
        </div>

        <button type="submit" className="action-btn" disabled={submitting}>
          {submitting ? '正在启动任务（模型预热约 3～8 分钟）…' : '启动评测'}
        </button>
      </form>
    </>
  );
}
