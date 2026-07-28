import { useState } from 'react';

export default function SubmitWeightForm({ modelId, onRegistered, onCancel }) {
  const [label, setLabel] = useState('');
  const [path, setPath] = useState('');
  const [file, setFile] = useState(null);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState('');

  const submit = async (e) => {
    e.preventDefault();
    setError('');
    if (!label.trim()) return setError('请填写权重名称');
    if (!path.trim() && !file) return setError('请填写服务器路径或上传权重文件');

    setSubmitting(true);
    try {
      const fd = new FormData();
      fd.append('model_id', modelId);
      fd.append('label', label.trim());
      fd.append('path', path.trim());
      if (file) fd.append('weight_file', file);
      const res = await fetch('/api/console/weights', { method: 'POST', body: fd });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || `HTTP ${res.status}`);
      onRegistered?.(data);
    } catch (err) {
      setError(err.message);
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <form className="formpanel weight-form" onSubmit={submit}>
      <div className="group-title">提交新权重</div>
      <p className="field-hint">模型固定为 FireRed；上传 LoRA/权重或填写服务器路径，注册后可选择该权重进行测评。</p>
      {error && <div className="banner error compact">{error}</div>}
      <label className="form-field">
        <span className="field-label">权重名称 *</span>
        <input value={label} onChange={(e) => setLabel(e.target.value)} placeholder="例如 my-lora-v1" />
      </label>
      <label className="form-field">
        <span className="field-label">服务器路径</span>
        <input value={path} onChange={(e) => setPath(e.target.value)} placeholder="/path/to/your/model" />
      </label>
      <label className="form-field">
        <span className="field-label">或上传文件</span>
        <input type="file" accept=".safetensors,.bin,.pt,.pth" onChange={(e) => setFile(e.target.files?.[0] || null)} />
      </label>
      <div className="row-actions">
        <button type="submit" className="action-btn" disabled={submitting}>
          {submitting ? '注册中…' : '注册权重'}
        </button>
        {onCancel && (
          <button type="button" className="action-btn secondary" onClick={onCancel}>取消</button>
        )}
      </div>
    </form>
  );
}
