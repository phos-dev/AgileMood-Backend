import ForgeUI, {
  Fragment,
  Form,
  TextField,
  Text,
  SectionMessage,
  useStorage,
  useState,
} from '@forge/ui';

export default function Settings() {
  const [settings, setSettings] = useStorage('agilemood-settings');
  const [error, setError] = useState(null);
  const [saved, setSaved] = useState(false);

  const handleSubmit = async (formData) => {
    const { apiUrl, jwtToken, teamId, webhookSecret } = formData;
    if (!apiUrl || !jwtToken || !teamId) {
      setError('Os campos URL da API, Token JWT e ID da Equipe são obrigatórios.');
      return;
    }
    try {
      const resp = await fetch(`${apiUrl}/teams/`, {
        headers: { Authorization: `Bearer ${jwtToken}` },
      });
      if (!resp.ok) throw new Error(`${resp.status}`);
    } catch (e) {
      setError(`Falha ao validar token: ${e.message}. Verifique a URL e o JWT.`);
      return;
    }
    await setSettings({
      apiUrl: apiUrl.replace(/\/$/, ''),
      jwtToken,
      teamId: parseInt(teamId, 10),
      webhookSecret: webhookSecret || '',
    });
    setSaved(true);
    setError(null);
  };

  return (
    <Fragment>
      <Text>**Configurações AgileMood**</Text>
      {saved && (
        <SectionMessage title="Configurações salvas com sucesso!" appearance="confirmation" />
      )}
      {error && <SectionMessage title={error} appearance="error" />}
      <Form onSubmit={handleSubmit} submitButtonText="Salvar">
        <TextField
          name="apiUrl"
          label="URL da API AgileMood"
          placeholder="https://seu-backend.com"
          defaultValue={settings?.apiUrl || ''}
        />
        <TextField
          name="jwtToken"
          label="Token JWT do Gestor"
          placeholder="eyJ..."
          defaultValue={settings?.jwtToken || ''}
        />
        <TextField
          name="teamId"
          label="ID da Equipe"
          placeholder="1"
          defaultValue={settings?.teamId ? String(settings.teamId) : ''}
        />
        <TextField
          name="webhookSecret"
          label="Webhook Secret (JIRA_WEBHOOK_SECRET do backend)"
          placeholder="segredo-compartilhado"
          defaultValue={settings?.webhookSecret || ''}
        />
      </Form>
    </Fragment>
  );
}
