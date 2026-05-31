import React, { useState, useEffect } from 'react';
import {
  Text,
  Strong as RawStrong,
  Stack as RawStack,
  SectionMessage as RawSectionMessage,
  DynamicTable as RawDynamicTable,
} from '@forge/react';
const Strong = RawStrong as any;
const Stack = RawStack as any;
const SectionMessage = RawSectionMessage as any;
const DynamicTable = RawDynamicTable as any;
import { invoke } from '@forge/bridge';

export default function RF07Messages() {
  const [settings, setSettings] = useState<any>(null);
  const [messages, setMessages] = useState<any[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    invoke<any>('getSettings').then((s: any) => {
      setSettings(s);
      if (!s?.jwtToken) { setLoading(false); return; }
      invoke<any>('getMessages', { jwtToken: s.jwtToken })
        .then((data: any[]) => setMessages(data))
        .catch((e: any) => {
          if (e.message?.includes('401')) {
            setError('Sessão expirada. Desconecte e reconecte nas Configurações.');
          } else {
            setError(`Erro ao carregar mensagens: ${e.message}`);
          }
        })
        .finally(() => setLoading(false));
    });
  }, []);

  if (loading) return <Text>Carregando mensagens...</Text>;

  if (!settings?.jwtToken) {
    return (
      <SectionMessage title="AgileMood não configurado" appearance="warning" actions={[]} testId="sm-cfg">
        <Text>Peça ao gestor para configurar o app.</Text>
      </SectionMessage>
    );
  }

  if (error) {
    return (
      <SectionMessage title={error} appearance="error" actions={[]} testId="sm-err">
        <Text> </Text>
      </SectionMessage>
    );
  }

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
    <Stack space="space.200">
      <DynamicTable head={head} rows={rows} />
    </Stack>
  );
}
