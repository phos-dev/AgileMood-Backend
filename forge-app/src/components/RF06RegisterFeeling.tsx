import React, { useState, useEffect } from 'react';
import {
  Text,
  Strong as RawStrong,
  SectionMessage as RawSectionMessage,
  Form,
  Select as RawSelect,
  Range as RawRange,
  Textfield as RawTextfield,
  Button,
} from '@forge/react';
const Strong = RawStrong as any;
const SectionMessage = RawSectionMessage as any;
const Select = RawSelect as any;
const Range = RawRange as any;
const Textfield = RawTextfield as any;
import { invoke } from '@forge/bridge';

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
  const [settingsLoaded, setSettingsLoaded] = useState(false);
  const [submitted, setSubmitted] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [emotionId, setEmotionId] = useState('1');
  const [intensity, setIntensity] = useState(3);
  const [notes, setNotes] = useState('');

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
        <Text>Peça ao gestor para configurar o app em Configurações → Apps → AgileMood.</Text>
      </SectionMessage>
    );
  }

  if (submitted) {
    return (
      <SectionMessage title="Sentimento registrado com sucesso!" appearance="confirmation" actions={[]} testId="sm-ok">
        <Text>Seu registro é 100% anônimo.</Text>
      </SectionMessage>
    );
  }

  const handleSubmit = async () => {
    setError(null);
    try {
      await invoke('registerEmotion', {
        emotionId,
        intensity,
        notes,
        teamId: settings.teamId,
        jwtToken: settings.jwtToken,
      });
      setSubmitted(true);
    } catch (e: any) {
      setError(`Erro ao registrar: ${e.message}`);
    }
  };

  return (
    <>
      <Text><Strong>Registrar Sentimento</Strong> — anônimo e confidencial</Text>
      {error && (
        <SectionMessage title={error} appearance="error" actions={[]} testId="sm-err">
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
