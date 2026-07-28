export function jobCanResume(job) {
  return ['cancelled', 'failed', 'interrupted'].includes(job?.status);
}

export function jobIsActive(job) {
  return job?.status === 'running';
}

export function isModelWarmup(job, phase) {
  const status = job?.status || '';
  const p = phase || job?.progress?.phase || '';
  if (p === 'evaluating' || p === 'pipeline' || status === 'evaluating') return false;
  if (p === 'loading_model' || p === 'queued') return true;
  if (!['queued', 'running'].includes(status)) return false;
  return (job?.progress?.gen_done ?? 0) < 1;
}

export function isEvalInline(job) {
  const params = job?.params || {};
  return !params.gen_only && !params.eval_only && params.eval_inline !== false;
}

export function warmupNotice(job, phase) {
  const genDone = job?.progress?.gen_done ?? 0;
  const genTotal = job?.progress?.gen_total ?? 0;
  const evalDone = job?.progress?.eval_done ?? 0;
  const evalTotal = job?.progress?.eval_total ?? 0;
  const weight = job?.weight_label || job?.model_path?.split('/').pop() || '模型';
  const isResume = genDone > 0 || (job?.resume_gen_snapshot ?? 0) > 0;

  if (phase === 'queued' || (job?.message || '').includes('排队')) {
    return {
      title: '⏳ 任务排队中',
      desc: `继续测试已提交，worker 正在启动。磁盘已有 ${genDone}/${genTotal} 张将跳过（评测 ${evalDone}/${evalTotal}）。启动后仍需重新加载模型约 3～8 分钟。`,
    };
  }
  if (isResume || phase === 'loading_model') {
    return {
      title: '⏳ 继续测试 · 模型重新加载中',
      desc: `进度按磁盘实时统计：生成 ${genDone}/${genTotal}，评测 ${evalDone}/${evalTotal}。模型预热约 3～8 分钟，加载完成后从第 ${genDone + 1} 张继续。`,
    };
  }
  return {
    title: '⏳ 模型预热加载中，请耐心等待',
    desc: `正在将 ${weight} 加载到所选 GPU（一卡一任务，N 卡 = N 路并行分片）。首次启动通常需要 3～8 分钟，加载完成后会自动开始出图与评测。`,
  };
}
