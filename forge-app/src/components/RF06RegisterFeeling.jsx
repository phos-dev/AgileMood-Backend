import ForgeUI, {
  Fragment,
  Form,
  Select,
  Option,
  Range,
  TextField,
  Text,
  SectionMessage,
  useStorage,
  useState,
} from '@forge/ui';

const EMOTIONS = [
  { value: '1', label: 'Alegria' },
  { value: '2', label: 'Tristeza' },
  { value: '3', label: 'Raiva' },
  { value: '4', label: 'Medo' },
  { value: '5', label: 'Surpresa' },
  { value: '6', label: 'Nojo' },
];

export default function RF06RegisterFeeling() {
  const [settings] = useStorage('agilemood-settings');
  const [submitted, setSubmitted] = useState(false);
  const [error, setError] = useState(null);

  if (!settings?.apiUrl) {
    return (
      <SectionMessage title="AgileMood não configurado" appearance="warning">
        <Text>Peça ao gestor para configurar o app em Configurações → Apps → AgileMood.</Text>
      </SectionMessage>
    );
  }

  if (submitted) {
    return (
      <SectionMessage title="Sentimento registrado com sucesso!" appearance="confirmation">
        <Text>Seu registro é 100% anônimo.</Text>
      </SectionMessage>
    );
  }

  const handleSubmit = async (formData) => {
    setError(null);
    const { emotionId, intensity, notes } = formData;
    try {
      const resp = await fetch(`${settings.apiUrl}/emotion_record/`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${settings.jwtToken}`,
        },
        body: JSON.stringify({
          emotion_id: parseInt(emotionId, 10),
          intensity: parseInt(intensity, 10),
          notes: notes || '',
          team_id: settings.teamId,
          is_anonymous: true,
        }),
      });
      if (!resp.ok) throw new Error(`${resp.status}`);
      setSubmitted(true);
    } catch (e) {
      setError(`Erro ao registrar: ${e.message}`);
    }
  };

  return (
    <Fragment>
      <Text>**Registrar Sentimento** — anônimo e confidencial</Text>
      {error && <SectionMessage title={error} appearance="error" />}
      <Form onSubmit={handleSubmit} submitButtonText="Registrar">
        <Select name="emotionId" label="Como você está se sentindo?">
          {EMOTIONS.map((e) => (
            <Option key={e.value} label={e.label} value={e.value} />
          ))}
        </Select>
        <Range
          name="intensity"
          label="Intensidade (1–5)"
          min={1}
          max={5}
          defaultValue={3}
          step={1}
        />
        <TextField
          name="notes"
          label="Notas (opcional)"
          placeholder="Algum comentário adicional..."
        />
      </Form>
    </Fragment>
  );
}
