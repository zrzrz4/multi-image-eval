import { useEffect, useState } from 'react';

export default function JudgeConfigModal({ open, onClose, onSaved }) {
  const [config, setConfig] = useState(null);
  const [baseUrl, setBaseUrl] = useState('');
  const [model, setModel] = useState('');
  const [apiKey, setApiKey] = useState('');
  const [models, setModels] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  useEffect(() => {
    if (!open) return;
    setError('');
    fetch('/api/console/judge-config')
      .then((r) => r.json())
      .then((data) => {
        setConfig(data);
        setBaseUrl(data.base_url || '');
        setModel(data.model || '');
      })
      .catch((e) => setError(e.message));
  }, [open]);

  const listModels = async () => {
    setError('');
    setLoading(true);
    try {
      const res = await fetch('/api/console/judge-models', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          base_url: baseUrl || undefined,
          api_key: apiKey || undefined,
        }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || `HTTP ${res.status}`);
      setModels(data.models || []);
      if (data.models?.length && !model) setModel(data.models[0]);
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  };

  const save = async () => {
    setError('');
    setLoading(true);
    try {
      const res = await fetch('/api/console/judge-config', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          base_url: baseUrl,
          model,
          api_key: apiKey || undefined,
        }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || `HTTP ${res.status}`);
      setConfig(data);
      setApiKey('');
      onSaved?.(data);
      onClose();
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  };

  if (!open) return null;

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal judge-modal" onClick={(e) => e.stopPropagation()}>
        <button type="button" className="modal-close" onClick={onClose}>×</button>
        <h3>裁判配置（全局默认）</h3>
        <p className="field-hint">所有评测任务默认使用此网关；提交时可单独覆盖裁判模型。</p>
        {config && (
          <p className="field-hint">
            当前 Key：{config.api_key_configured ? config.api_key_masked : '未配置'}
          </p>
        )}
        {error && <div className="banner error compact">{error}</div>}
        <label className="form-field">
          <span className="field-label">Base URL</span>
          <input value={baseUrl} onChange={(e) => setBaseUrl(e.target.value)} placeholder="https://..." />
        </label>
        <label className="form-field">
          <span className="field-label">API Key（留空则不修改）</span>
          <input type="password" value={apiKey} onChange={(e) => setApiKey(e.target.value)} placeholder="sk-..." />
        </label>
        <div className="form-field">
          <span className="field-label">裁判模型</span>
          <div className="judge-model-row">
            <select value={model} onChange={(e) => setModel(e.target.value)}>
              {model && !models.includes(model) && <option value={model}>{model}</option>}
              {models.map((m) => <option key={m} value={m}>{m}</option>)}
            </select>
            <button type="button" className="tool-btn" onClick={listModels} disabled={loading}>
              {loading ? '拉取中…' : '拉取模型列表'}
            </button>
          </div>
        </div>
        <div className="row-actions">
          <button type="button" className="action-btn" onClick={save} disabled={loading}>保存</button>
          <button type="button" className="action-btn secondary" onClick={onClose}>取消</button>
        </div>
      </div>
    </div>
  );
}
