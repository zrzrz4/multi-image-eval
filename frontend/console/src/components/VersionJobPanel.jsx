import { useEffect, useState } from 'react';
import GpuLivePanel from './GpuLivePanel.jsx';
import JobSamplesPanel from './JobSamplesPanel.jsx';
import ParallelProgress from './ParallelProgress.jsx';
import WarmupNotice from './WarmupNotice.jsx';
import { jobCanResume, jobIsActive } from '../utils/jobHelpers.js';

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

export default function VersionJobPanel({
  job, gpus, selectedGpus, toggleGpu, onCancel, onResume,
}) {
  const [liveJob, setLiveJob] = useState(job);
  const [resuming, setResuming] = useState(false);
  const canResume = jobCanResume(liveJob);
  const active = jobIsActive(liveJob);

  useEffect(() => {
    setLiveJob(job);
  }, [job]);

  useEffect(() => {
    if (liveJob.status !== 'running') return undefined;
    const timer = setInterval(() => {
      fetch(`/api/jobs/${liveJob.id}`)
        .then((r) => (r.ok ? r.json() : null))
        .then((data) => { if (data) setLiveJob(data); })
        .catch(() => {});
    }, 2000);
    return () => clearInterval(timer);
  }, [liveJob.id, liveJob.status]);

  return (
    <div className="version-job-panel">
      {canResume ? (
        <div className="param-group resume-panel">
          <div className="group-title">继续测试 · 选择 GPU</div>
          {liveJob.message && <p className="field-hint">{liveJob.message}</p>}
          <p className="field-hint">已生成的图片和评测结果会保留；重新启动后需重新加载模型约 3～8 分钟。</p>
          <div className="gpu-section compact">
            <div className="gpu-section-head">
              <div>
                <div className="gpu-title">选择 GPU</div>
                <div className="gpu-subtitle">每张卡同时只跑 1 个推理任务 · 选 N 张卡 = N 路并行</div>
              </div>
            </div>
            <div className="gpu-section-body">
              <div className={`gpu-sel-summary ${selectedGpus.length ? '' : 'empty'}`}>
                {selectedGpus.length
                  ? `已选 GPU：${selectedGpus.join(', ')} · ${selectedGpus.length} 路并行`
                  : '请至少选择 1 张 GPU'}
              </div>
              <div className="gpu-grid compact">
                {gpus.map((g) => (
                  <GpuCard key={g.index} gpu={g} selected={selectedGpus.includes(g.index)} onToggle={toggleGpu} />
                ))}
              </div>
            </div>
          </div>
          <div className="row-actions">
            <button
              type="button"
              className="action-btn"
              disabled={resuming || !selectedGpus.length}
              onClick={async () => {
                setResuming(true);
                try {
                  await onResume(liveJob.id, selectedGpus);
                } finally {
                  setResuming(false);
                }
              }}
            >
              {resuming ? '启动中…' : '▶ 继续测试'}
            </button>
          </div>
        </div>
      ) : (
        <>
          {active && <WarmupNotice job={liveJob} />}
          {active && <GpuLivePanel job={liveJob} />}
          {active ? <ParallelProgress job={liveJob} /> : (
            <div className="param-group">
              <div className="cat">
                <div className="top">
                  <span>生成</span>
                  <span className="s">{liveJob.progress?.gen_done ?? 0}/{liveJob.progress?.gen_total ?? 0}</span>
                </div>
              </div>
              <div className="cat" style={{ marginTop: 10 }}>
                <div className="top">
                  <span>评测</span>
                  <span className="s">{liveJob.progress?.eval_done ?? 0}/{liveJob.progress?.eval_total ?? 0}</span>
                </div>
              </div>
            </div>
          )}
          <JobSamplesPanel key={liveJob.id} job={liveJob} />
          <div className="row-actions">
            {active && (
              <button type="button" className="action-btn secondary" onClick={() => onCancel(liveJob.id)}>终止测试</button>
            )}
          </div>
        </>
      )}
    </div>
  );
}
