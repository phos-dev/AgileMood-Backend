import ForgeUI, {
  Fragment,
  Text,
  SectionMessage,
  Table,
  Head,
  Cell,
  Row,
  useStorage,
  useEffect,
  useState,
} from '@forge/ui';

export default function RF07Messages() {
  const [settings] = useStorage('agilemood-settings');
  const [messages, setMessages] = useState([]);
  const [error, setError] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(async () => {
    if (!settings?.apiUrl) {
      setLoading(false);
      return;
    }
    try {
      const resp = await fetch(
        `${settings.apiUrl}/feedback/?team_id=${settings.teamId}`,
        { headers: { Authorization: `Bearer ${settings.jwtToken}` } },
      );
      if (!resp.ok) throw new Error(`${resp.status}`);
      const data = await resp.json();
      setMessages(Array.isArray(data) ? data : data.feedbacks || []);
    } catch (e) {
      setError(`Erro ao carregar mensagens: ${e.message}`);
    } finally {
      setLoading(false);
    }
  }, []);

  if (!settings?.apiUrl) {
    return (
      <SectionMessage title="AgileMood não configurado" appearance="warning">
        <Text>Peça ao gestor para configurar o app.</Text>
      </SectionMessage>
    );
  }

  if (loading) return <Text>Carregando mensagens...</Text>;
  if (error) return <SectionMessage title={error} appearance="error" />;
  if (messages.length === 0) return <Text>Nenhuma mensagem recebida ainda.</Text>;

  return (
    <Fragment>
      <Text>**Mensagens Recebidas** — somente leitura</Text>
      <Table>
        <Head>
          <Cell><Text>Data</Text></Cell>
          <Cell><Text>Mensagem</Text></Cell>
        </Head>
        {messages.map((msg, i) => (
          <Row key={i}>
            <Cell><Text>{new Date(msg.created_at).toLocaleDateString('pt-BR')}</Text></Cell>
            <Cell><Text>{msg.content || msg.message || ''}</Text></Cell>
          </Row>
        ))}
      </Table>
    </Fragment>
  );
}
