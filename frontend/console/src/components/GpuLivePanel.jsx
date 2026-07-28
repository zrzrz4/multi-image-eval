import { useEffect, useState } from 'react';
import { isEvalInline, isModelWarmup, jobIsActive } from '../utils/jobHelpers.js';

const REFRESH_MS = 5000;

export default function GpuLivePanel({ job }) {
  const [gpus, setGpus] = useState([]);
  const [updatedAt, setUpdatedAt] = useState(0);

  const active = jobIsActive(job);
  const mine = new Set(job?.gpus || []);

  useEffect(() => {
    if (!active) return undefined;
    const load = () => {
      fetch('/api/console/gpus')
        .then((r) => (r.ok ? r.json() : null))
        .then((data) => {
          if (data?.gpus) {
            setGpus(data.gpus);
            setUpdatedAt(Date.now());
          }
        })
        .catch(() => {});
    };
    load();
    const timer = setInterval(load, REFRESH_MS);
    return () => clearInterval(timer);
  }, [active, job?.id]);

  if (!active) return null;

  const mineGpus = gpus.filter((g) => mine.has(g.index));
  const mineMemMax = mineGpus.reduce((m, g) => Math.max(m, g.memory_used_mb || 0), 0);
  const phase = job?.progress?.phase;
  const warmup = isModelWarmup(job, phase);
  const genDone = job?.progress?.gen_done ?? 0;
  const genTotal = job?.progress?.gen_total ?? 0;
  const evalDone = job?.progress?.eval_done ?? 0;
  const evalTotal = job?.progress?.eval_total ?? 0;
  const genActive = genTotal > 0 && genDone < genTotal;
  const evalActive = evalTotal > 0 && evalDone < evalTotal;
  const inline = isEvalInline(job);
  const pipeline = phase === 'pipeline' || (inline && phase === 'evaluating' && genActive);
  const evalTail = !genActive && evalActive;

  const ageSec = updatedAt ? Math.max(0, Math.round((Date.now() - updatedAt) / 1000)) : 0;
  const ageTxt = ageSec <= 1 ? '刚刚更新' : `${ageSec} 秒前更新`;

  let hint = null;
  if (evalTail) {
    hint = (
      <div className="gpu-warn-banner eval">
        生成已全部完成，当前仅剩 <b>Gemini API 评测</b>（不占 GPU）。显存可能仍被模型占用，但利用率接近 0% 属正常。
      </div>
    );
  } else if (pipeline && genActive) {
    hint = (
      <p className="field-hint" style={{ marginBottom: 10 }}>
        流水线并行：GPU 持续出图（利用率接近 100% 正常），Gemini 评测在后台 API 进行，两条进度可能不一致。
      </p>
    );
  } else if (warmup || (mineMemMax < 2048 && genActive)) {
    hint = (
      <div className="gpu-warn-banner">
        GPU 面板约每 {REFRESH_MS / 1000} 秒刷新；模型加载阶段（约 3～8 分钟）显存/利用率可能短暂显示 0，属正常现象。
      </div>
    );
  } else {
    hint = (
      <p className="field-hint" style={{ marginBottom: 10 }}>
        GPU 面板约每 {REFRESH_MS / 1000} 秒刷新（{ageTxt}）；显存/利用率非实时秒级。
      </p>
    );
  }

  return (
    <div className="gpu-live-panel">
      <div className="gtitle">🖥 GPU 资源实时状态（一卡一任务）</div>
      <p className="field-hint" style={{ margin: '6px 0 10px' }}>
        {mine.size
          ? `本任务使用 GPU ${[...mine].join(', ')}（${mine.size} 张卡 = ${mine.size} 路并行）`
          : '本任务 GPU 配置'}
      </p>
      {hint}
      <div className="gpu-live-grid">
        {gpus.map((g) => {
          const isMine = mine.has(g.index);
          const usedPct = g.memory_total_mb
            ? Math.min(100, Math.round((g.memory_used_mb || 0) / g.memory_total_mb * 100))
            : 0;
          const barColor = isMine ? 'var(--accent2)' : (g.utilization_pct > 10 ? 'var(--bad)' : 'var(--good)');
          const tag = isMine ? '本任务' : (g.utilization_pct > 10 ? '占用' : '空闲');
          return (
            <div key={g.index} className={`gpu-live-cell${isMine ? ' mine' : ''}`}>
              <div className="gid">GPU {g.index} · {tag}</div>
              <div className="gpu-live-meta">
                显存 {Math.round((g.memory_used_mb || 0) / 1024)}G / {Math.round((g.memory_total_mb || 0) / 1024)}G
                · 利用率 {g.utilization_pct ?? '-'}%
              </div>
              <div className="gpu-mem-bar">
                <i style={{ width: `${Math.max(usedPct, 2)}%`, background: barColor }} />
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
