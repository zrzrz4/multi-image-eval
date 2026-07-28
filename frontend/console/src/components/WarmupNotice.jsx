import { isModelWarmup, warmupNotice } from '../utils/jobHelpers.js';

export default function WarmupNotice({ job }) {
  const phase = job?.progress?.phase;
  if (!job || !isModelWarmup(job, phase)) return null;
  const { title, desc } = warmupNotice(job, phase);
  return (
    <div className="warmup-box">
      <div className="warmup-title">{title}</div>
      <div className="warmup-desc">{desc}</div>
    </div>
  );
}
