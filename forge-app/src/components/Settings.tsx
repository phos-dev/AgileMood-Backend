import React, { useState, useEffect } from 'react';
import {
  Text,
  Strong as RawStrong,
  Stack as RawStack,
  SectionMessage as RawSectionMessage,
  Textfield as RawTextfield,
  Button,
  Form as RawForm,
  Select as RawSelect,
} from '@forge/react';
const Strong = RawStrong as any;
const Stack = RawStack as any;
const SectionMessage = RawSectionMessage as any;
const Textfield = RawTextfield as any;
const Form = RawForm as any;
const Select = RawSelect as any;
import { invoke } from '@forge/bridge';

interface SettingsProps {
  onLogin?: () => void;
  refreshKey?: number;
}

export default function Settings({ onLogin, refreshKey = 0 }: SettingsProps) {
  const [settings, setSettings] = useState<any>(null);
  const [error, setError] = useState<string | null>(null);
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [loading, setLoading] = useState(false);
  const [projectStatus, setProjectStatus] = useState<any>(null);
  const [teams, setTeams] = useState<{ id: number; name: string }[]>([]);
  const [connectingTeam, setConnectingTeam] = useState(false);

  useEffect(() => {
    setTeams([]);
    setProjectStatus(null);
    invoke<any>('getSettings').then((s: any) => {
      if (s?.jwtToken) {
        setSettings(s);
        if (s.role === 'manager') {
          Promise.all([
            invoke<any>('getProjectStatus'),
            invoke<any>('getMyTeams', { jwtToken: s.jwtToken }).catch(() => []),
          ]).then(([status, allTeams]: any[]) => {
            setTeams(allTeams);
            if (allTeams.length > 0 && status?.teamId) {
              const teamName = allTeams.find((t: any) => t.id === status.teamId)?.name ?? '';
              if (teamName) setSettings((prev: any) => ({ ...prev, teamName }));
            }
            setProjectStatus(status ?? { connected: false, teamId: null });
          });
        }
      }
    });
  }, [refreshKey]);

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
      if (data.role === 'manager' && teamId) {
        const existingStatus = await invoke<any>('getProjectStatus').catch(() => null);
        if (!existingStatus?.connected) {
          await invoke('connectProject', { teamId });
          setProjectStatus({ connected: true, teamId });
        } else {
          setProjectStatus(existingStatus);
        }
      }
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
    await invoke('saveSettings', undefined);
    setSettings(null);
    setTeams([]);
    setProjectStatus(null);
    setEmail('');
    setPassword('');
    onLogin?.();
  };

  if (settings?.jwtToken) {
    const roleLabel = settings.role === 'manager' ? 'Gestor' : 'Funcionário';
    const connectedTeamName = teams.find(t => t.id === projectStatus?.teamId)?.name;
    const teamDisplay = connectedTeamName || settings.teamName || (settings.teamId ? String(settings.teamId) : null);
    const teamOptions = teams.map(t => ({ label: t.name, value: String(t.id) }));
    const selectedTeamOption = teamOptions.find(o => o.value === String(projectStatus?.teamId)) ?? null;

    return (
      <Stack space="space.200">
        <SectionMessage title="Conectado" appearance="confirmation" actions={[]} testId="sm-ok">
          <Text>{settings.name || settings.email} — <Strong>{roleLabel}</Strong></Text>
          <Text>Equipe: {teamDisplay ?? '—'}</Text>
        </SectionMessage>
        {!settings.teamId && settings.role !== 'manager' && (
          <SectionMessage title="Equipe não encontrada" appearance="warning" actions={[]} testId="sm-noteam">
            <Text>Verifique sua conta no AgileMood — você precisa estar associado a uma equipe.</Text>
          </SectionMessage>
        )}
        {settings.role === 'manager' && projectStatus !== null && (
          projectStatus.connected
            ? <Stack space="space.100">
                <SectionMessage title="Integração Jira ativa" appearance="confirmation" actions={[]} testId="sm-jira-ok">
                  <Text>Sprints detectados automaticamente ao encerrar no Jira.</Text>
                </SectionMessage>
                {teams.length > 0 && (
                  <Stack space="space.100">
                    <Text><Strong>Time vinculado a este projeto:</Strong></Text>
                    <Select
                      name="project-team"
                      options={teamOptions}
                      value={selectedTeamOption}
                      onChange={async (opt: any) => {
                        if (!opt || connectingTeam) return;
                        setConnectingTeam(true);
                        const newTeamId = parseInt(opt.value, 10);
                        await invoke('connectProject', { teamId: newTeamId });
                        setProjectStatus((prev: any) => ({ ...prev, teamId: newTeamId }));
                        setConnectingTeam(false);
                      }}
                    />
                    {connectingTeam && <Text>Atualizando...</Text>}
                  </Stack>
                )}
                <SectionMessage title="Desconectar integração" appearance="warning" actions={[]} testId="sm-jira-disconnect-info">
                  <Text>Ao desconectar, sprints futuros não serão mais detectados automaticamente e o questionário de Segurança Psicológica não será acionado. Os dados históricos já registados são preservados.</Text>
                </SectionMessage>
                <Button type="button" onClick={async () => {
                  try {
                    await invoke('disconnectJira', { teamId: projectStatus.teamId, jwtToken: settings.jwtToken });
                  } catch (_) { /* already disconnected or backend error — proceed anyway */ }
                  setProjectStatus({ connected: false, teamId: null });
                }}>Desconectar integração Jira</Button>
              </Stack>
            : <Stack space="space.100">
                <SectionMessage title="Jira não conectado" appearance="warning" actions={[]} testId="sm-jira-warn">
                  <Text>Conecte este projeto para detectar sprints automaticamente.</Text>
                </SectionMessage>
                {teams.length > 0 && (
                  <Stack space="space.100">
                    <Text><Strong>Time a vincular:</Strong></Text>
                    <Select
                      name="project-team-connect"
                      options={teamOptions}
                      value={selectedTeamOption}
                      onChange={(opt: any) => {
                        if (!opt) return;
                        setProjectStatus((prev: any) => ({ ...prev, teamId: parseInt(opt.value, 10) }));
                      }}
                    />
                  </Stack>
                )}
                <Button type="button" onClick={async () => {
                  const teamIdToConnect = projectStatus?.teamId ?? settings.teamId;
                  await invoke('connectProject', { teamId: teamIdToConnect });
                  setProjectStatus({ connected: true, teamId: teamIdToConnect });
                }}>Conectar este projeto</Button>
              </Stack>
        )}
        <Button type="button" onClick={handleDisconnect}>Desconectar</Button>
      </Stack>
    );
  }

  return (
    <Form onSubmit={handleLogin}>
      <Stack space="space.200">
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
        {error && (
          <SectionMessage title={error} appearance="error" actions={[]} testId="sm-err">
            <Text> </Text>
          </SectionMessage>
        )}
        <Button type="submit">{loading ? 'Conectando...' : 'Entrar'}</Button>
      </Stack>
    </Form>
  );
}
