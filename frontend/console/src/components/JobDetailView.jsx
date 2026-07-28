import VersionJobPanel from './VersionJobPanel.jsx';

export default function JobDetailView({
  job,
  versionLabel,
  benchmarkTitle,
  weightLabel,
  gpus,
  selectedGpus,
  toggleGpu,
  onCancel,
  onResume,
  onBack,
}) {
  if (!job) {
    return (
      <div className="empty-panel">
        未找到该测试任务。
        <div className="row-actions" style={{ marginTop: 12 }}>
          <button type="button" className="action-btn secondary" onClick={onBack}>← 返回测试版本</button>
        </div>
      </div>
    );
  }

  return (
    <div className="job-detail-page">
      <div className="version-head">
        <div>
          <div className="section-title">{versionLabel || '测试详情'}</div>
          <div className="scopebar">
            {benchmarkTitle} · 权重 <b>{weightLabel || job.weight_label}</b> · <code>{job.id}</code>
            · 裁判 {job.judge?.judge_model || '全局默认'}
          </div>
        </div>
        <button type="button" className="action-btn secondary" onClick={onBack}>← 返回测试版本</button>
      </div>
      <VersionJobPanel
        key={job.id}
        job={job}
        gpus={gpus}
        selectedGpus={selectedGpus}
        toggleGpu={toggleGpu}
        onCancel={onCancel}
        onResume={onResume}
      />
    </div>
  );
}
