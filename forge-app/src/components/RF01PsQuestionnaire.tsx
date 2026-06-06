import React, { useState, useEffect } from 'react';
import {
  Text,
  Strong as RawStrong,
  Stack as RawStack,
  SectionMessage as RawSectionMessage,
  Range as RawRange,
  Button,
} from '@forge/react';
const Strong = RawStrong as any;
const Stack = RawStack as any;
const SectionMessage = RawSectionMessage as any;
const Range = RawRange as any;
import { invoke } from '@forge/bridge';

const QUESTIONS = [
  'Se você comete um erro neste time, muitas vezes ele é usado contra você.',
  'Os membros deste time são capazes de levantar problemas e questões difíceis.',
  'As pessoas neste time às vezes rejeitam outras por serem diferentes.',
  'É seguro arriscar neste time.',
  'É difícil pedir ajuda a outros membros deste time.',
  'Nenhum membro deste time agiria de forma a prejudicar deliberadamente os esforços dos outros.',
  'Minhas habilidades únicas e talentos são valorizados e utilizados neste time.',
];

const SCALE_LABEL = '1 = Discordo totalmente · 5 = Concordo totalmente';

export default function RF01PsQuestionnaire() {
  const [settings, setSettings] = useState<any>(null);
  const [loaded, setLoaded] = useState(false);
  const [sprintState, setSprintState] = useState<any>(null);
  const [sprintLoaded, setSprintLoaded] = useState(false);
  const [answers, setAnswers] = useState<Record<string, number>>({
    q1: 3, q2: 3, q3: 3, q4: 3, q5: 3, q6: 3, q7: 3,
  });
  const [submitted, setSubmitted] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    invoke<any>('getSettings').then((s: any) => {
      setSettings(s);
      setLoaded(true);
      if (s?.jwtToken && s?.teamId) {
        invoke<any>('getSprintToken', { teamId: s.teamId, jwtToken: s.jwtToken })
          .then((state: any) => { setSprintState(state); setSprintLoaded(true); })
          .catch(() => { setSprintState({ status: 'no_active_sprint' }); setSprintLoaded(true); });
      } else {
        setSprintLoaded(true);
      }
    });
  }, []);

  if (!loaded) return <Text>Carregando...</Text>;

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

  if (!sprintLoaded) return <Text>Carregando questionário...</Text>;

  if (sprintState?.status === 'no_active_sprint') {
    return (
      <SectionMessage title="Nenhum sprint ativo" appearance="information" actions={[]} testId="sm-nosprint">
        <Text>Nenhum sprint ativo no momento. O questionário fica disponível por 48h após o encerramento do sprint.</Text>
      </SectionMessage>
    );
  }

  if (sprintState?.status === 'expired') {
    return (
      <SectionMessage title="Questionário expirado" appearance="error" actions={[]} testId="sm-expired">
        <Text>O prazo para responder este questionário encerrou. Fale com o Scrum Master.</Text>
      </SectionMessage>
    );
  }

  if (sprintState?.status === 'answered' || submitted) {
    const answeredAt = sprintState?.answered_at
      ? new Date(sprintState.answered_at).toLocaleDateString('pt-BR')
      : null;
    return (
      <SectionMessage title="Obrigado pela sua resposta!" appearance="confirmation" actions={[]} testId="sm-done">
        <Text>
          {answeredAt
            ? `Você respondeu em ${answeredAt}. Sua resposta foi registrada anonimamente.`
            : 'Sua resposta foi registrada anonimamente.'}
        </Text>
      </SectionMessage>
    );
  }

  const handleSubmit = async () => {
    setError(null);
    try {
      await invoke('submitPsQuestionnaire', {
        jwtToken: settings.jwtToken,
        sprint_token: sprintState.sprint_token,
        answers,
      });
      setSubmitted(true);
    } catch (e: any) {
      if (e.message?.includes('401')) {
        setError('Sessão expirada. Reconecte nas Configurações.');
      } else if (e.message?.includes('409')) {
        setError('Você já respondeu este questionário.');
      } else {
        setError(`Erro ao enviar: ${e.message}`);
      }
    }
  };

  return (
    <Stack space="space.200">
      <Text><Strong>Questionário de Segurança Psicológica — Sprint {sprintState?.sprint_number}</Strong></Text>
      <Text>{SCALE_LABEL}</Text>
      <SectionMessage title="Respostas anônimas" appearance="information" actions={[]} testId="sm-anon">
        <Text>Suas respostas não são associadas ao seu nome. O gestor vê apenas médias do time.</Text>
      </SectionMessage>
      {error && (
        <SectionMessage title={error} appearance="error" actions={[]} testId="sm-err">
          <Text> </Text>
        </SectionMessage>
      )}
      {QUESTIONS.map((question, idx) => {
        const key = `q${idx + 1}`;
        return (
          <Stack key={key} space="space.100">
            <Text>{idx + 1}. {question}</Text>
            <Text>Resposta: <Strong>{answers[key]}</Strong></Text>
            <Range
              name={key}
              min={1}
              max={5}
              step={1}
              value={answers[key]}
              onChange={(v: number) => setAnswers((prev) => ({ ...prev, [key]: v }))}
            />
          </Stack>
        );
      })}
      <Button type="button" onClick={handleSubmit}>Enviar respostas</Button>
    </Stack>
  );
}
