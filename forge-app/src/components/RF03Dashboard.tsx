import React, { useState, useEffect } from 'react';
import {
  Text,
  Strong as RawStrong,
  Stack as RawStack,
  SectionMessage as RawSectionMessage,
  DynamicTable as RawDynamicTable,
  DatePicker as RawDatePicker,
  Button,
} from '@forge/react';
const Strong = RawStrong as any;
const Stack = RawStack as any;
const SectionMessage = RawSectionMessage as any;
const DynamicTable = RawDynamicTable as any;
const DatePicker = RawDatePicker as any;
import { invoke } from '@forge/bridge';

export default function RF03Dashboard() {
  const [settings, setSettings] = useState<any>(null);
  const [settingsLoaded, setSettingsLoaded] = useState(false);
  const [report, setReport] = useState<any>(null);
  const [startDate, setStartDate] = useState('');
  const [endDate, setEndDate] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    invoke<any>('getSettings').then((s: any) => {
      setSettings(s);
      setSettingsLoaded(true);
    });
  }, []);

  if (!settingsLoaded) return <Text>Carregando...</Text>;

  if (!settings?.jwtToken) {
    return (
      <SectionMessage title="AgileMood não configurado" appearance="warning" actions={[]} testId="sm-cfg">
        <Text>Configure o app em Configurações → Apps → AgileMood.</Text>
      </SectionMessage>
    );
  }

  if (!settings?.teamId) {
    return (
      <SectionMessage title="Equipe não configurada" appearance="warning" actions={[]} testId="sm-noteam">
        <Text>Sua conta não está associada a uma equipe. Verifique no AgileMood.</Text>
      </SectionMessage>
    );
  }

  const handleSubmit = async () => {
    setError(null);
    setLoading(true);
    try {
      const data = await invoke<any>('getMoodSummary', {
        teamId: settings.teamId,
        jwtToken: settings.jwtToken,
        startDate,
        endDate,
      });
      setReport(data);
    } catch (e: any) {
      setError(`Erro ao carregar dashboard: ${e.message}`);
    } finally {
      setLoading(false);
    }
  };

  const distHead = { cells: [{ key: 'emotion', content: 'Emoção' }, { key: 'freq', content: 'Frequência' }] };
  const distRows = (report?.dist?.emoji_distribution ?? []).map((e: any, i: number) => ({
    key: String(i),
    cells: [{ content: e.emotion_name }, { content: String(e.frequency) }],
  }));

  const intHead = { cells: [{ key: 'emotion', content: 'Emoção' }, { key: 'avg', content: 'Intensidade Média' }] };
  const intRows = (report?.intensity?.average_intensity ?? []).map((e: any, i: number) => ({
    key: String(i),
    cells: [{ content: e.emotion_name }, { content: e.avg_intensity?.toFixed(2) }],
  }));

  return (
    <Stack space="space.200">
      <DatePicker name="startDate" onChange={(v: string) => setStartDate(v)} />
      <DatePicker name="endDate" onChange={(v: string) => setEndDate(v)} />
      <Button type="button" onClick={handleSubmit}>{loading ? 'Carregando...' : 'Carregar'}</Button>
      {error && (
        <SectionMessage title={error} appearance="error" actions={[]} testId="sm-err">
          <Text> </Text>
        </SectionMessage>
      )}
      {report && (
        <>
          <Text><Strong>Alerta:</Strong> {report.dist.alert ?? '—'}</Text>
          <Text><Strong>Ratio Negativo:</Strong> {(report.dist.negative_emotion_ratio ?? 0).toFixed(1)}%</Text>
          {distRows.length > 0 && <DynamicTable head={distHead} rows={distRows} />}
          {intRows.length > 0 && <DynamicTable head={intHead} rows={intRows} />}
        </>
      )}
    </Stack>
  );
}
