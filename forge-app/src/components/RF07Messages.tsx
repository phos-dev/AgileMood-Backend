import * as ForgeUI from 'react';
import { useState, useEffect } from 'react';
import {
  Text,
  SectionMessage as RawSectionMessage,
  DynamicTable as RawDynamicTable,
} from '@forge/react';
const SectionMessage = RawSectionMessage as any;
const DynamicTable = RawDynamicTable as any;
import { kvs } from '@forge/kvs';

const API_URL = 'https://agilemood-backend-v2.vercel.app';

export default function RF07Messages() {
  const [settings, setSettings] = useState<any>(null);
  const [messages, setMessages] = useState<any[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    kvs.get('agilemood-settings').then((s: any) => {
      setSettings(s);
      if (!s?.jwtToken) { setLoading(false); return; }
      fetch(
        `${API_URL}/feedback/?team_id=${s.teamId}`,
        { headers: { Authorization: `Bearer ${s.jwtToken}` } },
      )
        .then((r) => { if (!r.ok) throw new Error(`${r.status}`); return r.json(); })
        .then((data) => setMessages(Array.isArray(data) ? data : data.feedbacks || []))
        .catch((e: any) => setError(`Erro ao carregar mensagens: ${e.message}`))
        .finally(() => setLoading(false));
    });
  }, []);

  if (!settings?.jwtToken) {
    return (
      <SectionMessage title="AgileMood não configurado" appearance="warning">
        <Text>Peça ao gestor para configurar o app.</Text>
      </SectionMessage>
    );
  }

  if (loading) return <Text>Carregando mensagens...</Text>;
  if (error) return <SectionMessage title={error} appearance="error"><Text> </Text></SectionMessage>;
  if (messages.length === 0) return <Text>Nenhuma mensagem recebida ainda.</Text>;

  const head = { cells: [{ key: 'date', content: 'Data' }, { key: 'msg', content: 'Mensagem' }] };
  const rows = messages.map((msg, i) => ({
    key: String(i),
    cells: [
      { content: new Date(msg.created_at).toLocaleDateString('pt-BR') },
      { content: msg.content || msg.message || '' },
    ],
  }));

  return (
    <>
      <Text>**Mensagens Recebidas** — somente leitura</Text>
      <DynamicTable head={head} rows={rows} />
    </>
  );
}
