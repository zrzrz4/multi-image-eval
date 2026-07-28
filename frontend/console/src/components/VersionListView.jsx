import { useEffect, useState } from 'react';

const versionCache = new Map();

function cacheKey(modelId, weightId, benchmarkId) {
  return `${modelId}|${weightId}|${benchmarkId}`;
}

export function clearVersionListCache(modelId, weightId, benchmarkId) {
  if (modelId && weightId && benchmarkId) {
    versionCache.delete(cacheKey(modelId, weightId, benchmarkId));
  }
}

function statusClass(status) {
  if (status === 'completed') return 'ok';
  if (status === 'running') return 'run';
  if (status === 'failed' || status === 'cancelled' || status === 'interrupted') return 'bad';
  return '';
}

export default function VersionListView({
  modelId, weightId, weightLabel, benchmark,
  selectedJobId, onSelectJob, onDeleteJob,
  onNewRun, onBackBenchmarks,
}) {
  const key = modelId && weightId && benchmark?.id
    ? cacheKey(modelId, weightId, benchmark.id)
    : '';
  const [data, setData] = useState(() => (key ? versionCache.get(key) : null) ?? null);
  const [error, setError] = useState('');
  const [refreshing, setRefreshing] = useState(false);
  const [deletingId, setDeletingId] = useState('');

  const reload = () => {
    if (!modelId || !weightId || !benchmark?.id) return Promise.resolve();
    const ck = cacheKey(modelId, weightId, benchmark.id);
    setRefreshing(true);
    return fetch(`/api/console/versions?model_id=${encodeURIComponent(modelId)}&weight_id=${encodeURIComponent(weightId)}&benchmark=${encodeURIComponent(benchmark.id)}`)
      .then((r) => (r.ok ? r.json() : r.json().then((d) => Promise.reject(new Error(d.detail || r.status)))))
      .then((payload) => {
        versionCache.set(ck, payload);
        setData(payload);
        setError('');
      })
      .catch((e) => setError(e.message))
      .finally(() => setRefreshing(false));
  };

  useEffect(() => {
    if (!modelId || !weightId || !benchmark?.id) return undefined;
    const cached = versionCache.get(cacheKey(modelId, weightId, benchmark.id));
    if (cached) setData(cached);
    reload();
    const timer = setInterval(reload, 5000);
    return () => clearInterval(timer);
  }, [modelId, weightId, benchmark?.id]);

  const handleDelete = async (item, e) => {
    e.stopPropagation();
    if (!item.can_delete || deletingId) return;
    const host = item.source_host ? ` · ${item.source_host}` : '';
    const scope = item.read_only
      ? '\n将从公共盘删除该归档目录。'
      : '\n将删除本机 jobs / outputs / logs。';
    if (!window.confirm(`确定删除「${item.label}」？\n${item.id}${host}${scope}\n此操作不可恢复。`)) return;
    setDeletingId(item.id);
    setError('');
    try {
      const res = await fetch(`/api/jobs/${item.id}`, { method: 'DELETE' });
      const body = await res.json().catch(() => ({}));
      if (!res.ok) throw new Error(body.detail || `HTTP ${res.status}`);
      clearVersionListCache(modelId, weightId, benchmark.id);
      if (onDeleteJob) await onDeleteJob(item);
      await reload();
    } catch (err) {
      setError(err.message);
    } finally {
      setDeletingId('');
    }
  };

  return (
    <>
      <div className="version-head">
        <div>
          <div className="section-title">测试版本</div>
          <div className="scopebar">
            权重 <b>{weightLabel}</b> · 测评 <b>{benchmark?.title}</b>
            {data && <> · {data.group_count} 个参数组 · {data.total_runs} 次测试</>}
            {refreshing && data && <span className="refresh-hint"> · 刷新中…</span>}
          </div>
        </div>
        <button type="button" className="action-btn" onClick={onNewRun}>重新评测 / 提交</button>
      </div>
      <p className="field-hint">
        相同数据范围与推理/裁判参数会自动归为一个<strong>参数组</strong>；点击某次测试进入<strong>独立详情页</strong>查看案例样板与评分。已结束的测试可点<strong>删除</strong>清理记录。
      </p>
      {error && <div className="banner error compact">{error}</div>}
      {!data && !error && <div className="boot-empty">正在加载版本列表…</div>}
      {data && !data.groups.length && (
        <div className="empty-panel">
          暂无测试版本。点击右上角「重新评测 / 提交」开始第一次评测。
        </div>
      )}
      {data?.groups.map((group, gi) => (
        <div className="version-group" key={group.params_key}>
          <div className="version-group-title">
            参数组 {gi + 1}
            <span className="version-group-sub">{group.params_summary}</span>
          </div>
          <div className="version-grid">
            {group.items.map((item) => (
              <div
                key={item.id}
                role="button"
                tabIndex={0}
                className={`version-mini ${statusClass(item.status)} ${selectedJobId === item.id ? 'selected' : ''}`}
                onClick={() => onSelectJob(item.id, item.label)}
                onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') onSelectJob(item.id, item.label); }}
              >
                <div className="version-mini-top">
                  <div className="vtitle">{item.label}{item.source_host ? ` · ${item.source_host}` : ''}</div>
                  {item.can_delete && (
                    <button
                      type="button"
                      className="version-delete-btn"
                      disabled={deletingId === item.id}
                      onClick={(e) => handleDelete(item, e)}
                    >
                      {deletingId === item.id ? '…' : '删除'}
                    </button>
                  )}
                </div>
                <div className="vmeta">{item.id}</div>
                <div className={`vstatus ${statusClass(item.status)}`}>{item.progress_label}</div>
                {item.avg_score != null && (
                  <div className="vscore">均分 <b>{Number(item.avg_score).toFixed(2)}</b></div>
                )}
                {item.can_resume && (
                  <div className="version-actions">
                    <span className="link-hint">可继续测试 →</span>
                  </div>
                )}
              </div>
            ))}
          </div>
        </div>
      ))}

      <div className="row-actions" style={{ marginTop: 16 }}>
        <button type="button" className="action-btn secondary" onClick={onBackBenchmarks}>← 返回测评方法</button>
      </div>
    </>
  );
}
