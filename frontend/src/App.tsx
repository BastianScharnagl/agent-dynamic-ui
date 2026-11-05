import React, { useState } from 'react';
import { UIRenderEvent } from './types/agui';
import { AdvancedDynamicForm } from './components/AdvancedDynamicForm';

const SESSION_ID = 'demo-session-1';

export const App: React.FC = () => {
  const [prompt, setPrompt] = useState('Erstelle eine neue Tabelle "users" mit den Spalten "id", "name" und "email".');
  const [messages, setMessages] = useState<string[]>([]);
  const [currentUI, setCurrentUI] = useState<UIRenderEvent | null>(null);
  const [status, setStatus] = useState<string>('bereit');

  const executeStream = async (payload: { prompt?: string; toolResponse?: any }) => {
    setStatus('Verarbeite...');
    const response = await fetch('http://localhost:8000/api/agent/stream', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ sessionId: SESSION_ID, ...payload })
    });

    const reader = response.body?.getReader();
    const decoder = new TextDecoder();
    let buffer = '';

    while (reader) {
      const { done, value } = await reader.read();
      if (done) break;

      buffer += decoder.decode(value, { stream: true });
      const parts = buffer.split('\n\n');
      buffer = parts.pop() || '';

      for (const block of parts) {
        const lines = block.split('\n');
        const event = lines.find(l => l.startsWith('event: '))?.replace('event: ', '');
        const dataStr = lines.find(l => l.startsWith('data: '))?.replace('data: ', '');
        if (!dataStr) continue;

        const data = JSON.parse(dataStr);
        if (event === 'STATUS_UPDATE') setStatus(data.status);
        if (event === 'TEXT_MESSAGE') setMessages(prev => [...prev, data.text]);
        if (event === 'UI_RENDER') setCurrentUI(data);
        if (event === 'RUN_COMPLETED') setStatus('Eingabe erforderlich');
      }
    }
  };

  const handleFormSubmit = (formData: Record<string, any>) => {
    if (!currentUI) return;
    
    const { callId, toolName } = currentUI;
    setCurrentUI(null); // Formular nach Absenden ausblenden

    executeStream({
      toolResponse: {
        toolName,
        callId,
        output: formData
      }
    });
  };

  return (
    <div style={{ maxWidth: '680px', margin: '40px auto', fontFamily: 'system-ui, sans-serif', padding: '0 16px' }}>
      <h2>Autonomes Generative-UI Cockpit</h2>
      <div style={{ marginBottom: '16px', color: '#64748b' }}>Status: <strong>{status}</strong></div>

      <div style={{ display: 'flex', gap: '8px', marginBottom: '24px' }}>
        <input
          style={{ flex: 1, padding: '10px', borderRadius: '6px', border: '1px solid #cbd5e1' }}
          value={prompt}
          onChange={(e) => setPrompt(e.target.value)}
        />
        <button
          onClick={() => executeStream({ prompt })}
          style={{ padding: '10px 20px', background: '#2563eb', color: '#fff', border: 'none', borderRadius: '6px', cursor: 'pointer' }}
        >
          Senden
        </button>
      </div>

      <div>
        {messages.map((m, idx) => (
          <div key={idx} style={{ background: '#f8fafc', padding: '12px', borderRadius: '6px', marginBottom: '8px', border: '1px solid #e2e8f0' }}>
            {m}
          </div>
        ))}

        {currentUI && (
          <AdvancedDynamicForm
            data={currentUI.component}
            onSubmit={handleFormSubmit}
          />
        )}
      </div>
    </div>
  );
};

export default App;