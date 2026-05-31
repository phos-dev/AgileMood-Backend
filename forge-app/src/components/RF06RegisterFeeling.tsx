import React, { useState, useEffect } from 'react';
import {
  Text,
  Strong as RawStrong,
  Stack as RawStack,
  SectionMessage as RawSectionMessage,
  Select as RawSelect,
  Range as RawRange,
  Textfield as RawTextfield,
  Checkbox as RawCheckbox,
  Button,
} from '@forge/react';
const Strong = RawStrong as any;
const Stack = RawStack as any;
const SectionMessage = RawSectionMessage as any;
const Select = RawSelect as any;
const Range = RawRange as any;
const Textfield = RawTextfield as any;
const Checkbox = RawCheckbox as any;
import { invoke } from '@forge/bridge';

export default function RF06RegisterFeeling() {
  const [settings, setSettings] = useState<any>(null);
  const [settingsLoaded, setSettingsLoaded] = useState(false);
  const [emotions, setEmotions] = useState<any[]>([]);
  const [emotionsLoaded, setEmotionsLoaded] = useState(false);
  const [emotionsError, setEmotionsError] = useState<string | null>(null);
  const [submitted, setSubmitted] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [emotionId, setEmotionId] = useState<string>('');
  const [intensity, setIntensity] = useState(3);
  const [notes, setNotes] = useState('');
  const [isAnonymous, setIsAnonymous] = useState(true);

  useEffect(() => {
    invoke<any>('getSettings').then((s: any) => {
      setSettings(s);
      setSettingsLoaded(true);
      if (s?.teamId) {
        invoke<any>('getEmotions', { teamId: s.teamId })
          .then((data: any[]) => {
            setEmotions(data);
            if (data.length > 0) setEmotionId(String(data[0].id));
            setEmotionsLoaded(true);
          })
          .catch((e: any) => {
            setEmotionsError(`Erro ao carregar emoções: ${e.message}`);
            setEmotionsLoaded(true);
          });
      } else {
        setEmotionsLoaded(true);
      }
    });
  }, []);

  if (!settingsLoaded) return <Text>Carregando...</Text>;

  if (!settings?.jwtToken) {
    return (
      <SectionMessage title="AgileMood não configurado" appearance="warning" actions={[]} testId="sm-cfg">
        <Text>Faça login na aba Configurações.</Text>
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

  if (submitted) {
    return (
      <SectionMessage
        title="Sentimento registrado com sucesso!"
        appearance="confirmation"
        actions={[]}
        testId="sm-ok"
      >
        <Text>
          {isAnonymous
            ? 'Enviado anonimamente — nenhum dado pessoal foi registrado.'
            : 'Enviado de forma identificada.'}
        </Text>
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
        isAnonymous,
      });
      setSubmitted(true);
    } catch (e: any) {
      setError(`Erro ao registrar: ${e.message}`);
    }
  };

  const emotionOptions = emotions.map((e) => ({
    label: e.emoji ? `${e.emoji} ${e.name}` : e.name,
    value: String(e.id),
  }));

  return (
    <Stack space="space.200">
      {isAnonymous ? (
        <SectionMessage title="Envio anônimo" appearance="information" actions={[]} testId="sm-anon">
          <Text>Seu registro não conterá nenhum dado pessoal.</Text>
        </SectionMessage>
      ) : (
        <SectionMessage title="Envio identificado" appearance="warning" actions={[]} testId="sm-ident">
          <Text>O gestor poderá ver sua identidade.</Text>
        </SectionMessage>
      )}
      {error && (
        <SectionMessage title={error} appearance="error" actions={[]} testId="sm-err">
          <Text> </Text>
        </SectionMessage>
      )}
      {emotionsError && (
        <SectionMessage title={emotionsError} appearance="error" actions={[]} testId="sm-emo-err">
          <Text> </Text>
        </SectionMessage>
      )}
      {!emotionsLoaded && <Text>Carregando emoções...</Text>}
      {emotionsLoaded && emotionOptions.length > 0 && (
        <Select
          name="emotionId"
          options={emotionOptions}
          defaultValue={emotionOptions[0]}
          onChange={(opt: any) => setEmotionId(opt?.value ?? '')}
        />
      )}
      <Text>Intensidade: <Strong>{intensity}</Strong>/5</Text>
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
      <Checkbox
        name="isAnonymous"
        label="Enviar anonimamente"
        defaultIsChecked={true}
        onChange={(e: any) => setIsAnonymous(e.target?.checked ?? !isAnonymous)}
      />
      <Button type="button" onClick={handleSubmit}>Registrar</Button>
    </Stack>
  );
}
