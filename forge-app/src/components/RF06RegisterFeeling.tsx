import * as ForgeUI from 'react';
import { useState, useEffect } from 'react';
import {
  Text,
  SectionMessage as RawSectionMessage,
  Form,
  Select as RawSelect,
  Range as RawRange,
  Textfield as RawTextfield,
  Button,
} from '@forge/react';
const SectionMessage = RawSectionMessage as any;
const Select = RawSelect as any;
const Range = RawRange as any;
const Textfield = RawTextfield as any;
import { kvs } from '@forge/kvs';

const API_URL = 'https://agilemood-backend-v2.vercel.app';

const EMOTIONS = [
  { label: 'Alegria', value: '1' },
  { label: 'Tristeza', value: '2' },
  { label: 'Raiva', value: '3' },
  { label: 'Medo', value: '4' },
  { label: 'Surpresa', value: '5' },
  { label: 'Nojo', value: '6' },
];

export default function RF06RegisterFeeling() {
  const [settings, setSettings] = useState<any>(null);
  const [submitted, setSubmitted] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [emotionId, setEmotionId] = useState('1');
  const [intensity, setIntensity] = useState(3);
  const [notes, setNotes] = useState('');

  useEffect(() => {
    kvs.get('agilemood-settings').then((s: any) => setSettings(s));
  }, []);

  if (!settings?.jwtToken) {
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

  const handleSubmit = async () => {
    setError(null);
    try {
      const resp = await fetch(`${API_URL}/emotion_record/`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${settings.jwtToken}`,
        },
        body: JSON.stringify({
          emotion_id: parseInt(emotionId, 10),
          intensity,
          notes,
          team_id: settings.teamId,
          is_anonymous: true,
        }),
      });
      if (!resp.ok) throw new Error(`${resp.status}`);
      setSubmitted(true);
    } catch (e: any) {
      setError(`Erro ao registrar: ${e.message}`);
    }
  };

  return (
    <>
      <Text>**Registrar Sentimento** — anônimo e confidencial</Text>
      {error && (
        <SectionMessage title={error} appearance="error">
          <Text> </Text>
        </SectionMessage>
      )}
      <Form onSubmit={handleSubmit}>
        <Select
          name="emotionId"
          options={EMOTIONS}
          defaultValue={EMOTIONS[0]}
          onChange={(opt: any) => setEmotionId(opt?.value ?? '1')}
        />
        <Range
          name="intensity"
          min={1}
          max={5}
          value={intensity}
          onChange={(v: number) => setIntensity(v)}
          step={1}
        />
        <Textfield
          name="notes"
          placeholder="Algum comentário adicional..."
          onChange={(e: any) => setNotes(e.target?.value ?? e)}
        />
        <Button type="submit">Registrar</Button>
      </Form>
    </>
  );
}
