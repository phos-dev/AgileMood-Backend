import React, { useState, useEffect } from 'react';
import {
  Text,
  Strong as RawStrong,
  Stack as RawStack,
  SectionMessage as RawSectionMessage,
  Textfield as RawTextfield,
  Button,
} from '@forge/react';
const Strong = RawStrong as any;
const Stack = RawStack as any;
const SectionMessage = RawSectionMessage as any;
const Textfield = RawTextfield as any;
import { invoke } from '@forge/bridge';

interface SettingsProps {
  onLogin?: () => void;
}

export default function Settings({ onLogin }: SettingsProps) {
  const [settings, setSettings] = useState<any>(null);
  const [error, setError] = useState<string | null>(null);
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    invoke<any>('getSettings').then((s: any) => {
      if (s?.jwtToken) setSettings(s);
    });
  }, []);

  const handleLogin = async () => {
    if (!email || !password) {
      setError('E-mail e senha são obrigatórios.');
      return;
    }
    setLoading(true);
    setError(null);
    try {
      const data = await invoke<any>('login', { email, password });
      let teamId = data.teamId ?? null;
      let teamName = '';
      if (!teamId && data.role === 'manager') {
        try {
          const team = await invoke<any>('getMyTeam', { jwtToken: data.access_token });
          teamId = team?.teamId ?? null;
          teamName = team?.teamName ?? '';
        } catch (_) { /* team lookup failed, proceed without */ }
      }
      const newSettings = {
        jwtToken: data.access_token,
        role: data.role,
        teamId,
        teamName,
        name: data.name,
        email: data.email,
      };
      await invoke('saveSettings', newSettings);
      setSettings(newSettings);
      setPassword('');
      onLogin?.();
    } catch (e: any) {
      setError(`Falha no login: ${e.message}. Verifique suas credenciais.`);
    } finally {
      setLoading(false);
    }
  };

  const handleDisconnect = async () => {
    await invoke('saveSettings', null);
    setSettings(null);
    setEmail('');
    setPassword('');
    onLogin?.();
  };

  if (settings?.jwtToken) {
    const roleLabel = settings.role === 'manager' ? 'Gestor' : 'Funcionário';
    const teamDisplay = settings.teamName || (settings.teamId ? String(settings.teamId) : null);
    return (
      <Stack space="space.200">
          <SectionMessage title="Conectado" appearance="confirmation" actions={[]} testId="sm-ok">
          <Text>{settings.name || settings.email} — <Strong>{roleLabel}</Strong></Text>
          <Text>Equipe: {teamDisplay ?? '—'}</Text>
        </SectionMessage>
        {!settings.teamId && (
          <SectionMessage title="Equipe não encontrada" appearance="warning" actions={[]} testId="sm-noteam">
            <Text>Verifique sua conta no AgileMood — você precisa estar associado a uma equipe.</Text>
          </SectionMessage>
        )}
        <Button type="button" onClick={handleDisconnect}>Desconectar</Button>
      </Stack>
    );
  }

  return (
    <Stack space="space.200">
      {error && (
        <SectionMessage title={error} appearance="error" actions={[]} testId="sm-err">
          <Text> </Text>
        </SectionMessage>
      )}
      <Textfield
        name="email"
        placeholder="E-mail"
        value={email}
        onChange={(e: any) => setEmail(e.target?.value ?? e)}
      />
      <Textfield
        name="password"
        type="password"
        placeholder="Senha"
        value={password}
        onChange={(e: any) => setPassword(e.target?.value ?? e)}
      />
      <Button type="button" onClick={handleLogin}>{loading ? 'Conectando...' : 'Entrar'}</Button>
    </Stack>
  );
}
