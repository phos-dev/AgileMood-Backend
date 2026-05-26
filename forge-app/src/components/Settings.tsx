import React, { useState, useEffect } from 'react';
import {
  Text,
  Strong as RawStrong,
  SectionMessage as RawSectionMessage,
  Form,
  Textfield as RawTextfield,
  Button,
} from '@forge/react';
const Strong = RawStrong as any;
const SectionMessage = RawSectionMessage as any;
const Textfield = RawTextfield as any;
import { invoke } from '@forge/bridge';

export default function Settings() {
  const [settings, setSettings] = useState<any>(null);
  const [error, setError] = useState<string | null>(null);
  const [teamId, setTeamId] = useState('');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    invoke<any>('getSettings').then((s: any) => {
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
      const data = await invoke<any>('login', { email, password });
      const newSettings = { teamId: parseInt(teamId, 10), jwtToken: data.access_token, email };
      await invoke('saveSettings', newSettings);
      setSettings(newSettings);
      setPassword('');
    } catch (e: any) {
      setError(`Falha no login: ${e.message}. Verifique suas credenciais.`);
    } finally {
      setLoading(false);
    }
  };

  const handleDisconnect = async () => {
    await invoke('saveSettings', null);
    setSettings(null);
    setTeamId('');
    setEmail('');
    setPassword('');
  };

  if (settings?.jwtToken) {
    return (
      <>
        <Text><Strong>Configurações AgileMood</Strong></Text>
        <SectionMessage title="App conectado!" appearance="confirmation" actions={[]} testId="sm-ok">
          <Text>Equipe: {String(settings.teamId)} — {settings.email || 'conectado'}</Text>
        </SectionMessage>
        <Button type="button" onClick={handleDisconnect}>Desconectar</Button>
      </>
    );
  }

  return (
    <>
      <Text>**Configurações AgileMood**</Text>
      {error && (
        <SectionMessage title={error} appearance="error" actions={[]} testId="sm-err">
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
    </>
  );
}
