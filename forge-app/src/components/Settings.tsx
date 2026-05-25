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

const API_URL = 'https://agilemood-backend-v2.vercel.app';

export default function Settings() {
  const [settings, setSettings] = useState<any>(null);
  const [error, setError] = useState<string | null>(null);
  const [teamId, setTeamId] = useState('');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    kvs.get('agilemood-settings').then((s: any) => {
      if (s?.jwtToken) setSettings(s);
    });
  }, []);

  const handleLogin = async () => {
    if (!teamId || !email || !password) {
      setError('ID da Equipe, e-mail e senha são obrigatórios.');
      return;
    }
    setLoading(true);
    setError(null);
    try {
      const resp = await fetch(`${API_URL}/user/login`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
        body: new URLSearchParams({ username: email, password }).toString(),
      });
      if (!resp.ok) throw new Error(`${resp.status}`);
      const data = await resp.json();
      const newSettings = { teamId: parseInt(teamId, 10), jwtToken: data.access_token, email };
      await kvs.set('agilemood-settings', newSettings);
      setSettings(newSettings);
      setPassword('');
    } catch (e: any) {
      setError(`Falha no login: ${e.message}. Verifique suas credenciais.`);
    } finally {
      setLoading(false);
    }
  };

  const handleDisconnect = async () => {
    await kvs.set('agilemood-settings', null);
    setSettings(null);
    setTeamId('');
    setEmail('');
    setPassword('');
  };

  if (settings?.jwtToken) {
    return (
      <ForgeUI.Fragment>
        <Text>**Configurações AgileMood**</Text>
        <SectionMessage title="App conectado!" appearance="confirmation">
          <Text>Equipe: {String(settings.teamId)} — {settings.email || 'conectado'}</Text>
        </SectionMessage>
        <Button type="button" onClick={handleDisconnect}>Desconectar</Button>
      </ForgeUI.Fragment>
    );
  }

  return (
    <ForgeUI.Fragment>
      <Text>**Configurações AgileMood**</Text>
      {error && (
        <SectionMessage title={error} appearance="error">
          <Text> </Text>
        </SectionMessage>
      )}
      <Form onSubmit={handleLogin}>
        <Textfield
          name="teamId"
          placeholder="ID da Equipe (ex: 1)"
          value={teamId}
          onChange={(e: any) => setTeamId(e.target?.value ?? e)}
        />
        <Textfield
          name="email"
          placeholder="E-mail do gestor"
          value={email}
          onChange={(e: any) => setEmail(e.target?.value ?? e)}
        />
        <Textfield
          name="password"
          placeholder="Senha"
          value={password}
          onChange={(e: any) => setPassword(e.target?.value ?? e)}
        />
        <Button type="submit">{loading ? 'Conectando...' : 'Conectar'}</Button>
      </Form>
    </ForgeUI.Fragment>
  );
}
