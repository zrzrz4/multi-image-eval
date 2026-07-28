import { isEvalInline, isModelWarmup } from '../utils/jobHelpers.js';

function pct(done, total) {
  if (!total) return 0;
  return Math.min(100, Math.round((done / total) * 100));
}

export default function ParallelProgress({ job }) {
  const p = job?.progress || {};
  const genDone = p.gen_done ?? 0;
  const genTotal = p.gen_total ?? 0;
  const evalDone = p.eval_done ?? 0;
  const evalTotal = p.eval_total ?? 0;
  const phase = p.phase;
  const warmup = isModelWarmup(job, phase);
  const inline = isEvalInline(job);
  const genPct = pct(genDone, genTotal);
  const evalPct = pct(evalDone, evalTotal);
  const genActive = genTotal > 0 && genDone < genTotal;
  const evalActive = evalTotal > 0 && evalDone < evalTotal;
  const pipeline = phase === 'pipeline' || (inline && phase === 'evaluating' && genActive);
  const evalTail = !genActive && evalActive;

  if (!job || job.status !== 'running') return null;

  const title = warmup
    ? '⏳ 模型预热中（加载完成后再生成与评测）'
    : pipeline
      ? '⚡ 流水线并行：GPU 持续出图，Gemini API 后台评测'
      : evalTail
        ? '⏳ 生成已完成，收尾评测中（API 调用，GPU 空闲）'
        : inline
          ? '⚡ 生成与评测'
          : '⚡ 生成与评测分阶段运行';

  const genLabel = warmup
    ? ' · 模型预热中'
    : genActive ? ' · GPU 出图中' : ' · 已完成';
  const evalLabel = (warmup && phase !== 'evaluating' && phase !== 'pipeline')
    ? ' · 等待模型加载后开始'
    : evalActive ? ' · API 评分中' : ' · 已完成';

  return (
    <div className="parallel-status">
      <div className="ptitle">{title}</div>
      <div className="pgrid">
        <div className="pcell">
          <div>生成 <b>{genDone}/{genTotal}</b> ({genPct}%){genLabel}</div>
          <div className="mini-bar"><i style={{ width: `${genPct}%`, background: '#2563eb' }} /></div>
        </div>
        <div className="pcell">
          <div>评测 <b>{evalDone}/{evalTotal}</b> ({evalPct}%){evalLabel}</div>
          <div className="mini-bar"><i style={{ width: `${evalPct}%`, background: '#e11d48' }} /></div>
        </div>
      </div>
      {pipeline && !warmup && (
        <p className="hint">
          生成进度通常领先评测：GPU 不等 API 返回就继续出下一张；评测并发数由参数「评测并发数」控制。
        </p>
      )}
      {evalTail && (
        <p className="hint">
          全部图片已生成，正在等待剩余 Gemini 评测完成，此阶段 GPU 利用率为 0 属正常。
        </p>
      )}
    </div>
  );
}
