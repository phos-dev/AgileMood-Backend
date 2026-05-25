import * as ForgeUI from 'react';
import { useState, useEffect } from 'react';
import {
  Text,
  SectionMessage as RawSectionMessage,
  DynamicTable as RawDynamicTable,
  Form,
  DatePicker as RawDatePicker,
  Button,
} from '@forge/react';
const SectionMessage = RawSectionMessage as any;
const DynamicTable = RawDynamicTable as any;
const DatePicker = RawDatePicker as any;
import { kvs } from '@forge/kvs';

export default function RF03Dashboard() {
  const [settings, setSettings] = useState<any>(null);
  const [report, setReport] = useState<any>(null);
  const [startDate, setStartDate] = useState('');
  const [endDate, setEndDate] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    kvs.get('agilemood-settings').then((s: any) => setSettings(s));
  }, []);

  if (!settings?.apiUrl) {
    return (
      <SectionMessage title="AgileMood não configurado" appearance="warning">
        <Text>Configure o app em Configurações → Apps → AgileMood.</Text>
      </SectionMessage>
    );
  }

  const handleSubmit = async () => {
    setError(null);
    setLoading(true);
    try {
      const params = new URLSearchParams({ team_id: settings.teamId });
      if (startDate) params.set('start_date', startDate);
      if (endDate) params.set('end_date', endDate);
      const resp = await fetch(
        `${settings.apiUrl}/reports/mood-summary?${params}`,
        { headers: { Authorization: `Bearer ${settings.jwtToken}` } },
      );
      if (!resp.ok) throw new Error(`${resp.status}`);
      setReport(await resp.json());
    } catch (e: any) {
      setError(`Erro ao carregar dashboard: ${e.message}`);
    } finally {
      setLoading(false);
    }
  };

  const head = { cells: [{ key: 'emotion', content: 'Emoção' }, { key: 'count', content: 'Contagem' }] };
  const rows = (report?.emotions ?? []).map((e: any, i: number) => ({
    key: String(i),
    cells: [{ content: e.name || e.emotion }, { content: String(e.count) }],
  }));

  return (
    <>
      <Text>**Dashboard AgileMood — Humor da Equipe**</Text>
      <Form onSubmit={handleSubmit}>
        <DatePicker name="startDate" onChange={(v: string) => setStartDate(v)} />
        <DatePicker name="endDate" onChange={(v: string) => setEndDate(v)} />
        <Button type="submit">{loading ? 'Carregando...' : 'Carregar'}</Button>
      </Form>
      {error && (
        <SectionMessage title={error} appearance="error">
          <Text> </Text>
        </SectionMessage>
      )}
      {report && (
        <>
          <Text>**Nível de Alerta:** {report.alert_level ?? '—'}</Text>
          <Text>**Intensidade Média:** {report.avg_intensity?.toFixed(2) ?? '—'}</Text>
          {rows.length > 0 && <DynamicTable head={head} rows={rows} />}
        </>
      )}
    </>
  );
}
