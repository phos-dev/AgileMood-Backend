import ForgeUI, {
  Fragment,
  Text,
  SectionMessage,
  Table,
  Head,
  Cell,
  Row,
  Form,
  DatePicker,
  useStorage,
  useState,
} from '@forge/ui';

export default function RF03Dashboard() {
  const [settings] = useStorage('agilemood-settings');
  const [report, setReport] = useState(null);
  const [error, setError] = useState(null);
  const [loading, setLoading] = useState(false);

  if (!settings?.apiUrl) {
    return (
      <SectionMessage title="AgileMood não configurado" appearance="warning">
        <Text>Configure o app em Configurações → Apps → AgileMood.</Text>
      </SectionMessage>
    );
  }

  const handleLoad = async (formData) => {
    setError(null);
    setLoading(true);
    const { startDate, endDate } = formData;
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
    } catch (e) {
      setError(`Erro ao carregar dashboard: ${e.message}`);
    } finally {
      setLoading(false);
    }
  };

  return (
    <Fragment>
      <Text>**Dashboard AgileMood — Humor da Equipe**</Text>
      <Form onSubmit={handleLoad} submitButtonText="Carregar">
        <DatePicker name="startDate" label="Data inicial (opcional)" />
        <DatePicker name="endDate" label="Data final (opcional)" />
      </Form>
      {loading && <Text>Carregando...</Text>}
      {error && <SectionMessage title={error} appearance="error" />}
      {report && (
        <Fragment>
          <Text>**Nível de Alerta:** {report.alert_level ?? '—'}</Text>
          <Text>**Intensidade Média:** {report.avg_intensity?.toFixed(2) ?? '—'}</Text>
          {report.emotions && report.emotions.length > 0 && (
            <Table>
              <Head>
                <Cell><Text>Emoção</Text></Cell>
                <Cell><Text>Contagem</Text></Cell>
              </Head>
              {report.emotions.map((e, i) => (
                <Row key={i}>
                  <Cell><Text>{e.name || e.emotion}</Text></Cell>
                  <Cell><Text>{e.count}</Text></Cell>
                </Row>
              ))}
            </Table>
          )}
        </Fragment>
      )}
    </Fragment>
  );
}
