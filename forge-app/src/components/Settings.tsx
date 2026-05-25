import * as ForgeUI from 'react';
import { useState, useEffect } from 'react';
import {
  Text,
  SectionMessage as RawSectionMessage,
  Form,
  Textfield as RawTextfield,
  Button,
} from '@forge/react';
const SectionMessage = RawSectionMessage as any;
const Textfield = RawTextfield as any;
import { kvs } from '@forge/kvs';

export default function Settings() {
  const [settings, setSettings] = useState<any>(null);
  const [error, setError] = useState<string | null>(null);
  const [saved, setSaved] = useState(false);
  const [apiUrl, setApiUrl] = useState('');
  const [jwtToken, setJwtToken] = useState('');
  const [teamId, setTeamId] = useState('');
  const [webhookSecret, setWebhookSecret] = useState('');

  useEffect(() => {
    kvs.get('agilemood-settings').then((s: any) => {
      if (s) {
        setSettings(s);
        setApiUrl(s.apiUrl || '');
        setJwtToken(s.jwtToken || '');
        setTeamId(s.teamId ? String(s.teamId) : '');
        setWebhookSecret(s.webhookSecret || '');
      }
    });
  }, []);

  const handleSubmit = async () => {
    if (!apiUrl || !jwtToken || !teamId) {
      setError('Os campos URL da API, Token JWT e ID da Equipe são obrigatórios.');
      return;
    }
    if (!apiUrl.startsWith('https://') && !apiUrl.startsWith('http://localhost')) {
      setError('A URL da API deve usar HTTPS (ex: https://seu-backend.com).');
      return;
    }
    try {
      const resp = await fetch(`${apiUrl}/teams/`, {
        headers: { Authorization: `Bearer ${jwtToken}` },
      });
      if (!resp.ok) throw new Error(`${resp.status}`);
    } catch (e: any) {
      setError(`Falha ao validar token: ${e.message}. Verifique a URL e o JWT.`);
      return;
    }
    const newSettings = {
      apiUrl: apiUrl.replace(/\/$/, ''),
      jwtToken,
      teamId: parseInt(teamId, 10),
      webhookSecret: webhookSecret || '',
    };
    await kvs.set('agilemood-settings', newSettings);
    setSettings(newSettings);
    setSaved(true);
    setError(null);
  };

  return (
    <>
      <Text>**Configurações AgileMood**</Text>
      {saved && (
        <SectionMessage title="Configurações salvas com sucesso!" appearance="confirmation">
          <Text> </Text>
        </SectionMessage>
      )}
      {error && (
        <SectionMessage title={error} appearance="error">
          <Text> </Text>
        </SectionMessage>
      )}
      <Form onSubmit={handleSubmit}>
        <Textfield
          name="apiUrl"
          placeholder="https://seu-backend.com"
          value={apiUrl}
          onChange={(e: any) => setApiUrl(e.target?.value ?? e)}
        />
        <Textfield
          name="jwtToken"
          placeholder="eyJ..."
          value={jwtToken}
          onChange={(e: any) => setJwtToken(e.target?.value ?? e)}
        />
        <Textfield
          name="teamId"
          placeholder="1"
          value={teamId}
          onChange={(e: any) => setTeamId(e.target?.value ?? e)}
        />
        <Textfield
          name="webhookSecret"
          placeholder="segredo-compartilhado"
          value={webhookSecret}
          onChange={(e: any) => setWebhookSecret(e.target?.value ?? e)}
        />
        <Button type="submit">Salvar</Button>
      </Form>
    </>
  );
}
