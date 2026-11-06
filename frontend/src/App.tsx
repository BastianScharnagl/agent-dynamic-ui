import React, { useState } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { UIRenderEvent } from './types/agui';
import { DynamicForm } from './components/DynamicForm';

const SESSION_ID = 'demo-session-1';

export const App: React.FC = () => {
  const [prompt, setPrompt] = useState('Erstelle eine neue Tabelle.');
  const [messages, setMessages] = useState<string[]>([]);
  const [currentUI, setCurrentUI] = useState<UIRenderEvent | null>(null);
  const [status, setStatus] = useState<string>('bereit');

  const sendPrompt = () => {
    const message = prompt.trim();
    if (!message) return;

    setPrompt('');
    void executeStream({ prompt: message });
  };

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
      <p style={{ color: '#475569', lineHeight: 1.5 }}>
        Beispiele: Erstelle eine Tabelle, füge Kunden hinzu, zeige oder
        ändere Datensätze, lösche Einträge, ergänze Tabellenspalten oder lass
        dir ein dynamisches Formular erstellen. Neue Tabellenspalten werden
        derzeit als TEXT angelegt.
      </p>
      <div style={{ marginBottom: '16px', color: '#64748b' }}>Status: <strong>{status}</strong></div>

      <div style={{ display: 'flex', gap: '8px', marginBottom: '24px' }}>
        <input
          style={{ flex: 1, padding: '10px', borderRadius: '6px', border: '1px solid #cbd5e1' }}
          value={prompt}
          onChange={(e) => setPrompt(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === 'Enter') sendPrompt();
          }}
        />
        <button
          onClick={sendPrompt}
          style={{ padding: '10px 20px', background: '#2563eb', color: '#fff', border: 'none', borderRadius: '6px', cursor: 'pointer' }}
        >
          Senden
        </button>
      </div>

      <div>
        {currentUI && (
          <DynamicForm
            data={currentUI.component}
            onSubmit={handleFormSubmit}
          />
        )}
        {[...messages].reverse().map((m, idx) => (
          <div key={idx} style={{ background: '#f8fafc', padding: '12px', borderRadius: '6px', marginBottom: '8px', border: '1px solid #e2e8f0', overflowWrap: 'anywhere' }}>
            <ReactMarkdown remarkPlugins={[remarkGfm]}>{m}</ReactMarkdown>
          </div>
        ))}
      </div>
    </div>
  );
};

export default App;